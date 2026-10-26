from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from handlers.ai_engine.rag_onnx import OnnxEmbeddingHandler, OnnxTextModel
from handlers.ai_engine.rag_runtime import WorkerCrossEncoderReranker
from managers.rag import install_spec, onnx_artifacts
from managers.settings_manager import SettingsManager


@pytest.fixture
def onnx_settings(monkeypatch, tmp_path):
    values = {"RAG_LOCAL_BACKEND": "onnx", "RAG_ONNX_DEVICE": "dml", "RAG_CE_INT8": True}
    monkeypatch.setattr(SettingsManager, "get", staticmethod(lambda key, default=None: values.get(key, default)))
    monkeypatch.setenv("NEUROMITA_CHECKPOINTS_DIR", str(tmp_path / "Модели с пробелами"))
    monkeypatch.setattr(install_spec, "check_requirements", lambda *args, **kwargs: {
        "ok": True, "details": [], "missing_required": [],
    })
    return values


def _artifact(kind, model, config=None):
    root = onnx_artifacts.artifact_dir(kind, model)
    root.mkdir(parents=True)
    (root / "model.onnx").write_bytes(b"test graph")
    (root / "config.json").write_text(json.dumps(config or {"hidden_size": 2, "model_type": "qwen3"}))
    (root / "tokenizer_config.json").write_text("{}")
    (root / "weights.data").write_bytes(b"external weights")
    (root / onnx_artifacts.MANIFEST).write_text(json.dumps({
        "version": onnx_artifacts.EXPORT_VERSION, "kind": kind, "model": model,
        "files": {path.name: path.stat().st_size for path in root.iterdir()},
    }), encoding="utf-8")
    return root


def test_onnx_card_requires_export_even_with_torch_cache(onnx_settings):
    model = "Qwen/Qwen3-Embedding-0.6B"
    from pathlib import Path

    Path(install_spec._cache_marker_path(model)).mkdir(parents=True)
    status = install_spec.model_install_status("embeddings", model, ctx={"gpu_vendor": "AMD"})
    assert status["ok"] is False
    assert status["required_backend"] == "onnx"
    assert status["onnx_exports"] == [("embeddings", model)]
    _artifact("embeddings", model)
    assert install_spec.model_install_status("embeddings", model)["ok"] is True


@pytest.mark.parametrize("kind", ["embeddings", "reranker"])
def test_install_uses_managed_onnx_without_cpu_runtime_extra(onnx_settings, kind, tmp_path):
    model = "Qwen/Qwen3-Embedding-0.6B" if kind == "embeddings" else "Qwen/Qwen3-Reranker-0.6B"
    plan = install_spec.build_model_install_plan(kind, model, ctx={"libs_dir": str(tmp_path / "overlay")})
    assert plan.required_backend.value == "onnx"
    assert plan.backend_context["libs_dir"] == str(tmp_path / "overlay")
    specs = [package for action in plan.actions for package in (action.packages or [])]
    assert "optimum-onnx>=0.1,<1" in specs
    assert not any("onnxruntime" in spec or "bitsandbytes" in spec for spec in specs)
    assert any(action.description == f"Exporting ONNX model: {model}" for action in plan.actions)
    onnx_settings["RAG_LOCAL_BACKEND"] = "torch"
    _artifact(kind, model)
    assert plan.actions[-1].fn(ctx={}) is True


def test_export_manifest_checks_external_weights(onnx_settings):
    root = _artifact("embeddings", "owner/model")
    assert onnx_artifacts.artifact_ready("embeddings", "owner/model")
    (root / "weights.data").unlink()
    assert not onnx_artifacts.artifact_ready("embeddings", "owner/model")


def test_export_recognises_directml_distribution(monkeypatch):
    import_utils = SimpleNamespace(_onnxruntime_available=False)
    utils_package = SimpleNamespace(import_utils=import_utils)
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(__version__="1.24.4"))
    monkeypatch.setitem(sys.modules, "optimum", SimpleNamespace(utils=utils_package))
    monkeypatch.setitem(sys.modules, "optimum.utils", utils_package)
    monkeypatch.setitem(sys.modules, "optimum.utils.import_utils", import_utils)

    onnx_artifacts._enable_directml_runtime_detection()

    assert import_utils._onnxruntime_available is True


def test_export_keeps_runtime_flag_when_module_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    modules = SimpleNamespace(_onnxruntime_available=False)
    monkeypatch.setitem(sys.modules, "optimum.utils.import_utils", modules)

    onnx_artifacts._enable_directml_runtime_detection()

    assert modules._onnxruntime_available is False


def _fake_runtime(monkeypatch, providers):
    sessions = []

    class Session:
        def __init__(self, path, sess_options, providers):
            self.path, self.options, self.providers = path, sess_options, providers
            self.inputs = None
            sessions.append(self)

        def get_providers(self):
            return [entry[0] if isinstance(entry, tuple) else entry for entry in self.providers]

        def get_inputs(self):
            return [SimpleNamespace(name=name, type="tensor(int64)")
                    for name in ("input_ids", "attention_mask", "position_ids")]

        def run(self, names, inputs):
            self.inputs = inputs
            ids = inputs["input_ids"]
            return [np.stack([ids, ids + 1], axis=-1).astype(np.float32)]

    class Tokenizer:
        pad_token_id = 0
        eos_token_id = 1

        def __call__(self, texts, **kwargs):
            return {"input_ids": np.tile([0, 2, 3], (len(texts), 1)),
                    "attention_mask": np.tile([0, 1, 1], (len(texts), 1))}

    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(
        get_available_providers=lambda: providers,
        SessionOptions=SimpleNamespace,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        InferenceSession=Session,
    ))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *args, **kwargs: Tokenizer()),
    ))
    return sessions


def test_directml_session_and_left_padding_pooling(onnx_settings, monkeypatch):
    _artifact("embeddings", "owner/model")
    sessions = _fake_runtime(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    handler = OnnxEmbeddingHandler("owner/model", "query: ", "dml")
    vectors = handler.get_embeddings(["фраза", "", "другая фраза"], batch_size=16)
    assert vectors[1] is None
    np.testing.assert_allclose(vectors[0], [0.6, 0.8])
    assert sessions[0].options.enable_mem_pattern is False
    assert sessions[0].options.execution_mode == "sequential"
    assert sessions[0].providers[0] == ("DmlExecutionProvider", {"device_id": 0})
    np.testing.assert_array_equal(sessions[0].inputs["position_ids"], [[0, 0, 1]])


def test_explicit_directml_never_silently_uses_cpu(onnx_settings, monkeypatch):
    _artifact("embeddings", "owner/model")
    sessions = _fake_runtime(monkeypatch, ["CPUExecutionProvider"])
    with pytest.raises(RuntimeError, match="DirectML"):
        OnnxTextModel("embeddings", "owner/model", "dml")
    assert not sessions
    assert OnnxTextModel("embeddings", "owner/model", "auto").provider == "CPUExecutionProvider"


def test_worker_routes_onnx_without_loading_torch_handler(monkeypatch):
    from handlers.ai_engine.services.rag_service import RAGService

    seen = []
    monkeypatch.setattr(install_spec, "ensure_runtime_ready", lambda target, **kwargs: seen.append(kwargs))
    monkeypatch.setattr(OnnxEmbeddingHandler, "shared", lambda *args: SimpleNamespace(
        get_embeddings=lambda texts, **kwargs: [[1.0, 0.0] for _ in texts],
    ))
    result = asyncio.run(RAGService(emit_event=lambda *args: None).handle("get_embeddings", {
        "texts": ["фраза"], "model_name": "owner/model", "local_backend": "onnx", "onnx_device": "dml",
    }))
    assert result == [[1.0, 0.0]]
    assert seen == [{"ctx": {"rag_backend": "onnx"}}]


def test_headless_engine_preserves_selected_backend(monkeypatch):
    from handlers.ai_engine.inprocess_engine import InProcessAIEngine

    seen = []
    engine = InProcessAIEngine()
    engine._rag = SimpleNamespace(_get_embeddings_sync=lambda *args: seen.append(args) or [[1.0]])
    assert engine.call("rag", "get_embeddings", {
        "texts": ["query"], "model_name": "owner/model", "local_backend": "onnx", "onnx_device": "cpu",
    }).result() == [[1.0]]
    assert seen[0][-2:] == ("onnx", "cpu")


@pytest.mark.parametrize("lm", [False, True])
def test_onnx_reranker_scoring_preserves_public_results(lm):
    reranker = WorkerCrossEncoderReranker("Qwen/Qwen3-Reranker-0.6B" if lm else "owner/reranker", "onnx", "cpu")
    reranker._tokenizer = lambda *args, **kwargs: {}
    logits = np.array([[[1000.0, 1002.0]]]) if lm else np.array([[0.75]])
    reranker._model = SimpleNamespace(predict=lambda *args: logits)
    reranker._token_false_id, reranker._token_true_id = 0, 1
    result = reranker.rerank_payload("query", [{"id": 1, "source": "memory", "content": "text"}],
                                    top_k=1, alpha=1.0, early_exit_score=1.1, total_candidates=1)
    expected = 1 / (1 + np.exp(-2)) if lm else 0.75
    assert result["updates"][0]["score"] == pytest.approx(expected)
    assert result["loaded"] is True


@pytest.mark.parametrize("kind,model,task", [
    ("embeddings", "Qwen/Qwen3-Embedding-0.6B", "feature-extraction"),
    ("reranker", "Qwen/Qwen3-Reranker-0.6B", "text-generation"),
    ("reranker", "owner/cross-encoder", "text-classification"),
])
def test_export_is_atomic_and_selects_task(onnx_settings, monkeypatch, kind, model, task):
    calls = []

    def export(**kwargs):
        calls.append(kwargs)
        kwargs["output"].mkdir()
        for name in ("model.onnx", "config.json"):
            (kwargs["output"] / name).write_text("{}")

    def save(root):
        (root / "tokenizer_config.json").write_text("{}")

    monkeypatch.setitem(sys.modules, "optimum.exporters.onnx", SimpleNamespace(main_export=export))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=SimpleNamespace(
        from_pretrained=lambda *args, **kwargs: SimpleNamespace(save_pretrained=save),
    )))
    onnx_artifacts.prepare_artifact(kind, model)
    assert calls[0]["task"] == task
    assert calls[0]["device"] == "cpu"
    assert onnx_artifacts.artifact_ready(kind, model)
    onnx_artifacts.prepare_artifact(kind, model)
    assert len(calls) == 1
    (onnx_artifacts.artifact_dir(kind, model) / "model.onnx").unlink()
    onnx_artifacts.prepare_artifact(kind, model)
    assert len(calls) == 2
    assert onnx_artifacts.artifact_ready(kind, model)


def test_real_onnx_cpu_session_in_cyrillic_path(onnx_settings, monkeypatch):
    pytest.importorskip("onnxruntime")
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    root = _artifact("embeddings", "owner/real-graph")
    _fake_runtime(monkeypatch, ["CPUExecutionProvider"])
    monkeypatch.delitem(sys.modules, "onnxruntime")
    table = numpy_helper.from_array(np.array([[0, 1], [1, 2], [2, 3], [3, 4]], dtype=np.float32), "table")
    graph = helper.make_graph(
        [helper.make_node("Gather", ["table", "input_ids"], ["last_hidden_state"], axis=0)],
        "embedding-smoke",
        [helper.make_tensor_value_info(name, TensorProto.INT64, [None, None])
         for name in ("input_ids", "attention_mask", "position_ids")],
        [helper.make_tensor_value_info("last_hidden_state", TensorProto.FLOAT, [None, None, 2])],
        initializer=[table],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
    onnx.save(model, root / "model.onnx")
    manifest = json.loads((root / onnx_artifacts.MANIFEST).read_text())
    manifest["files"]["model.onnx"] = (root / "model.onnx").stat().st_size
    (root / onnx_artifacts.MANIFEST).write_text(json.dumps(manifest))
    handler = OnnxEmbeddingHandler("owner/real-graph", "query: ", "cpu")
    vectors = handler.get_embeddings(["фраза игрока", "фраза Миты"])
    np.testing.assert_allclose(vectors, [[0.6, 0.8], [0.6, 0.8]])


def test_export_action_runs_in_install_subprocess(onnx_settings, monkeypatch, tmp_path):
    overlay = tmp_path / "пакеты"
    exporter = overlay / "optimum" / "exporters" / "onnx"
    exporter.mkdir(parents=True)
    (exporter / "__init__.py").write_text(
        "def main_export(**kwargs):\n"
        "    root = kwargs['output']\n"
        "    root.mkdir()\n"
        "    (root / 'model.onnx').write_bytes(b'graph')\n"
        "    (root / 'config.json').write_text('{}')\n", encoding="utf-8",
    )
    tokenizer = overlay / "transformers"
    tokenizer.mkdir()
    (tokenizer / "__init__.py").write_text(
        "class AutoTokenizer:\n"
        "    @classmethod\n"
        "    def from_pretrained(cls, *args, **kwargs): return cls()\n"
        "    def save_pretrained(self, root):\n"
        "        (root / 'tokenizer_config.json').write_text('{}')\n", encoding="utf-8",
    )
    active = []
    installer = SimpleNamespace(
        script_path=sys.executable,
        _set_active_process=lambda process, killer: active.append(process),
        _clear_active_process=lambda process: active.remove(process),
        _terminate_process=lambda process, reason: process.kill(),
    )
    action = install_spec._snapshot_download_action(
        "owner/model", description="Export", progress=65, onnx_kind="embeddings",
    )
    assert action.fn(pip_installer=installer, ctx={"python_paths": [str(overlay)], "timeout_sec": 30})
    assert not active
    assert onnx_artifacts.artifact_ready("embeddings", "owner/model")


def test_failed_export_preserves_previous_files(onnx_settings, monkeypatch):
    root = _artifact("embeddings", "owner/model")
    original = (root / "model.onnx").read_bytes()
    monkeypatch.setattr(onnx_artifacts, "artifact_ready", lambda *args: False)

    def fail_export(**kwargs):
        kwargs["output"].mkdir()
        (kwargs["output"] / "model.onnx").write_bytes(b"partial export")
        raise RuntimeError("export failed")

    monkeypatch.setitem(sys.modules, "optimum.exporters.onnx", SimpleNamespace(main_export=fail_export))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=object))
    with pytest.raises(RuntimeError, match="export failed"):
        onnx_artifacts.prepare_artifact("embeddings", "owner/model")
    assert (root / "model.onnx").read_bytes() == original
    assert list(root.parent.iterdir()) == [root]
