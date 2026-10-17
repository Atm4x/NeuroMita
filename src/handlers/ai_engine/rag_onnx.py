from __future__ import annotations

import json
from threading import Lock

import numpy as np

from main_logger import logger
from managers.rag.onnx_artifacts import artifact_dir, artifact_ready
from managers.rag.local_backend import LAST_TOKEN_MODEL_TYPES


class OnnxTextModel:
    def __init__(self, kind: str, model_name: str, device: str = "auto") -> None:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        if device not in {"auto", "dml", "cpu"}:
            raise ValueError(f"Unknown RAG ONNX device: {device}")
        if not artifact_ready(kind, model_name):
            raise RuntimeError(f"Install the ONNX export for {model_name} through AI Hub first")
        root = artifact_dir(kind, model_name)
        available = ort.get_available_providers()
        use_dml = device != "cpu" and "DmlExecutionProvider" in available
        if device == "dml" and not use_dml:
            raise RuntimeError("RAG requested DirectML, but DmlExecutionProvider is unavailable")
        self.provider = "DmlExecutionProvider" if use_dml else "CPUExecutionProvider"
        options = ort.SessionOptions()
        if use_dml:
            options.enable_mem_pattern = False
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            providers = [(self.provider, {"device_id": 0}), "CPUExecutionProvider"]
        else:
            providers = [self.provider]
            if device == "auto":
                logger.warning("[RAG][ONNX] DirectML unavailable; using CPUExecutionProvider")
        self.session = ort.InferenceSession(str(root / "model.onnx"), sess_options=options, providers=providers)
        if use_dml and self.provider not in self.session.get_providers():
            raise RuntimeError("RAG ONNX session failed to activate DirectML")
        self.tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=True)
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        self._lock = Lock()
        logger.info(f"[RAG][ONNX] Loaded '{model_name}' ({kind}); provider={self.provider}; path={root}")

    def predict(self, tokens: dict, output_name: str) -> np.ndarray:
        values = dict(tokens)
        mask = np.asarray(values["attention_mask"])
        values["position_ids"] = np.maximum(mask.cumsum(-1) - 1, 0)
        values.setdefault("token_type_ids", np.zeros_like(mask))
        dtypes = {"tensor(int64)": np.int64, "tensor(int32)": np.int32, "tensor(float)": np.float32}
        inputs = {}
        for field in self.session.get_inputs():
            if field.name not in values:
                raise RuntimeError(f"Unsupported RAG ONNX input: {field.name}")
            inputs[field.name] = np.asarray(values[field.name], dtype=dtypes.get(field.type))
        with self._lock:
            return self.session.run([output_name], inputs)[0]


class OnnxEmbeddingHandler:
    _shared = None
    _shared_lock = Lock()

    @classmethod
    def shared(cls, model_name: str, query_prefix: str = "", device: str = "auto"):
        key = (model_name, query_prefix, device)
        with cls._shared_lock:
            if cls._shared is None or cls._shared[0] != key:
                cls._shared = (key, cls(model_name, query_prefix, device))
            return cls._shared[1]

    @classmethod
    def clear(cls) -> None:
        with cls._shared_lock:
            cls._shared = None

    def __init__(self, model_name: str, query_prefix: str, device: str) -> None:
        self.runtime = OnnxTextModel("embeddings", model_name, device)
        self.query_prefix = query_prefix or "query: "
        self.hidden_size = int(self.runtime.config["hidden_size"])
        model_type = self.runtime.config.get("model_type", "").lower()
        self._last_token = model_type in LAST_TOKEN_MODEL_TYPES

    def get_embeddings(self, texts: list[str], prefix: str = "", batch_size: int = 32) -> list:
        results = [None] * len(texts)
        prefix = prefix or self.query_prefix
        valid = [(i, prefix + str(text)) for i, text in enumerate(texts) if text is not None and str(text).strip()]
        size = 1 if self.runtime.provider == "DmlExecutionProvider" else max(1, int(batch_size))
        for start in range(0, len(valid), size):
            chunk = valid[start:start + size]
            tokens = self.runtime.tokenizer(
                [text for _, text in chunk], padding=True, truncation=True,
                return_tensors="np", max_length=512,
            )
            hidden = self.runtime.predict(tokens, "last_hidden_state")
            if self._last_token:
                mask = np.asarray(tokens["attention_mask"])
                positions = np.where(mask != 0, np.arange(mask.shape[1]), -1).max(axis=1)
                vectors = hidden[np.arange(len(chunk)), positions]
            else:
                vectors = hidden[:, 0]
            vectors = vectors.astype(np.float32)
            vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
            for (index, _), vector in zip(chunk, vectors):
                results[index] = vector
        return results
