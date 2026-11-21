"""API data model (spec Stage 5). JSON uses camelCase to match the TypeScript frontend."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

SEED_MAX = 2**32 - 1


class Mode(StrEnum):
    FAST = "fast"
    QUALITY = "quality"


class Aspect(StrEnum):
    SQUARE = "1:1"
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


SIZES: dict[Aspect, tuple[int, int]] = {
    Aspect.SQUARE: (1024, 1024),
    Aspect.LANDSCAPE: (1344, 768),
    Aspect.PORTRAIT: (768, 1344),
}

FAST_STEPS = 8
FAST_CFG = 1.0
QUALITY_STEPS = 35
QUALITY_CFG = 5.0


def now() -> datetime:
    return datetime.now(UTC)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class JobCreate(ApiModel):
    """Body of POST /api/jobs (Item 5.4 rules)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    mode: Mode = Mode.FAST
    prompt: Annotated[str, Field(max_length=2000)]
    negative_prompt: Annotated[str, Field(max_length=1000)] = " "
    aspect: Aspect = Aspect.SQUARE
    steps: int | None = None
    cfg: float | None = None
    base_seed: Annotated[int, Field(ge=0, le=SEED_MAX)] | None = None
    count: Annotated[int, Field(ge=1, le=4)] = 1
    source_image_id: str | None = None

    @field_validator("prompt")
    @classmethod
    def prompt_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt must not be empty")
        return v

    @field_validator("negative_prompt")
    @classmethod
    def negative_never_empty(cls, v: str) -> str:
        # An empty negative prompt disables true CFG in Qwen-Image 2.1
        return v if v.strip() else " "

    @model_validator(mode="after")
    def apply_mode_rules(self) -> JobCreate:
        if self.mode is Mode.FAST:
            # Fast is locked: silently reset (Item 5.4, choice A)
            self.steps = FAST_STEPS
            self.cfg = FAST_CFG
            return self
        if self.count != 1:
            raise ValueError("quality mode renders exactly 1 image")
        steps = QUALITY_STEPS if self.steps is None else self.steps
        cfg = QUALITY_CFG if self.cfg is None else self.cfg
        if not 10 <= steps <= 60:
            raise ValueError("steps must be between 10 and 60 in quality mode")
        if not 1.0 <= cfg <= 10.0 or (cfg * 2) != int(cfg * 2):
            raise ValueError("cfg must be 1.0-10.0 in steps of 0.5")
        self.steps, self.cfg = steps, cfg
        return self


class Progress(ApiModel):
    image_index: int = 0
    step: int = 0
    total_steps: int = 0


class Image(ApiModel):
    id: str
    job_id: str
    index: int
    seed: int
    mode: Mode
    filename: str
    url: str
    width: int
    height: int
    created_at: datetime


class Job(ApiModel):
    id: str
    mode: Mode
    prompt: str
    negative_prompt: str
    aspect: Aspect
    width: int
    height: int
    steps: int
    cfg: float
    base_seed: int
    count: int
    source_image_id: str | None = None
    status: Status = Status.QUEUED
    progress: Progress = Field(default_factory=Progress)
    error: str | None = None
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
    images: list[Image] = Field(default_factory=list)


class AuthRequest(ApiModel):
    key: Annotated[str, Field(min_length=1, max_length=256)]


class Health(ApiModel):
    status: str  # "ready" | "offline"
    mock: bool
    comfy: str  # "ready" | "offline"
    model_quant: str
    busy: bool
    vram_total_gb: float | None = None
    vram_free_gb: float | None = None
    ram_total_gb: float | None = None
    ram_used_gb: float | None = None
