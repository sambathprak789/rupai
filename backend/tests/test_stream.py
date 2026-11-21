from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.engine import parse_preview
from app.eta import DEFAULT_START_S, DEFAULT_STEP_S, EtaModel, ImageTimer
from app.main import create_app
from app.models import Aspect, Mode
from tests.conftest import KEY, make_settings

# ---- WebSocket /api/ws ------------------------------------------------------------
# TestClient opens ws:// so the Secure cookie is not sent; browsers send it (checked in the e2e run)
BEARER = {"Authorization": f"Bearer {KEY}"}


def test_ws_rejects_without_key(client: TestClient):
    with pytest.raises(WebSocketDisconnect) as e, client.websocket_connect("/api/ws") as ws:
        ws.receive_json()
    assert e.value.code == 4401


def test_ws_streams_job_steps_and_previews(tmp_path):
    app = create_app(make_settings(tmp_path, mock_step_delay=0.01))
    with TestClient(app, base_url="https://testserver") as c:
        c.post("/api/auth", json={"key": KEY})
        with c.websocket_connect("/api/ws", headers=BEARER) as ws:
            job = c.post("/api/jobs", json={"prompt": "mug", "count": 2, "baseSeed": 5}).json()
            jobs, previews = [], []
            while True:
                ev = ws.receive_json()
                if ev["type"] == "job":
                    jobs.append(ev["job"])
                    if ev["job"]["status"] == "done":
                        break
                else:
                    previews.append(ev)
    assert all(j["id"] == job["id"] for j in jobs)
    # every step of both images was reported, in order (an extra event repeats the last step when an image is saved)
    steps = [(j["progress"]["imageIndex"], j["progress"]["step"]) for j in jobs if j["status"] == "running"]
    assert list(dict.fromkeys(s for s in steps if s[1] > 0)) == [(i, s) for i in range(2) for s in range(1, 9)]
    assert [len(j["images"]) for j in jobs if j["progress"]["step"] == 8][-1] == 2
    # one preview per step, a real JPEG
    assert len(previews) == 16
    assert {p["imageIndex"] for p in previews} == {0, 1}
    head, b64 = previews[-1]["dataUrl"].split(",", 1)
    assert head == "data:image/jpeg;base64" and base64.b64decode(b64)[:2] == b"\xff\xd8"
    # countdown numbers present while running, cleared when done
    running = [j for j in jobs if j["status"] == "running"]
    assert all(j["progress"]["imageEtaS"] is not None and j["progress"]["updatedAt"] for j in running)
    assert running[0]["progress"]["jobEtaS"] > running[0]["progress"]["imageEtaS"]  # 2 images
    assert jobs[-1]["progress"]["imageEtaS"] is None and len(jobs[-1]["images"]) == 2


def test_ws_snapshot_for_late_client(tmp_path):
    app = create_app(make_settings(tmp_path, mock_step_delay=0.05))
    with TestClient(app, base_url="https://testserver") as c:
        c.post("/api/auth", json={"key": KEY})
        job = c.post("/api/jobs", json={"prompt": "mug"}).json()
        with c.websocket_connect("/api/ws", headers=BEARER) as ws:  # connects after the job started
            first = ws.receive_json()
            assert first["type"] == "job" and first["job"]["id"] == job["id"]


# ---- preview frame parsing ----------------------------------------------------------


def test_parse_preview_frame():
    jpeg = b"\xff\xd8 fake jpeg"
    frame = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + jpeg
    assert parse_preview(frame) == (jpeg, "image/jpeg")
    assert parse_preview((2).to_bytes(4, "big") + b"x" * 10) is None  # other binary events ignored
    assert parse_preview(b"\x00\x01") is None


# ---- ETA model ---------------------------------------------------------------------


def test_eta_before_first_step_uses_defaults_then_counts_down():
    eta = EtaModel()
    t = ImageTimer(eta, Mode.FAST, Aspect.SQUARE, steps=8, started=100.0)
    assert t.kind == "cold"
    assert t.image_eta(100.0) == pytest.approx(DEFAULT_START_S["cold"] + 8 * DEFAULT_STEP_S[Mode.FAST])
    # 30 s later, still loading: 30 s less
    assert t.image_eta(130.0) == pytest.approx(DEFAULT_START_S["cold"] - 30 + 8 * DEFAULT_STEP_S[Mode.FAST])


def test_eta_uses_measured_step_time_and_learns():
    eta = EtaModel()
    t = ImageTimer(eta, Mode.FAST, Aspect.SQUARE, steps=8, started=0.0)
    t.on_step(1, 60.0)  # model took 60 s
    assert eta.start_s["cold"] == 60.0 and eta.last_mode is Mode.FAST
    t.on_step(3, 80.0)  # 2 steps in 20 s -> 10 s/step
    assert t.step_s(80.0) == pytest.approx(10.0)
    assert t.image_eta(80.0) == pytest.approx(5 * 10.0)
    t.on_step(8, 130.0)
    t.finish(130.0)  # (130-60)/7 = 10 s/step
    learned = eta.seconds_per_step(Mode.FAST, Aspect.SQUARE)
    assert DEFAULT_STEP_S[Mode.FAST] > learned > 10.0  # moves halfway toward the measurement
    # next fast image is "warm", a quality image is a "switch"
    assert eta.start_kind(Mode.FAST) == "warm" and eta.start_kind(Mode.QUALITY) == "switch"


def test_wide_sizes_estimated_slower():
    eta = EtaModel()
    assert eta.seconds_per_step(Mode.QUALITY, Aspect.LANDSCAPE) > eta.seconds_per_step(Mode.QUALITY, Aspect.SQUARE)
