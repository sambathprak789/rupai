"""Image engines: ComfyEngine talks to a local ComfyUI; MockEngine needs no GPU (MOCK=1)."""

from __future__ import annotations

import asyncio
import io
import json
import random
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx
import websockets
from PIL import Image as PILImage
from PIL import ImageDraw

from .workflow import RenderParams, WorkflowBuilder

StepCallback = Callable[[int, int], None]  # (step, total)
PreviewCallback = Callable[[bytes, str], None]  # (image bytes, mime type)

# ComfyUI binary WebSocket frames: 4-byte event type, then (for previews) 4-byte image format
BINARY_PREVIEW_IMAGE = 1
PREVIEW_MIME = {1: "image/jpeg", 2: "image/png"}

# ComfyUI can stay silent for minutes while loading models on a T4
WS_IDLE_TIMEOUT_S = 900


class EngineError(Exception):
    """A render failed; the message is shown to the user."""


def friendly_error(raw: str) -> str:
    low = raw.lower()
    if "out of memory" in low or "outofmemory" in low:
        return "GPU out of memory - try a smaller size, or MODEL_QUANT=Q4_K_M in the notebook"
    if "connect" in low and ("refused" in low or "error" in low):
        return "ComfyUI is not reachable - run the 'Show logs' cell in the notebook"
    return raw[:300]


class Engine(Protocol):
    async def render(
        self, params: RenderParams, on_step: StepCallback, on_preview: PreviewCallback | None = None
    ) -> Path: ...

    async def health(self) -> dict: ...

    async def close(self) -> None: ...


class ComfyEngine:
    def __init__(self, comfy_url: str, output_dir: Path, builder: WorkflowBuilder):
        self.base = comfy_url.rstrip("/")
        self.ws_base = self.base.replace("http://", "ws://").replace("https://", "wss://")
        self.output_dir = output_dir
        self.builder = builder
        self.http = httpx.AsyncClient(base_url=self.base, timeout=30)

    async def close(self) -> None:
        await self.http.aclose()

    async def health(self) -> dict:
        try:
            r = await self.http.get("/system_stats", timeout=5)
            r.raise_for_status()
        except httpx.HTTPError:
            return {"comfy": "offline"}
        dev = (r.json().get("devices") or [{}])[0]
        gb = 1024**3
        return {
            "comfy": "ready",
            "vram_total_gb": round(dev.get("vram_total", 0) / gb, 1) or None,
            "vram_free_gb": round(dev.get("vram_free", 0) / gb, 1) or None,
        }

    async def interrupt(self) -> None:
        await self.http.post("/interrupt")

    async def render(
        self, params: RenderParams, on_step: StepCallback, on_preview: PreviewCallback | None = None
    ) -> Path:
        client_id = uuid.uuid4().hex
        workflow = self.builder.build(params)
        try:
            async with websockets.connect(f"{self.ws_base}/ws?clientId={client_id}", max_size=None) as ws:
                r = await self.http.post("/prompt", json={"prompt": workflow, "client_id": client_id})
                if r.status_code != 200:
                    raise EngineError(friendly_error(_prompt_error(r)))
                prompt_id = r.json()["prompt_id"]
                await _wait_until_done(ws, prompt_id, on_step, on_preview)
            hist = (await self.http.get(f"/history/{prompt_id}")).json()[prompt_id]
        except (httpx.HTTPError, OSError, websockets.WebSocketException) as e:
            raise EngineError(friendly_error(f"connection error: {e}")) from e
        img = hist["outputs"]["9"]["images"][0]
        return self.output_dir / img.get("subfolder", "") / img["filename"]


def _prompt_error(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        return r.text
    err = body.get("error", {})
    details = [
        f"{nid}: {e.get('message')} {e.get('details', '')}".strip()
        for nid, ne in (body.get("node_errors") or {}).items()
        for e in ne.get("errors", [])
    ]
    return "; ".join([err.get("message", "invalid prompt"), *details])


def parse_preview(frame: bytes) -> tuple[bytes, str] | None:
    """Returns (image bytes, mime) for a ComfyUI PREVIEW_IMAGE frame, else None."""
    if len(frame) < 8 or int.from_bytes(frame[0:4], "big") != BINARY_PREVIEW_IMAGE:
        return None
    mime = PREVIEW_MIME.get(int.from_bytes(frame[4:8], "big"))
    return (bytes(frame[8:]), mime) if mime else None


async def _wait_until_done(
    ws, prompt_id: str, on_step: StepCallback, on_preview: PreviewCallback | None = None
) -> None:
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=WS_IDLE_TIMEOUT_S)
        except TimeoutError as e:
            raise EngineError("ComfyUI stopped responding") from e
        if not isinstance(raw, str):
            # Only one job runs at a time, so a preview belongs to the current prompt
            preview = parse_preview(raw)
            if preview and on_preview:
                on_preview(*preview)
            continue
        msg = json.loads(raw)
        data = msg.get("data", {})
        if data.get("prompt_id") not in (None, prompt_id):
            continue
        kind = msg.get("type")
        if kind == "progress":
            on_step(int(data["value"]), int(data["max"]))
        elif kind == "execution_error":
            raise EngineError(friendly_error(f"{data.get('exception_type')}: {data.get('exception_message')}"))
        elif kind == "execution_interrupted":
            raise asyncio.CancelledError()
        elif kind == "executing" and data.get("node") is None:
            return


class MockEngine:
    """Draws a placeholder image and simulates step progress. For dev and tests."""

    def __init__(self, output_dir: Path, step_delay: float = 0.3):
        self.output_dir = output_dir
        self.step_delay = step_delay

    async def close(self) -> None:
        pass

    async def health(self) -> dict:
        return {"comfy": "ready", "vram_total_gb": 15.0, "vram_free_gb": 14.5}

    async def interrupt(self) -> None:
        pass

    async def render(
        self, params: RenderParams, on_step: StepCallback, on_preview: PreviewCallback | None = None
    ) -> Path:
        for step in range(1, params.steps + 1):
            await asyncio.sleep(self.step_delay)
            on_step(step, params.steps)
            if on_preview:
                on_preview(_mock_preview(params, step / params.steps), "image/jpeg")
        path = self.output_dir / f"{params.filename_prefix}_00001_.png"
        await asyncio.to_thread(_draw_placeholder, path, params)
        return path


def _draw_placeholder(path: Path, p: RenderParams) -> None:
    hue = p.seed % 360
    img = PILImage.new("HSV", (p.width, p.height), (int(hue / 360 * 255), 90, 70)).convert("RGB")
    d = ImageDraw.Draw(img)
    lines = [
        "MOCK",
        f"{p.width}x{p.height}  seed {p.seed}",
        f"{p.steps} steps  cfg {p.cfg}  {'fast' if p.lora else 'quality'}",
        p.prompt[:80],
    ]
    for i, line in enumerate(lines):
        d.text((32, 32 + i * 28), line, fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def _mock_preview(p: RenderParams, done: float) -> bytes:
    """Noise that fades into the final placeholder colour, like a real denoising preview."""
    hue = int(p.seed % 360 / 360 * 255)
    w, h = (64, round(64 * p.height / p.width)) if p.width >= p.height else (round(64 * p.width / p.height), 64)
    rng = random.Random(p.seed)
    base = PILImage.new("HSV", (w, h), (hue, 90, 70)).convert("RGB")
    noise = PILImage.frombytes("RGB", (w, h), bytes(rng.randrange(256) for _ in range(w * h * 3)))
    img = PILImage.blend(noise, base, done).resize((w * 8, h * 8), PILImage.Resampling.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()
