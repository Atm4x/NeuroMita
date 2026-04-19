from __future__ import annotations

from enum import Enum


class Backend(str, Enum):
    CUDA = "cuda"   # PyTorch CUDA — NVIDIA
    ONNX = "onnx"   # onnxruntime DirectML — AMD и прочие


class BackendManager:
    instance: BackendManager | None = None

    def __init__(self) -> None:
        self._available: set[Backend] = self._detect()
        self._active: Backend = self._load_active()

    # ------------------------------------------------------------------ detection

    @staticmethod
    def _detect() -> set[Backend]:
        available: set[Backend] = set()
        try:
            import torch
            if torch.cuda.is_available():
                available.add(Backend.CUDA)
        except Exception:
            pass
        try:
            import onnxruntime
            providers = onnxruntime.get_available_providers()
            if "DmlExecutionProvider" in providers or "CUDAExecutionProvider" in providers:
                available.add(Backend.ONNX)
        except Exception:
            pass
        return available

    def _load_active(self) -> Backend:
        try:
            from managers.settings_manager import SettingsManager
            val = SettingsManager.get("backend", None)
            if val in (b.value for b in Backend):
                return Backend(val)
        except Exception:
            pass
        return Backend.CUDA if Backend.CUDA in self._available else Backend.ONNX

    # ------------------------------------------------------------------ public API

    def available(self) -> set[Backend]:
        return self._available

    def is_available(self, backend: Backend) -> bool:
        return backend in self._available

    def active(self) -> Backend:
        return self._active

    def set_active(self, backend: Backend) -> None:
        self._active = backend
        try:
            from managers.settings_manager import SettingsManager
            SettingsManager.set("backend", backend.value)
        except Exception:
            pass

    def install_backend(self, backend: Backend, **uv_callbacks) -> bool:
        """Устанавливает пакеты для выбранного бэкенда через uv_sync."""
        from utils.uv_sync import UvSync
        extras: set[str] = {"core"}
        if backend == Backend.CUDA:
            extras.add("backend-nvidia")
        elif backend == Backend.ONNX:
            extras.add("backend-amd")
        return UvSync(**uv_callbacks).apply(extras)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def recommend() -> Backend:
        """Рекомендует бэкенд на основе обнаруженного GPU (для первого запуска)."""
        try:
            from utils.gpu_utils import check_gpu_provider
            vendor = check_gpu_provider()
            if vendor == "NVIDIA":
                return Backend.CUDA
        except Exception:
            pass
        return Backend.ONNX
