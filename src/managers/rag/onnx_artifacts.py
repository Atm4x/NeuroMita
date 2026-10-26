from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from core.app_paths import checkpoints_dir


EXPORT_VERSION = 1
MANIFEST = "neuromita_onnx.json"


def artifact_dir(kind: str, model_name: str) -> Path:
    if kind not in {"embeddings", "reranker"}:
        raise ValueError(f"Unknown RAG ONNX model kind: {kind}")
    identity = json.dumps([EXPORT_VERSION, kind, str(model_name)], ensure_ascii=False)
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return checkpoints_dir() / "rag_onnx" / kind / key


def artifact_ready(kind: str, model_name: str) -> bool:
    root = artifact_dir(kind, model_name)
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in {
            "version": EXPORT_VERSION, "kind": kind, "model": str(model_name),
        }.items()):
            return False
        files = manifest.get("files") or {}
        if not isinstance(files, dict) or not {"model.onnx", "config.json", "tokenizer_config.json"}.issubset(files):
            return False
        return all(
            (root / name).is_relative_to(root) and ".." not in Path(name).parts
            and (root / name).stat().st_size == size
            for name, size in files.items()
        )
    except (OSError, ValueError):
        return False


def _enable_directml_runtime_detection() -> None:
    """Teach optimum that the DirectML runtime is installed.

    ``optimum`` looks for distribution metadata named ``onnxruntime`` (or a
    short list of variants) and does not recognise ``onnxruntime-directml``.
    The module itself is importable, so verify it and replace that false
    negative before the exporter validates the graph it just produced.
    """
    try:
        import onnxruntime  # noqa: F401
        from optimum.utils import import_utils
    except Exception:
        return
    import_utils._onnxruntime_available = True


def prepare_artifact(kind: str, model_name: str) -> None:
    """Run only in the installer's disposable subprocess, never on a query."""
    if artifact_ready(kind, model_name):
        return
    _enable_directml_runtime_detection()
    from optimum.exporters.onnx import main_export
    from transformers import AutoTokenizer

    from managers.rag.local_backend import is_lm_reranker

    output = artifact_dir(kind, model_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    task = "feature-extraction" if kind == "embeddings" else (
        "text-generation" if is_lm_reranker(model_name) else "text-classification"
    )
    token = os.environ.get("HF_TOKEN") or None
    with tempfile.TemporaryDirectory(prefix=".export-", dir=output.parent) as temporary:
        staging = Path(temporary) / "model"
        main_export(
            model_name_or_path=model_name, output=staging, task=task,
            device="cpu", dtype="fp32", opset=17, monolith=True,
            no_post_process=True, cache_dir=str(checkpoints_dir()), token=token,
            trust_remote_code=True,
        )
        AutoTokenizer.from_pretrained(
            model_name, cache_dir=str(checkpoints_dir()), token=token,
            trust_remote_code=True,
        ).save_pretrained(staging)
        required = ("model.onnx", "config.json", "tokenizer_config.json")
        if not all((staging / name).is_file() for name in required):
            raise RuntimeError("RAG ONNX export is missing model, config or tokenizer files")
        (staging / MANIFEST).write_text(json.dumps({
            "version": EXPORT_VERSION, "kind": kind, "model": str(model_name),
            "files": {str(path.relative_to(staging)): path.stat().st_size
                      for path in staging.rglob("*") if path.is_file()},
        }, ensure_ascii=False), encoding="utf-8")
        if output.exists():
            if artifact_ready(kind, model_name):
                return
            allowed_root = checkpoints_dir().resolve()
            previous = Path(temporary) / "previous"
            if not all(path.resolve().is_relative_to(allowed_root) for path in (output, previous, staging)):
                raise RuntimeError("RAG ONNX export paths must stay inside checkpoints")
            output.rename(previous)
            try:
                staging.rename(output)
            except Exception:
                previous.rename(output)
                raise
        else:
            staging.rename(output)
