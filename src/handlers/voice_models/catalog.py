from __future__ import annotations

from typing import Optional, Type, Dict, List, Tuple

from core.backends import Backend, normalize_backend
from managers.backend_manager import BackendManager


class VoiceModelSpecProtocol:
    @classmethod
    def supported_model_ids(cls) -> List[str]: ...
    @classmethod
    def build_install_plan(cls, model_id: str, ctx: dict): ...
    @classmethod
    def build_uninstall_plan(cls, model_id: str, ctx: dict): ...
    @classmethod
    def is_installed(cls, model_id: str, ctx: dict) -> bool: ...
    @classmethod
    def title(cls, model_id: str) -> str: ...


def _load_specs() -> List[Type[VoiceModelSpecProtocol]]:
    # Единственная точка, где перечисляются спеки (каталог).
    from handlers.voice_models.edge_tts_rvc_model import EdgeTTSRVCInstallSpec
    from handlers.voice_models.edge_tts_rvc_onnx_model import EdgeTTSRVCOnnxInstallSpec
    from handlers.voice_models.fish_speech_model import FishSpeechInstallSpec
    from handlers.voice_models.f5_tts_model import F5TTSInstallSpec

    return [
        EdgeTTSRVCInstallSpec,
        EdgeTTSRVCOnnxInstallSpec,
        FishSpeechInstallSpec,
        F5TTSInstallSpec,
    ]


_SPECS: List[Type[VoiceModelSpecProtocol]] = _load_specs()

_BY_ID: Dict[Tuple[str, str], Type[VoiceModelSpecProtocol]] = {}
for _spec in _SPECS:
    _backend = normalize_backend(getattr(_spec, "REQUIRED_BACKEND", None), Backend.ONNX) or Backend.ONNX
    for _mid in (_spec.supported_model_ids() or []):
        _BY_ID[(_backend.value, str(_mid))] = _spec


def get_voice_spec(model_id: str, backend: Backend | str | None = None) -> Optional[Type[VoiceModelSpecProtocol]]:
    resolved = normalize_backend(backend, BackendManager.active()) or BackendManager.active()
    return _BY_ID.get((resolved.value, str(model_id or "").strip()))


def get_all_voice_specs(backend: Backend | str | None = None) -> List[Type[VoiceModelSpecProtocol]]:
    resolved = normalize_backend(backend, BackendManager.active()) or BackendManager.active()
    return [spec for spec in _SPECS if normalize_backend(getattr(spec, "REQUIRED_BACKEND", None), Backend.ONNX) == resolved]


def get_supported_model_ids(backend: Backend | str | None = None) -> List[str]:
    resolved = normalize_backend(backend, BackendManager.active()) or BackendManager.active()
    return [model_id for spec_backend, model_id in _BY_ID.keys() if spec_backend == resolved.value]
