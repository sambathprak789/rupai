"""FastAPI app: API, protected images and (from M4) the built frontend."""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import psutil
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import COOKIE_NAME, Authenticator, FailureLimiter
from .config import Settings
from .engine import ComfyEngine, Engine, MockEngine
from .models import AuthRequest, Health, Job, JobCreate
from .service import JobConflict, JobService, NotFound, NotRunning
from .workflow import WorkflowBuilder

log = logging.getLogger("rupai")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.png$")
KEY_IN_URL_RE = re.compile(r"([?&]key=)[^&\s\"]+")


class RedactKeyFilter(logging.Filter):
    """Hides ?key=... in access logs (Item 6.3)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(KEY_IN_URL_RE.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
        record.msg = KEY_IN_URL_RE.sub(r"\1***", str(record.msg))
        return True


logging.getLogger("uvicorn.access").addFilter(RedactKeyFilter())


def build_engine(s: Settings) -> Engine:
    if s.mock:
        return MockEngine(s.output_dir, s.mock_step_delay)
    builder = WorkflowBuilder(s.workflow_path, s.unet_file, s.text_encoder_file, s.vae_file)
    return ComfyEngine(s.comfy_url, s.output_dir, builder)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    s = settings or Settings.from_env()
    eng = engine or build_engine(s)
    service = JobService(eng, s.output_dir, s.fast_lora_file)
    auth = Authenticator(s.rupai_key, FailureLimiter(s.max_failures, s.failure_window_s, s.block_s))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        log.info("RupAI backend up (mock=%s, quant=%s, warmup=%s)", s.mock, s.model_quant, s.warmup)
        if s.warmup:
            service.start_warmup()
        yield
        await service.shutdown()
        await eng.close()

    app = FastAPI(title="RupAI", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = s
    app.state.service = service
    app.state.auth = auth

    def require_auth(request: Request) -> None:
        auth.check(request)

    @app.post("/api/auth", status_code=status.HTTP_204_NO_CONTENT)
    async def login(body: AuthRequest, request: Request, response: Response) -> Response:
        auth.login(request, body.key)
        response.set_cookie(
            COOKIE_NAME,
            auth.token,
            httponly=True,
            secure=s.cookie_secure,
            samesite="strict",
            max_age=7 * 24 * 3600,
        )
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @app.get("/api/health", response_model=Health, response_model_by_alias=True, dependencies=[Depends(require_auth)])
    async def health() -> Health:
        info = await eng.health()
        mem = psutil.virtual_memory()
        return Health(
            status="ready" if info.get("comfy") == "ready" else "offline",
            mock=s.mock,
            comfy=info.get("comfy", "offline"),
            model_quant=s.model_quant,
            busy=service.busy,
            warming=service.warming,
            vram_total_gb=info.get("vram_total_gb"),
            vram_free_gb=info.get("vram_free_gb"),
            ram_total_gb=round(mem.total / 1e9, 1),
            ram_used_gb=round(mem.used / 1e9, 1),
        )

    @app.post(
        "/api/jobs",
        response_model=Job,
        response_model_by_alias=True,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_auth)],
    )
    async def create_job(body: JobCreate) -> Job:
        try:
            return service.create_job(body)
        except JobConflict as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
        except NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e

    @app.get("/api/jobs", response_model=list[Job], response_model_by_alias=True, dependencies=[Depends(require_auth)])
    async def list_jobs() -> list[Job]:
        return service.list_jobs()

    @app.get(
        "/api/jobs/{job_id}", response_model=Job, response_model_by_alias=True, dependencies=[Depends(require_auth)]
    )
    async def get_job(job_id: str) -> Job:
        try:
            return service.get_job(job_id)
        except NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e

    @app.post(
        "/api/jobs/{job_id}/cancel",
        response_model=Job,
        response_model_by_alias=True,
        dependencies=[Depends(require_auth)],
    )
    async def cancel_job(job_id: str) -> Job:
        try:
            return await service.cancel(job_id)
        except NotFound as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
        except NotRunning as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e

    @app.websocket("/api/ws")
    async def events(ws: WebSocket) -> None:
        """Live job state and step previews (M5). Same auth as the REST API (cookie or Bearer)."""
        try:
            auth.check(ws)
        except HTTPException as e:
            # Accept first so the browser receives the code: 4401 = need key, 4429 = blocked
            await ws.accept()
            await ws.close(code=4000 + e.status_code)
            return
        await ws.accept()
        queue = service.subscribe()
        try:
            for event in service.snapshot():
                await ws.send_json(event)

            async def pump() -> None:
                while True:
                    await ws.send_json(await queue.get())

            async def drain() -> None:
                while True:
                    await ws.receive_text()  # client sends nothing; this notices disconnects

            tasks = [asyncio.create_task(pump()), asyncio.create_task(drain())]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in tasks:
                with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                    await t
        finally:
            service.unsubscribe(queue)

    @app.get("/images/{filename}", dependencies=[Depends(require_auth)])
    async def get_image(filename: str) -> FileResponse:
        if not FILENAME_RE.match(filename):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        path = s.output_dir / filename
        if not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    if s.static_dir and Path(s.static_dir).is_dir():
        # Built React app (M4). Mounted last so /api and /images win.
        app.mount("/", StaticFiles(directory=s.static_dir, html=True), name="static")

    return app
