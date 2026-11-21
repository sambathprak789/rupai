"""In-memory job store and runner (Item 4.4: history lives in RAM until the session ends)."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import uuid
from pathlib import Path

from .engine import Engine, EngineError
from .models import SEED_MAX, SIZES, Image, Job, JobCreate, Mode, Status, now
from .workflow import RenderParams

log = logging.getLogger("rupai")


class JobConflict(Exception):
    """Another job is running (409)."""


class NotFound(Exception):
    """Unknown job or image id (404)."""


class JobService:
    def __init__(self, engine: Engine, output_dir: Path, fast_lora: str):
        self.engine = engine
        self.output_dir = output_dir
        self.fast_lora = fast_lora
        self.jobs: dict[str, Job] = {}
        self.images: dict[str, Image] = {}
        self.active_id: str | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        output_dir.mkdir(parents=True, exist_ok=True)

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

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def _run(self, job: Job) -> None:
        job.status = Status.RUNNING
        try:
            for index in range(job.count):
                seed = (job.base_seed + index) % (SEED_MAX + 1)
                job.progress.image_index = index
                job.progress.step = 0
                job.progress.total_steps = job.steps
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

                def on_step(step: int, total: int) -> None:
                    job.progress.step = step
                    job.progress.total_steps = total

                raw = await self.engine.render(params, on_step)
                job.images.append(self._store_image(job, index, seed, raw))
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
            self.active_id = None

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
