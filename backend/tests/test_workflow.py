from __future__ import annotations

from app.config import REPO_ROOT
from app.engine import _prompt_error, friendly_error
from app.workflow import RenderParams, WorkflowBuilder

BUILDER = WorkflowBuilder(REPO_ROOT / "comfy" / "t2i_workflow.json", "unet.gguf", "te.safetensors", "vae.safetensors")


def params(**kw) -> RenderParams:
    base = dict(
        prompt="p",
        negative_prompt="",
        width=1344,
        height=768,
        seed=9,
        steps=8,
        cfg=1.0,
        lora=None,
        filename_prefix="tmp_x_0",
    )
    base.update(kw)
    return RenderParams(**base)


def test_quality_workflow_has_no_lora():
    wf = BUILDER.build(params(steps=35, cfg=5.0, negative_prompt="blurry"))
    assert "10" not in wf
    assert wf["2"]["inputs"]["model"] == ["1", 0]
    assert wf["1"]["inputs"]["unet_name"] == "unet.gguf"
    assert wf["3"]["inputs"]["clip_name"] == "te.safetensors"
    assert wf["5"]["inputs"]["negative_prompt"] == "blurry"
    assert wf["6"]["inputs"] == {"width": 1344, "height": 768, "batch_size": 1}
    k = wf["7"]["inputs"]
    assert (k["seed"], k["steps"], k["cfg"], k["sampler_name"], k["scheduler"]) == (9, 35, 5.0, "er_sde", "simple")
    assert wf["9"]["inputs"]["filename_prefix"] == "tmp_x_0"


def test_fast_workflow_inserts_lora_between_unet_and_cache():
    wf = BUILDER.build(params(lora="fast.safetensors"))
    assert wf["10"]["class_type"] == "LoraLoaderModelOnly"
    assert wf["10"]["inputs"] == {"model": ["1", 0], "lora_name": "fast.safetensors", "strength_model": 1.0}
    assert wf["2"]["inputs"]["model"] == ["10", 0]
    assert wf["5"]["inputs"]["negative_prompt"] == " "


def test_builder_does_not_mutate_template():
    BUILDER.build(params(lora="fast.safetensors"))
    assert "10" not in BUILDER.build(params())


def test_friendly_errors():
    assert "smaller size" in friendly_error("torch.OutOfMemoryError: CUDA out of memory")
    assert friendly_error("x" * 1000) == "x" * 300


class FakeResp:
    def __init__(self, body):
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def test_prompt_error_lists_node_errors():
    body = {
        "error": {"message": "Prompt outputs failed validation"},
        "node_errors": {"10": {"errors": [{"message": "Value not in list", "details": "lora_name: x"}]}},
    }
    msg = _prompt_error(FakeResp(body))
    assert "failed validation" in msg and "10: Value not in list lora_name: x" in msg
