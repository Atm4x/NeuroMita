from __future__ import annotations

from enum import Enum


class Backend(str, Enum):
    CUDA = "CUDA"
    ONNX = "ONNX"


def vendor_to_backend(vendor: str | None) -> Backend:
    return Backend.CUDA if str(vendor or "").upper() == "NVIDIA" else Backend.ONNX


def normalize_backend(value: object, default: Backend | None = None) -> Backend | None:
    if isinstance(value, Backend):
        return value

    raw = str(value or "").strip().upper()
    if raw in ("CUDA", "BACKEND.CUDA", "NVIDIA"):
        return Backend.CUDA
    if raw in ("ONNX", "BACKEND.ONNX", "AMD", "CPU", "DIRECTML"):
        return Backend.ONNX
    return default
