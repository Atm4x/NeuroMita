from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.rag_continuity import RagContinuity


def environment():
    state = SimpleNamespace(selection=1, epoch=0, head=10)
    runtime = SimpleNamespace(
        assert_current=lambda: None, turn=None, selection=state.selection,
        timeline=SimpleNamespace(branch_id="branch", branch=SimpleNamespace(head_sequence=state.head)),
        repository=SimpleNamespace(context_epoch=lambda *a, **kw: state.epoch),
    )
    conversation = SimpleNamespace(runtime=runtime)
    settings = SimpleNamespace(get={"RAG_ENABLED": True}.get)
    return state, runtime, conversation, settings


def record(identity):
    return {"source": "memory", "id": identity, "content": f"record {identity}",
            "score": 0.9, "features": {"kw": 0.8}}


def character(identity, conversation, search):
    return SimpleNamespace(character_id=identity, db=object(), _conversation=lambda: conversation,
                           recent_query_rows=lambda *a, **kw: [], search_relevant=search)


@pytest.mark.parametrize("enabled", [True, False])
def test_slow_search_does_not_block_another_character(enabled):
    _, _, conversation, _ = environment()
    settings = SimpleNamespace(get={"RAG_ENABLED": True, "RAG_CONTINUITY_ENABLED": enabled}.get)
    cache = RagContinuity()
    entered, release = Event(), Event()

    def slow(*a, **kw):
        entered.set()
        assert release.wait(3), "test did not release search"
        return [record(1)]

    first = character("A", conversation, slow)
    second = character("B", conversation, lambda *a, **kw: [record(2)])
    with ThreadPoolExecutor(max_workers=2) as executor:
        blocked = executor.submit(cache.search, first, "orchid", limit=5, threshold=0.3, settings=settings)
        try:
            assert entered.wait(1)
            independent = executor.submit(cache.search, second, "garden", limit=5, threshold=0.3, settings=settings)
            assert independent.result(timeout=1)[0]["id"] == 2
        finally:
            release.set()
        assert blocked.result(timeout=1)[0]["id"] == 1


def test_late_search_cannot_overwrite_newer_window_of_same_character():
    _, _, conversation, settings = environment()
    cache = RagContinuity()
    entered, release = Event(), Event()

    def search(query, **kw):
        if query == "orchid":
            entered.set()
            assert release.wait(3)
            return [record(1)]
        return [record(2)]

    rag = character("A", conversation, search)
    with ThreadPoolExecutor(max_workers=2) as executor:
        blocked = executor.submit(cache.search, rag, "orchid", limit=5, threshold=0.3, settings=settings)
        try:
            assert entered.wait(1)
            current = executor.submit(cache.search, rag, "garden", limit=5, threshold=0.3, settings=settings)
            assert current.result(timeout=1)[0]["id"] == 2
        finally:
            release.set()
        assert blocked.result(timeout=1)[0]["id"] == 1
    rag.search_relevant = lambda *a, **kw: []
    with patch.object(cache, "_resolve", side_effect=lambda r, c, ref: record(ref.identity)):
        retained = cache.search(rag, "Tell me more", limit=5, threshold=0.3, settings=settings)
    assert [row["id"] for row in retained] == [2]


@pytest.mark.parametrize("transition", ["session", "epoch", "rewind"])
def test_world_change_during_search_discards_the_old_result(transition):
    state, runtime, conversation, settings = environment()
    cache = RagContinuity()
    entered, release = Event(), Event()

    def search(*a, **kw):
        entered.set()
        assert release.wait(3)
        return [record(1)]

    rag = character("A", conversation, search)
    with ThreadPoolExecutor(max_workers=1) as executor:
        blocked = executor.submit(cache.search, rag, "orchid", limit=5, threshold=0.3, settings=settings)
        try:
            assert entered.wait(1)
            if transition == "session":
                runtime.selection += 1
            elif transition == "epoch":
                state.epoch += 1
            else:
                runtime.timeline.branch.head_sequence -= 1
        finally:
            release.set()
        assert blocked.result(timeout=1) == []
    rag.search_relevant = lambda *a, **kw: []
    assert cache.search(rag, "Tell me more", limit=5, threshold=0.3, settings=settings) == []


def test_slow_rehydration_does_not_hold_the_shared_lock():
    _, _, conversation, settings = environment()
    cache = RagContinuity()
    first = character("A", conversation, lambda *a, **kw: [record(1)])
    cache.search(first, "orchid", limit=5, threshold=0.3, settings=settings)
    first.search_relevant = lambda *a, **kw: []
    second = character("B", conversation, lambda *a, **kw: [record(2)])
    entered, release = Event(), Event()

    def resolve(rag, conv, ref):
        entered.set()
        assert release.wait(3)
        return record(ref.identity)

    with patch.object(cache, "_resolve", side_effect=resolve), ThreadPoolExecutor(max_workers=2) as executor:
        blocked = executor.submit(cache.search, first, "Tell me more", limit=5, threshold=0.3, settings=settings)
        try:
            assert entered.wait(1)
            independent = executor.submit(cache.search, second, "garden", limit=5, threshold=0.3, settings=settings)
            assert independent.result(timeout=1)[0]["id"] == 2
        finally:
            release.set()
        assert blocked.result(timeout=1)[0]["retained"]
