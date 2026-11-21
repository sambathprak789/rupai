"""Image engines: ComfyEngine talks to a local ComfyUI; MockEngine needs no GPU (MOCK=1)."""

from __future__ import annotations

import asyncio
import json
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
    async def render(self, params: RenderParams, on_step: StepCallback) -> Path: ...

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

    async def render(self, params: RenderParams, on_step: StepCallback) -> Path:
        client_id = uuid.uuid4().hex
        workflow = self.builder.build(params)
        try:
            async with websockets.connect(f"{self.ws_base}/ws?clientId={client_id}", max_size=None) as ws:
                r = await self.http.post("/prompt", json={"prompt": workflow, "client_id": client_id})
                if r.status_code != 200:
                    raise EngineError(friendly_error(_prompt_error(r)))
                prompt_id = r.json()["prompt_id"]
                await _wait_until_done(ws, prompt_id, on_step)
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


async def _wait_until_done(ws, prompt_id: str, on_step: StepCallback) -> None:
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=WS_IDLE_TIMEOUT_S)
        except TimeoutError as e:
            raise EngineError("ComfyUI stopped responding") from e
        if not isinstance(raw, str):
            continue  # binary preview frames
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

    async def render(self, params: RenderParams, on_step: StepCallback) -> Path:
        for step in range(1, params.steps + 1):
            await asyncio.sleep(self.step_delay)
            on_step(step, params.steps)
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
