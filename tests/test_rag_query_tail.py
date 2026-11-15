from types import SimpleNamespace

from managers.rag.pipeline.config import RAGConfig
from managers.rag.pipeline.query_builder import QueryBuilder


def test_keyword_tail_disambiguates_followups_without_overriding_specific_question():
    rag = SimpleNamespace(
        character_id="A",
        _build_query_from_recent=lambda query, tail: f"User: A truce near the castle\nUser: {query}",
    )
    cfg = RAGConfig()
    cfg.kw_enabled = True
    cfg.vector_search_enabled = False
    builder = QueryBuilder(rag=rag, cfg=cfg)
    short = builder.build("What terms?")
    assert "truce" in short.keywords
    explicit = builder.build("Does restoring a backup alter world history?")
    assert {"restoring", "backup", "history"}.issubset(explicit.keywords)
    assert "truce" not in explicit.keywords
