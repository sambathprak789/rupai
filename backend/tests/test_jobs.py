from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine import EngineError
from app.main import create_app
from app.workflow import RenderParams
from tests.conftest import KEY, make_settings, wait_done


def post(client: TestClient, **body):
    body.setdefault("prompt", "a blue mug")
    return client.post("/api/jobs", json=body)


# ---- validation (Item 5.4) -------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"prompt": "   "},
        {"prompt": "x" * 5001},
        {"negativePrompt": "x" * 1001},
        {"aspect": "4:3"},
        {"mode": "turbo"},
        {"count": 0},
        {"count": 5},
        {"baseSeed": -1},
        {"baseSeed": 2**32},
        {"mode": "quality", "count": 2},
        {"mode": "quality", "steps": 9},
        {"mode": "quality", "steps": 61},
        {"mode": "quality", "cfg": 0.5},
        {"mode": "quality", "cfg": 10.5},
        {"mode": "quality", "cfg": 5.25},
        {"unknownField": 1},
    ],
)
def test_invalid_bodies_422(authed: TestClient, body: dict):
    assert post(authed, **body).status_code == 422


def test_prompt_at_max_length_accepted(authed: TestClient):
    r = post(authed, prompt="x" * 5000)
    assert r.status_code == 201
    assert len(r.json()["prompt"]) == 5000


def test_fast_mode_locks_steps_and_cfg(authed: TestClient):
    r = post(authed, mode="fast", steps=40, cfg=7.5, count=2, baseSeed=10)
    assert r.status_code == 201
    job = r.json()
    assert (job["steps"], job["cfg"], job["count"]) == (8, 1.0, 2)


def test_quality_defaults(authed: TestClient):
    job = post(authed, mode="quality", negativePrompt="").json()
    assert (job["steps"], job["cfg"], job["count"]) == (35, 5.0, 1)
    assert job["negativePrompt"] == " "  # empty would disable true CFG


@pytest.mark.parametrize("aspect,size", [("1:1", (1024, 1024)), ("16:9", (1344, 768)), ("9:16", (768, 1344))])
def test_aspect_sizes(authed: TestClient, aspect, size):
    job = post(authed, aspect=aspect).json()
    assert (job["width"], job["height"]) == size


# ---- job flow (MOCK) -------------------------------------------------------


def test_fast_job_runs_and_serves_images(authed: TestClient, settings):
    job = post(authed, count=2, baseSeed=41).json()
    assert job["status"] in ("queued", "running")
    done = wait_done(authed, job["id"])
    assert done["status"] == "done"
    assert [i["seed"] for i in done["images"]] == [41, 42]
    assert all(i["mode"] == "fast" for i in done["images"])
    img = done["images"][0]
    assert "_fast_seed41" in img["filename"]
    r = authed.get(img["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    # temp files renamed, nothing left behind
    assert not list(Path(settings.output_dir).glob("tmp_*"))


def test_seed_wraps_at_uint32(authed: TestClient):
    done = wait_done(authed, post(authed, count=2, baseSeed=2**32 - 1).json()["id"])
    assert [i["seed"] for i in done["images"]] == [2**32 - 1, 0]


def test_second_job_while_running_409(tmp_path):
    s = make_settings(tmp_path, mock_step_delay=0.05)
    with TestClient(create_app(s), base_url="https://testserver") as c:
        c.post("/api/auth", json={"key": KEY})
        first = post(c)
        assert first.status_code == 201
        assert post(c).status_code == 409
        assert c.get("/api/health").json()["busy"] is True
        wait_done(c, first.json()["id"])
        assert post(c).status_code == 201


def test_render_in_quality_source_image(authed: TestClient):
    fast = wait_done(authed, post(authed, baseSeed=7).json()["id"])
    src = fast["images"][0]
    q = post(authed, mode="quality", baseSeed=src["seed"], sourceImageId=src["id"]).json()
    assert q["sourceImageId"] == src["id"] and q["mode"] == "quality"
    done = wait_done(authed, q["id"])
    assert done["images"][0]["mode"] == "quality"


def test_unknown_source_image_404(authed: TestClient):
    assert post(authed, mode="quality", sourceImageId="nope").status_code == 404


def test_jobs_list_newest_first_and_get_404(authed: TestClient):
    a = wait_done(authed, post(authed).json()["id"])
    b = wait_done(authed, post(authed).json()["id"])
    ids = [j["id"] for j in authed.get("/api/jobs").json()]
    assert ids[:2] == [b["id"], a["id"]]
    assert authed.get("/api/jobs/nope").status_code == 404


def test_image_path_traversal_blocked(authed: TestClient):
    assert authed.get("/images/..%2Fsecret.png").status_code == 404
    assert authed.get("/images/x.txt").status_code == 404


def test_health_shape(authed: TestClient):
    h = authed.get("/api/health").json()
    assert h["status"] == "ready" and h["mock"] is True and h["modelQuant"] == "Q5_K_M"
    assert {"vramTotalGb", "ramTotalGb", "busy"} <= h.keys()


# ---- failures -----------------------------------------------------------------


class FailingEngine:
    def __init__(self, message: str):
        self.message = message

    async def render(self, params: RenderParams, on_step, on_preview=None):
        on_step(1, params.steps)
        raise EngineError(self.message)

    async def health(self):
        return {"comfy": "ready"}

    async def close(self):
        pass


def test_engine_error_marks_job_failed_and_frees_slot(tmp_path):
    app = create_app(make_settings(tmp_path), engine=FailingEngine("GPU out of memory"))
    with TestClient(app, base_url="https://testserver") as c:
        c.post("/api/auth", json={"key": KEY})
        job = wait_done(c, post(c).json()["id"])
        assert job["status"] == "failed" and "out of memory" in job["error"]
        assert job["finishedAt"] is not None
        assert post(c).status_code == 201  # slot released


class CrashingEngine(FailingEngine):
    async def render(self, params, on_step, on_preview=None):
        await asyncio.sleep(0)
        raise RuntimeError("boom")


def test_unexpected_crash_is_hidden_behind_generic_error(tmp_path):
    app = create_app(make_settings(tmp_path), engine=CrashingEngine(""))
    with TestClient(app, base_url="https://testserver") as c:
        c.post("/api/auth", json={"key": KEY})
        job = wait_done(c, post(c).json()["id"])
        assert job["status"] == "failed" and "boom" not in job["error"]
