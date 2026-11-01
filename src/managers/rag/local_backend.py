from __future__ import annotations

from typing import Any


LAST_TOKEN_MODEL_TYPES = frozenset({
    "qwen3", "qwen2", "qwen", "llama", "mistral", "falcon", "gpt2",
    "gpt_neox", "bloom", "opt", "gemma", "gemma2", "phi", "phi3", "stablelm", "mpt", "rwkv",
})


def is_lm_reranker(model_name: str) -> bool:
    return "qwen3-reranker" in str(model_name or "").strip().lower()


def local_backend(ctx: dict[str, Any] | None = None) -> str:
    from managers.settings_manager import SettingsManager

    value = (ctx or {}).get("rag_backend")
    if value is None:
        value = SettingsManager.get("RAG_LOCAL_BACKEND", "torch")
    backend = str(value or "torch").strip().lower()
    if backend not in {"torch", "onnx"}:
        raise ValueError(f"Unknown local RAG backend: {backend}")
    return backend


def onnx_device() -> str:
    from managers.settings_manager import SettingsManager

    device = str(SettingsManager.get("RAG_ONNX_DEVICE", "auto") or "auto").strip().lower()
    if device not in {"auto", "dml", "cpu"}:
        raise ValueError(f"Unknown RAG ONNX device: {device}")
    return device


def request_backend_options() -> dict[str, str]:
    return {"local_backend": local_backend(), "onnx_device": onnx_device()}
