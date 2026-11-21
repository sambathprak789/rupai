"""Builds a ComfyUI API workflow from comfy/t2i_workflow.json."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderParams:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    seed: int
    steps: int
    cfg: float
    lora: str | None  # Fast mode LoRA file, None for Quality
    filename_prefix: str


class WorkflowBuilder:
    def __init__(self, template_path: Path, unet_file: str, te_file: str, vae_file: str):
        self._template = json.loads(template_path.read_text())
        self.unet_file = unet_file
        self.te_file = te_file
        self.vae_file = vae_file

    def build(self, p: RenderParams) -> dict:
        wf = copy.deepcopy(self._template)
        wf["1"]["inputs"]["unet_name"] = self.unet_file
        wf["3"]["inputs"]["clip_name"] = self.te_file
        wf["4"]["inputs"]["vae_name"] = self.vae_file
        wf["5"]["inputs"]["prompt"] = p.prompt
        wf["5"]["inputs"]["negative_prompt"] = p.negative_prompt or " "
        wf["6"]["inputs"].update(width=p.width, height=p.height, batch_size=1)
        wf["7"]["inputs"].update(seed=p.seed, steps=p.steps, cfg=p.cfg)
        wf["9"]["inputs"]["filename_prefix"] = p.filename_prefix
        if p.lora:
            # GGUF transformer -> LoRA -> KV cache
            wf["10"] = {
                "class_type": "LoraLoaderModelOnly",
                "_meta": {"title": "Fast LoRA"},
                "inputs": {"model": ["1", 0], "lora_name": p.lora, "strength_model": 1.0},
            }
            wf["2"]["inputs"]["model"] = ["10", 0]
        return wf
