"""Access-key auth (Item 6.1/6.3) and failed-attempt rate limiting (Item 6.4)."""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, WebSocket, status

COOKIE_NAME = "rupai_session"


def session_token(key: str) -> str:
    """Cookie value derived from the key, so the raw key never sits in a cookie."""
    return hmac.new(key.encode(), b"rupai-session-v1", hashlib.sha256).hexdigest()


def client_ip(conn: Request | WebSocket) -> str:
    # Cloudflare tunnel forwards the real client IP in this header
    return conn.headers.get("cf-connecting-ip") or (conn.client.host if conn.client else "unknown")


class FailureLimiter:
    """Blocks an IP for `block_s` after `max_failures` wrong keys within `window_s`."""

    def __init__(self, max_failures: int, window_s: int, block_s: int, clock=time.monotonic):
        self.max_failures = max_failures
        self.window_s = window_s
        self.block_s = block_s
        self.clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    def is_blocked(self, ip: str) -> bool:
        until = self._blocked_until.get(ip)
        if until is None:
            return False
        if self.clock() >= until:
            del self._blocked_until[ip]
            return False
        return True

    def record_failure(self, ip: str) -> None:
        t = self.clock()
        q = self._failures[ip]
        q.append(t)
        while q and t - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.max_failures:
            self._blocked_until[ip] = t + self.block_s
            q.clear()

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)


class Authenticator:
    def __init__(self, key: str, limiter: FailureLimiter):
        self._key = key
        self._token = session_token(key)
        self.limiter = limiter

    def key_matches(self, candidate: str) -> bool:
        return hmac.compare_digest(candidate.encode(), self._key.encode())

    def token_matches(self, candidate: str) -> bool:
        return hmac.compare_digest(candidate.encode(), self._token.encode())

    @property
    def token(self) -> str:
        return self._token

    def check(self, conn: Request | WebSocket) -> None:
        """Accept `Authorization: Bearer <key>` or the session cookie. Raises 401/429."""
        ip = client_ip(conn)
        if self.limiter.is_blocked(ip):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong keys. Try again later.")
        auth = conn.headers.get("authorization", "")
        cookie = conn.cookies.get(COOKIE_NAME)
        if auth.lower().startswith("bearer "):
            if self.key_matches(auth[7:].strip()):
                return
        elif cookie:
            if self.token_matches(cookie):
                return
        else:
            # No credentials at all: not counted as an attempt
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing key")
        self.limiter.record_failure(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong key")

    def login(self, conn: Request, key: str) -> None:
        ip = client_ip(conn)
        if self.limiter.is_blocked(ip):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong keys. Try again later.")
        if not self.key_matches(key):
            self.limiter.record_failure(ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong key")
        self.limiter.reset(ip)
