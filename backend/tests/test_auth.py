from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, FailureLimiter
from app.main import create_app
from tests.conftest import KEY, make_settings


def test_api_requires_key(client: TestClient):
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/images/x.png").status_code == 401


def test_login_sets_httponly_strict_secure_cookie(client: TestClient):
    r = client.post("/api/auth", json={"key": KEY})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert KEY not in cookie  # cookie holds a derived token, not the key
    low = cookie.lower()
    assert "httponly" in low and "secure" in low and "samesite=strict" in low
    assert client.get("/api/health").status_code == 200


def test_bearer_key_works(client: TestClient):
    r = client.get("/api/health", headers={"Authorization": f"Bearer {KEY}"})
    assert r.status_code == 200


def test_wrong_key_401(client: TestClient):
    assert client.post("/api/auth", json={"key": "nope"}).status_code == 401
    assert client.get("/api/health", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_ten_wrong_keys_block_ip_with_429(client: TestClient):
    for _ in range(10):
        assert client.post("/api/auth", json={"key": "nope"}).status_code == 401
    # blocked even with the right key now
    assert client.post("/api/auth", json={"key": KEY}).status_code == 429
    assert client.get("/api/health", headers={"Authorization": f"Bearer {KEY}"}).status_code == 429


def test_block_is_per_cf_connecting_ip(client: TestClient):
    bad = {"CF-Connecting-IP": "1.2.3.4"}
    for _ in range(10):
        client.post("/api/auth", json={"key": "nope"}, headers=bad)
    assert client.post("/api/auth", json={"key": KEY}, headers=bad).status_code == 429
    assert client.post("/api/auth", json={"key": KEY}, headers={"CF-Connecting-IP": "5.6.7.8"}).status_code == 204


def test_missing_credentials_do_not_count(client: TestClient):
    for _ in range(20):
        assert client.get("/api/jobs").status_code == 401
    assert client.post("/api/auth", json={"key": KEY}).status_code == 204


def test_limiter_window_and_block_expiry():
    t = [0.0]
    lim = FailureLimiter(max_failures=3, window_s=60, block_s=900, clock=lambda: t[0])
    lim.record_failure("ip")
    t[0] = 61  # first failure leaves the window
    lim.record_failure("ip")
    lim.record_failure("ip")
    assert not lim.is_blocked("ip")
    lim.record_failure("ip")
    assert lim.is_blocked("ip")
    t[0] += 900
    assert not lim.is_blocked("ip")


def test_cookie_from_other_key_rejected(tmp_path):
    other = create_app(make_settings(tmp_path, rupai_key="other-key"))
    with TestClient(other, base_url="https://testserver") as c:
        token = c.app.state.auth.token
    app = create_app(make_settings(tmp_path))
    with TestClient(app, base_url="https://testserver") as c:
        c.cookies.set(COOKIE_NAME, token)
        assert c.get("/api/jobs").status_code == 401
