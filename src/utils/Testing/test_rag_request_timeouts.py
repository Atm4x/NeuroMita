from concurrent.futures import Future
from types import SimpleNamespace

import pytest

from handlers.ai_engine import rag_client
from managers.rag.request_timeouts import embedding_timeout, reranker_timeout
from managers.settings_manager import SettingsManager


@pytest.fixture
def timeout_settings(monkeypatch):
    values = {"RAG_EMBED_TIMEOUT_SEC": 300, "RAG_RERANK_TIMEOUT_SEC": 600}
    monkeypatch.setattr(SettingsManager, "get", staticmethod(lambda key, default=None: values.get(key, default)))
    return values


@pytest.fixture
def engine_calls(monkeypatch):
    calls = []

    class Response(Future):
        def result(self, timeout=None):
            calls[-1]["wait_timeout"] = timeout
            return super().result(timeout)

    def call(service, method, payload, *, timeout=None):
        calls.append({"method": method, "payload": payload, "worker_timeout": timeout})
        future = Response()
        future.set_result([[1.0, 0.0]] if method == "get_embeddings" else {})
        return future

    monkeypatch.setattr(rag_client, "get_engine", lambda: SimpleNamespace(call=call))
    return calls


def test_fallback_and_worker_share_configured_budget(timeout_settings, engine_calls):
    from handlers.embedding_providers.base import EmbeddingRequest
    from handlers.embedding_providers.local_provider import LocalEmbeddingProvider

    request = EmbeddingRequest(texts=["фраза игрока"], model="owner/model")
    assert LocalEmbeddingProvider().embed(request) == [[1.0, 0.0]]
    assert engine_calls[-1]["wait_timeout"] == engine_calls[-1]["worker_timeout"] == 300
    timeout_settings["RAG_EMBED_TIMEOUT_SEC"] = 480
    rag_client.get_embeddings(["фраза Миты"], model_name="owner/model")
    assert engine_calls[-1]["wait_timeout"] == engine_calls[-1]["worker_timeout"] == 480


def test_controller_uses_same_setting_for_hot_requests(timeout_settings, monkeypatch):
    import controllers.embedding_controller as module

    controller = object.__new__(module.EmbeddingController)
    controller._provider_name = lambda: "local"
    controller._ensure_local_backend = lambda: True
    monkeypatch.setattr(module, "resolve_model_settings", lambda: {"hf_name": "owner/model", "query_prefix": ""})
    calls = []
    monkeypatch.setattr(module, "rag_get_embeddings", lambda texts, **kwargs: calls.append(kwargs) or [[1.0, 0.0]])
    controller.embed_one("query")
    controller.embed_many(["query"])
    controller.embed_many(["query"], priority="bulk")
    assert [call["timeout_sec"] for call in calls] == [300, 300, None]


def test_bulk_batches_retain_longer_budget(timeout_settings, engine_calls):
    rag_client.get_embeddings(["text"] * 32, model_name="owner/model", priority="bulk")
    assert engine_calls[-1]["worker_timeout"] == 640
    rag_client.get_embeddings(["text"], model_name="owner/model", timeout_sec=15)
    assert engine_calls[-1]["worker_timeout"] == engine_calls[-1]["wait_timeout"] == 15


def test_rerank_budget_reaches_worker_above_old_300_second_limit(timeout_settings, engine_calls):
    kwargs = dict(model_name="owner/reranker", query="query", candidates=[{}] * 75,
                  top_k=75, alpha=1, early_exit_score=1.1, total_candidates=75)
    rag_client.rerank_candidates(**kwargs)
    assert engine_calls[-1]["worker_timeout"] == engine_calls[-1]["wait_timeout"] == 600
    timeout_settings["RAG_RERANK_TIMEOUT_SEC"] = 0
    rag_client.rerank_candidates(**kwargs)
    assert engine_calls[-1]["worker_timeout"] == engine_calls[-1]["wait_timeout"] == 750


@pytest.mark.parametrize("value,expected", [
    (None, 60), ("bad", 60), (-1, 60), (0, 60), (float("nan"), 60),
    (float("inf"), 60), ("180", 180), (99999, 3600), (0.5, 1),
])
def test_invalid_and_extreme_settings_are_bounded(timeout_settings, value, expected):
    timeout_settings["RAG_EMBED_TIMEOUT_SEC"] = value
    assert embedding_timeout() == expected
    timeout_settings["RAG_RERANK_TIMEOUT_SEC"] = value
    assert 1 <= reranker_timeout(10) <= 3600


def test_default_and_auto_values(monkeypatch):
    monkeypatch.setattr(SettingsManager, "get", staticmethod(lambda key, default=None: default))
    assert embedding_timeout() == 60
    assert reranker_timeout(1) == 30
    assert reranker_timeout(75) == 750
    assert reranker_timeout(1000) == 3600
