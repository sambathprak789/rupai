from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from app.engine import MockEngine
from app.main import create_app
from tests.conftest import KEY, make_settings, wait_done


class SlowWarmEngine(MockEngine):
    """Mock whose 1-step warm-up takes a while, like loading models on a T4."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.renders: list[str] = []
        self.interrupts = 0

    async def render(self, params, on_step, on_preview=None):
        self.renders.append(params.prompt)
        if params.prompt == "warm-up":
            await asyncio.sleep(0.4)
        return await super().render(params, on_step, on_preview)

    async def interrupt(self):
        self.interrupts += 1


def make(tmp_path):
    s = make_settings(tmp_path, warmup=True, mock_step_delay=0.01)
    eng = SlowWarmEngine(s.output_dir, step_delay=0.01)
    return TestClient(create_app(s, engine=eng), base_url="https://testserver"), eng, s


def test_warmup_runs_first_then_job_and_leaves_no_file(tmp_path):
    c, eng, s = make(tmp_path)
    with c:
        c.post("/api/auth", json={"key": KEY})
        assert c.get("/api/health").json()["warming"] is True
        job = c.post("/api/jobs", json={"prompt": "mug"})  # allowed during warm-up, waits its turn
        assert job.status_code == 201 and job.json()["status"] == "queued"
        done = wait_done(c, job.json()["id"])
        assert done["status"] == "done"
        assert eng.renders == ["warm-up", "mug"]
        assert c.get("/api/health").json()["warming"] is False
        assert not list(s.output_dir.glob("tmp_warmup*"))  # warm-up image deleted
        assert c.get("/api/jobs").json()[0]["id"] == done["id"]  # warm-up is not a job
        # the model load was learned as the cold start, so the next job counts as warm
        app = c.app
        assert app.state.service.eta.last_mode is not None


def test_cancel_while_waiting_does_not_interrupt_warmup(tmp_path):
    c, eng, _ = make(tmp_path)
    with c:
        c.post("/api/auth", json={"key": KEY})
        job = c.post("/api/jobs", json={"prompt": "mug"}).json()
        r = c.post(f"/api/jobs/{job['id']}/cancel")
        assert r.json()["status"] == "cancelled"
        assert eng.interrupts == 0  # the warm-up keeps loading
        end = time.time() + 5
        while c.get("/api/health").json()["warming"] and time.time() < end:
            time.sleep(0.02)
        assert eng.renders == ["warm-up"]


def test_no_warmup_by_default(client: TestClient):
    client.post("/api/auth", json={"key": KEY})
    assert client.get("/api/health").json()["warming"] is False
