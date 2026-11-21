from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.engine import MockEngine
from app.main import create_app
from tests.conftest import KEY, make_settings, wait_done


class RecordingEngine(MockEngine):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.interrupts = 0

    async def interrupt(self) -> None:
        self.interrupts += 1


def make_client(tmp_path, delay=0.05):
    s = make_settings(tmp_path)
    engine = RecordingEngine(s.output_dir, step_delay=delay)
    c = TestClient(create_app(s, engine=engine), base_url="https://testserver")
    return c, engine


def test_cancel_keeps_finished_images_and_frees_slot(tmp_path):
    c, engine = make_client(tmp_path)
    with c:
        c.post("/api/auth", json={"key": KEY})
        job = c.post("/api/jobs", json={"prompt": "mug", "count": 3, "baseSeed": 1}).json()
        # wait until the first image is saved and the second is rendering
        for _ in range(200):
            j = c.get(f"/api/jobs/{job['id']}").json()
            if len(j["images"]) == 1 and j["progress"]["step"] >= 1:
                break
            time.sleep(0.01)
        r = c.post(f"/api/jobs/{job['id']}/cancel")
        assert r.status_code == 200
        done = r.json()
        assert done["status"] == "cancelled"
        assert [i["seed"] for i in done["images"]] == [1]  # image 1 kept, 2 and 3 never saved
        assert done["finishedAt"] is not None and done["progress"]["jobEtaS"] is None
        assert engine.interrupts == 1
        assert c.get("/api/health").json()["busy"] is False
        assert c.post("/api/jobs", json={"prompt": "next"}).status_code == 201  # GPU slot free again
        # the kept image is still served
        assert c.get(done["images"][0]["url"]).status_code == 200


def test_cancel_finished_job_409_and_unknown_404(tmp_path):
    c, _ = make_client(tmp_path, delay=0.0)
    with c:
        c.post("/api/auth", json={"key": KEY})
        job = wait_done(c, c.post("/api/jobs", json={"prompt": "mug"}).json()["id"])
        assert c.post(f"/api/jobs/{job['id']}/cancel").status_code == 409
        assert c.post("/api/jobs/nope/cancel").status_code == 404


def test_cancel_requires_key(tmp_path):
    with TestClient(create_app(make_settings(tmp_path)), base_url="https://testserver") as c:
        assert c.post("/api/jobs/x/cancel").status_code == 401


def test_cancel_pushes_cancelled_state_over_websocket(tmp_path):
    c, _ = make_client(tmp_path)
    with c:
        c.post("/api/auth", json={"key": KEY})
        with c.websocket_connect("/api/ws", headers={"Authorization": f"Bearer {KEY}"}) as ws:
            job = c.post("/api/jobs", json={"prompt": "mug", "count": 2}).json()
            while True:  # wait for the first step
                ev = ws.receive_json()
                if ev["type"] == "job" and ev["job"]["progress"]["step"] >= 1:
                    break
            c.post(f"/api/jobs/{job['id']}/cancel")
            while True:
                ev = ws.receive_json()
                if ev["type"] == "job" and ev["job"]["status"] != "running":
                    break
        assert ev["job"]["status"] == "cancelled"
