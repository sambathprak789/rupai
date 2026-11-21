"""Time estimates for the countdown (spec 2.3 Flow 2).

Starts from the M1/M1b measurements on a Colab T4 and learns from finished images in this session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Aspect, Mode

# M1/M1b on T4, Q5_K_M, 1024x1024 (seconds per step, VAE decode included)
DEFAULT_STEP_S = {Mode.FAST: 21.2, Mode.QUALITY: 38.6}
# 16:9 and 9:16 measured ~8% slower than 1:1
ASPECT_FACTOR = {Aspect.SQUARE: 1.0, Aspect.LANDSCAPE: 1.08, Aspect.PORTRAIT: 1.08}
# Seconds before the first step: model load (cold), mode switch (LoRA on/off), or same mode again (warm)
DEFAULT_START_S = {"cold": 90.0, "switch": 45.0, "warm": 30.0}
LEARN_RATE = 0.5


@dataclass
class EtaModel:
    step_s: dict[tuple[Mode, Aspect], float] = field(default_factory=dict)
    start_s: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_START_S))
    last_mode: Mode | None = None  # mode of the last image that reached step 1

    def start_kind(self, mode: Mode) -> str:
        if self.last_mode is None:
            return "cold"
        return "warm" if mode == self.last_mode else "switch"

    def seconds_per_step(self, mode: Mode, aspect: Aspect) -> float:
        learned = self.step_s.get((mode, aspect))
        return learned if learned is not None else DEFAULT_STEP_S[mode] * ASPECT_FACTOR[aspect]

    def expected_start(self, mode: Mode) -> float:
        return self.start_s[self.start_kind(mode)]

    def learn_start(self, kind: str, seconds: float) -> None:
        if kind == "cold":
            self.start_s[kind] = seconds  # happens once per session
        else:
            self.start_s[kind] += LEARN_RATE * (seconds - self.start_s[kind])

    def learn_step(self, mode: Mode, aspect: Aspect, seconds: float) -> None:
        current = self.seconds_per_step(mode, aspect)
        self.step_s[(mode, aspect)] = current + LEARN_RATE * (seconds - current)


@dataclass
class ImageTimer:
    """Tracks one image render and produces the numbers the UI counts down from."""

    eta: EtaModel
    mode: Mode
    aspect: Aspect
    steps: int
    started: float
    kind: str = ""
    first_step_at: float | None = None
    last_step: int = 0

    def __post_init__(self) -> None:
        self.kind = self.eta.start_kind(self.mode)

    def on_step(self, step: int, now: float) -> None:
        if self.first_step_at is None:
            self.first_step_at = now
            self.eta.learn_start(self.kind, now - self.started)
            self.eta.last_mode = self.mode
        self.last_step = step

    def measured_step_s(self, now: float) -> float | None:
        if self.first_step_at is None or self.last_step < 2:
            return None
        return (now - self.first_step_at) / (self.last_step - 1)

    def step_s(self, now: float) -> float:
        measured = self.measured_step_s(now)
        return measured if measured is not None else self.eta.seconds_per_step(self.mode, self.aspect)

    def image_eta(self, now: float) -> float:
        sps = self.step_s(now)
        if self.first_step_at is None:
            waited = now - self.started
            return max(0.0, self.eta.expected_start(self.mode) - waited) + self.steps * sps
        return max(0, self.steps - self.last_step) * sps

    def finish(self, now: float) -> None:
        if self.first_step_at is not None and self.steps > 1:
            # first step event fires after step 1 completes; the rest include the final decode
            self.eta.learn_step(self.mode, self.aspect, (now - self.first_step_at) / (self.steps - 1))

    def remaining_images_eta(self, images_left: int) -> float:
        per_image = self.eta.start_s["warm"] + self.steps * self.eta.seconds_per_step(self.mode, self.aspect)
        return images_left * per_image
