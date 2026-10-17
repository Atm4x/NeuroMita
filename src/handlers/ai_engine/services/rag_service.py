from __future__ import annotations

import asyncio
from typing import Any, Callable

from handlers.ai_engine.gpu_scheduler import Priority, get_scheduler


class RAGService:
    def __init__(self, *, emit_event: Callable[[str, Any], None]):
        self.emit_event = emit_event

    async def shutdown(self):
        await asyncio.to_thread(self._shutdown_sync)

    async def handle(self, method: str, payload: dict):
        m = str(method or "").strip().lower()
        backend = str(payload.get("local_backend") or "torch")
        device = str(payload.get("onnx_device") or "auto")

        if m == "ping":
            return True

        if m == "warmup_embeddings":
            model_name = str(payload.get("model_name") or "").strip()
            query_prefix = str(payload.get("query_prefix") or "")
            return await get_scheduler().run(
                Priority.BULK, self._warmup_embeddings_sync, model_name, query_prefix, backend, device
            )

        if m == "warmup_reranker":
            model_name = str(payload.get("model_name") or "").strip()
            return await get_scheduler().run(
                Priority.BULK,
                self._warmup_reranker_sync,
                model_name,
                backend,
                device,
            )

        if m == "get_embeddings":
            texts = payload.get("texts") or []
            model_name = str(payload.get("model_name") or "").strip()
            query_prefix = str(payload.get("query_prefix") or "")
            prefix = payload.get("prefix")
            prefix = query_prefix if prefix is None else str(prefix or "")
            batch_size = payload.get("batch_size")
            # Эмбеддинг запроса пользователя обгоняет фоновую индексацию.
            priority = Priority.parse(payload.get("priority"), default=Priority.HOT)
            return await get_scheduler().run(
                priority,
                self._get_embeddings_sync,
                list(texts or []),
                model_name,
                query_prefix,
                prefix,
                batch_size,
                backend,
                device,
            )

        if m == "rerank":
            model_name = str(payload.get("model_name") or "").strip()
            query = str(payload.get("query") or "")
            candidates = list(payload.get("candidates") or [])
            top_k = int(payload.get("top_k") or 0)
            alpha = float(payload.get("alpha") or 0.0)
            early_exit_score = float(payload.get("early_exit_score") or 0.0)
            total_candidates = int(payload.get("total_candidates") or len(candidates))

            return await get_scheduler().run(
                Priority.RERANK,
                self._rerank_sync,
                model_name,
                query,
                candidates,
                top_k,
                alpha,
                early_exit_score,
                total_candidates,
                backend,
                device,
            )

        if m == "get_reranker_status":
            model_name = str(payload.get("model_name") or "").strip()
            return await asyncio.to_thread(self._reranker_status_sync, model_name, backend, device)

        raise RuntimeError(f"Unknown rag method: {method}")


    @staticmethod
    def _rerank_sync(
        model_name: str,
        query: str,
        candidates: list[Any],
        top_k: int,
        alpha: float,
        early_exit_score: float,
        total_candidates: int,
        backend: str = "torch",
        device: str = "auto",
    ):
        from handlers.ai_engine.rag_runtime import WorkerCrossEncoderReranker

        reranker = WorkerCrossEncoderReranker.get(model_name, backend, device)
        return reranker.rerank_payload(
            query,
            candidates,
            top_k=top_k,
            alpha=alpha,
            early_exit_score=early_exit_score,
            total_candidates=total_candidates,
        )

    @staticmethod
    def _reranker_status_sync(model_name: str, backend: str = "torch", device: str = "auto"):
        from handlers.ai_engine.rag_runtime import WorkerCrossEncoderReranker

        return WorkerCrossEncoderReranker.status(model_name, backend, device)

    def _embedding_handler(self, model_name: str, query_prefix: str, backend: str, device: str):
        from managers.rag.install_spec import TARGET_EMBEDDINGS, ensure_runtime_ready

        ensure_runtime_ready(TARGET_EMBEDDINGS, ctx={"rag_backend": backend})
        if backend == "onnx":
            from handlers.ai_engine.rag_onnx import OnnxEmbeddingHandler

            return OnnxEmbeddingHandler.shared(model_name, query_prefix, device)
        if backend != "torch":
            raise ValueError(f"Unknown local RAG backend: {backend}")
        from handlers.embedding_handler import EmbeddingModelHandler

        return EmbeddingModelHandler.shared(
            model_name=model_name,
            query_prefix=query_prefix,
        )

    def _warmup_embeddings_sync(self, model_name: str, query_prefix: str, backend: str = "torch", device: str = "auto") -> bool:
        self._embedding_handler(model_name, query_prefix, backend, device)
        return True

    @staticmethod
    def _warmup_reranker_sync(model_name: str, backend: str = "torch", device: str = "auto") -> bool:
        from handlers.ai_engine.rag_runtime import WorkerCrossEncoderReranker

        if not model_name:
            raise ValueError("RAG reranker model name is required")
        return bool(WorkerCrossEncoderReranker.get(model_name, backend, device)._ensure_loaded())

    def _get_embeddings_sync(
        self,
        texts: list[str],
        model_name: str,
        query_prefix: str,
        prefix: str,
        batch_size,
        backend: str = "torch",
        device: str = "auto",
    ):
        handler = self._embedding_handler(model_name, query_prefix, backend, device)
        bs = 32
        try:
            if batch_size is not None:
                bs = max(1, int(batch_size))
        except Exception:
            bs = 32
        return handler.get_embeddings(list(texts or []), prefix=str(prefix or ""), batch_size=bs)

    def _shutdown_sync(self) -> None:
        from handlers.ai_engine.rag_runtime import shutdown_rag_runtime

        shutdown_rag_runtime()
