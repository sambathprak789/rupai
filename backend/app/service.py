"""In-memory job store and runner (Item 4.4: history lives in RAM until the session ends)."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import secrets
import time
import uuid
from pathlib import Path

from .engine import Engine, EngineError
from .eta import EtaModel, ImageTimer
from .models import SEED_MAX, SIZES, Image, Job, JobCreate, Mode, Status, now
from .workflow import RenderParams

SUBSCRIBER_QUEUE = 64

log = logging.getLogger("rupai")


class JobConflict(Exception):
    """Another job is running (409)."""


class NotFound(Exception):
    """Unknown job or image id (404)."""


class NotRunning(Exception):
    """Cancel on a job that already finished (409)."""


class JobService:
    def __init__(self, engine: Engine, output_dir: Path, fast_lora: str):
        self.engine = engine
        self.output_dir = output_dir
        self.fast_lora = fast_lora
        self.jobs: dict[str, Job] = {}
        self.images: dict[str, Image] = {}
        self.active_id: str | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self.eta = EtaModel()
        self.latest_preview: dict | None = None  # last preview event of the active job
        self._subscribers: set[asyncio.Queue] = set()
        output_dir.mkdir(parents=True, exist_ok=True)

    # ---- live events (WebSocket /api/ws) ------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _publish(self, event: dict) -> None:
        for q in self._subscribers:
            if q.full():
                if event["type"] == "preview":
                    continue  # a slow browser skips previews, never job state
                while not q.empty():
                    q.get_nowait()
            q.put_nowait(event)

    def _publish_job(self, job: Job) -> None:
        self._publish({"type": "job", "job": job.model_dump(by_alias=True, mode="json")})

    def snapshot(self) -> list[dict]:
        """Events a new WebSocket client needs to catch up with the active job."""
        if self.active_id is None:
            return []
        events = [{"type": "job", "job": self.jobs[self.active_id].model_dump(by_alias=True, mode="json")}]
        if self.latest_preview:
            events.append(self.latest_preview)
        return events

    @property
    def busy(self) -> bool:
        return self.active_id is not None

    def list_jobs(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def get_job(self, job_id: str) -> Job:
        try:
            return self.jobs[job_id]
        except KeyError:
            raise NotFound(f"job {job_id} not found") from None

    def create_job(self, req: JobCreate) -> Job:
        # No await between the busy check and taking the slot: atomic on the event loop
        if self.busy:
            raise JobConflict("A job is already running")
        if req.source_image_id is not None and req.source_image_id not in self.images:
            raise NotFound(f"image {req.source_image_id} not found")
        width, height = SIZES[req.aspect]
        job = Job(
            id=uuid.uuid4().hex,
            mode=req.mode,
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            aspect=req.aspect,
            width=width,
            height=height,
            steps=req.steps,
            cfg=req.cfg,
            base_seed=req.base_seed if req.base_seed is not None else secrets.randbelow(SEED_MAX + 1),
            count=req.count,
            source_image_id=req.source_image_id,
        )
        self.jobs[job.id] = job
        self.active_id = job.id
        self._tasks[job.id] = asyncio.create_task(self._run(job))
        return job

    async def cancel(self, job_id: str) -> Job:
        """Stops the job: interrupts ComfyUI, keeps the images that are already done (spec 5.3)."""
        job = self.get_job(job_id)
        if job.id != self.active_id:
            raise NotRunning(f"job {job_id} is not running")
        await self.engine.interrupt()
        task = self._tasks.get(job.id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return job

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    def _update_eta(self, job: Job, timer: ImageTimer) -> None:
        t = time.monotonic()
        image_eta = timer.image_eta(t)
        images_left = job.count - job.progress.image_index - 1
        job.progress.seconds_per_step = round(timer.step_s(t), 1)
        job.progress.image_eta_s = round(image_eta, 1)
        job.progress.job_eta_s = round(image_eta + timer.remaining_images_eta(images_left), 1)
        job.progress.updated_at = now()

    async def _run(self, job: Job) -> None:
        job.status = Status.RUNNING
        try:
            for index in range(job.count):
                seed = (job.base_seed + index) % (SEED_MAX + 1)
                job.progress.image_index = index
                job.progress.step = 0
                job.progress.total_steps = job.steps
                self.latest_preview = None
                timer = ImageTimer(self.eta, job.mode, job.aspect, job.steps, started=time.monotonic())
                self._update_eta(job, timer)
                self._publish_job(job)
                params = RenderParams(
                    prompt=job.prompt,
                    negative_prompt=job.negative_prompt,
                    width=job.width,
                    height=job.height,
                    seed=seed,
                    steps=job.steps,
                    cfg=job.cfg,
                    lora=self.fast_lora if job.mode is Mode.FAST else None,
                    filename_prefix=f"tmp_{job.id}_{index}",
                )

                def on_step(step: int, total: int, timer=timer, index=index) -> None:
                    timer.on_step(step, time.monotonic())
                    job.progress.image_index = index
                    job.progress.step = step
                    job.progress.total_steps = total
                    self._update_eta(job, timer)
                    self._publish_job(job)

                def on_preview(data: bytes, mime: str, index=index) -> None:
                    event = {
                        "type": "preview",
                        "jobId": job.id,
                        "imageIndex": index,
                        "step": job.progress.step,
                        "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode()}",
                    }
                    self.latest_preview = event
                    self._publish(event)

                raw = await self.engine.render(params, on_step, on_preview)
                timer.finish(time.monotonic())
                job.images.append(self._store_image(job, index, seed, raw))
                self.latest_preview = None
                self._publish_job(job)
            job.status = Status.DONE
        except asyncio.CancelledError:
            job.status = Status.CANCELLED
        except EngineError as e:
            job.status = Status.FAILED
            job.error = str(e)
        except Exception:
            log.exception("job %s crashed", job.id)
            job.status = Status.FAILED
            job.error = "Internal error - run the 'Show logs' cell in the notebook"
        finally:
            job.finished_at = now()
            job.progress.image_eta_s = job.progress.job_eta_s = None
            self.active_id = None
            self.latest_preview = None
            self._publish_job(job)

    def _store_image(self, job: Job, index: int, seed: int, raw: Path) -> Image:
        stem = f"rupai_{now():%Y%m%d-%H%M}_{job.mode.value}_seed{seed}"
        final = self.output_dir / f"{stem}.png"
        n = 2
        while final.exists():
            final = self.output_dir / f"{stem}-{n}.png"
            n += 1
        os.replace(raw, final)
        image = Image(
            id=uuid.uuid4().hex,
            job_id=job.id,
            index=index,
            seed=seed,
            mode=job.mode,
            filename=final.name,
            url=f"/images/{final.name}",
            width=job.width,
            height=job.height,
            created_at=now(),
        )
        self.images[image.id] = image
        return image
