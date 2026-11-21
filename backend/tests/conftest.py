from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

KEY = "test-key-123"


def make_settings(tmp_path: Path, **kw) -> Settings:
    defaults = dict(rupai_key=KEY, output_dir=tmp_path / "outputs", mock=True, mock_step_delay=0.0)
    defaults.update(kw)
    return Settings(**defaults)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings: Settings):
    # https base URL so the Secure session cookie is sent back
    with TestClient(create_app(settings), base_url="https://testserver") as c:
        yield c


@pytest.fixture
def authed(client: TestClient) -> TestClient:
    r = client.post("/api/auth", json={"key": KEY})
    assert r.status_code == 204
    return client


def wait_done(client: TestClient, job_id: str, timeout: float = 10) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")
