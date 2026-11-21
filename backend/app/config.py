"""Settings read from environment variables (see spec Item 7.3)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    rupai_key: str
    comfy_url: str = "http://127.0.0.1:8188"
    output_dir: Path = Path("/content/outputs")
    mock: bool = False
    model_quant: str = "Q5_K_M"
    text_encoder_file: str = "qwen3vl_8b_int8_convrot.safetensors"
    vae_file: str = "qwen_image_2.1_vae_bf16.safetensors"
    fast_lora_file: str = "p_q_image_2.1_8_steps_v0.1_comfyui_bf16.safetensors"
    workflow_path: Path = REPO_ROOT / "comfy" / "t2i_workflow.json"
    static_dir: Path | None = None
    cookie_secure: bool = True
    mock_step_delay: float = 0.3
    # auth rate limit (Item 6.4)
    max_failures: int = 10
    failure_window_s: int = 60
    block_s: int = 15 * 60

    @property
    def unet_file(self) -> str:
        return f"qwen-image-2.1-step90000-{self.model_quant}.gguf"

    @classmethod
    def from_env(cls) -> Settings:
        key = os.environ.get("RUPAI_KEY") or secrets.token_urlsafe(24)
        static = os.environ.get("STATIC_DIR")
        return cls(
            rupai_key=key,
            comfy_url=os.environ.get("COMFY_URL", cls.comfy_url),
            output_dir=Path(os.environ.get("OUTPUT_DIR", str(cls.output_dir))),
            mock=_bool(os.environ.get("MOCK"), False),
            model_quant=os.environ.get("MODEL_QUANT", cls.model_quant),
            text_encoder_file=os.environ.get("TEXT_ENCODER_FILE", cls.text_encoder_file),
            static_dir=Path(static) if static else None,
            cookie_secure=_bool(os.environ.get("COOKIE_SECURE"), True),
        )
