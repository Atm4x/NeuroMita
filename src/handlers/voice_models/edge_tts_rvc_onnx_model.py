from __future__ import annotations

from copy import deepcopy

from core.backends import Backend
from handlers.voice_models.edge_tts_rvc_model import EdgeTTSRVCInstallSpec, EdgeTTS_RVC_Model


class EdgeTTSRVCOnnxInstallSpec(EdgeTTSRVCInstallSpec):
    REQUIRED_BACKEND = Backend.ONNX

    @classmethod
    def requirements(cls, model_id: str, ctx: dict) -> list:
        return super().requirements(model_id, {"backend": Backend.ONNX.value, **(ctx or {})})

    @classmethod
    def build_install_plan(cls, model_id: str, ctx: dict):
        return super().build_install_plan(model_id, {"backend": Backend.ONNX.value, **(ctx or {})})

    @classmethod
    def build_uninstall_plan(cls, model_id: str, ctx: dict):
        return super().build_uninstall_plan(model_id, {"backend": Backend.ONNX.value, **(ctx or {})})

    @classmethod
    def is_installed(cls, model_id: str, ctx: dict) -> bool:
        return super().is_installed(model_id, {"backend": Backend.ONNX.value, **(ctx or {})})


class EdgeTTS_RVC_ONNX_Model(EdgeTTS_RVC_Model):
    REQUIRED_BACKEND = Backend.ONNX
    MODEL_CONFIGS = deepcopy(EdgeTTS_RVC_Model.MODEL_CONFIGS)

    for _cfg in MODEL_CONFIGS:
        _cfg["backend"] = [Backend.ONNX.value]
