from types import SimpleNamespace

from managers.rag.pipeline.config import RAGConfig
from managers.rag.pipeline.query_builder import QueryBuilder


def test_keyword_tail_disambiguates_followups_without_overriding_specific_question():
    rag = SimpleNamespace(
        character_id="A",
        _build_query_from_recent=lambda query, tail: f"User: A truce near the castle\nUser: {query}",
        recent_query_rows=lambda limit: [],
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


def test_long_intro_does_not_discard_the_topic_at_the_end():
    from managers.rag.rag_utils import fts_build_match_query

    rag = SimpleNamespace(character_id="A", _build_query_from_recent=lambda q, tail: q,
                          recent_query_rows=lambda limit: [])
    cfg = RAGConfig(kw_enabled=True, vector_search_enabled=False, kw_max_terms=8, lemmatization=False)
    query = "Слушай давай попробуем проверить твои воспоминания расскажи пожалуйста немного интересных подробностей про ядро"
    assert "ядро" in QueryBuilder(rag=rag, cfg=cfg).build(query).keywords
    assert '"ядро"' in fts_build_match_query(query, max_terms=8, min_len=3, from_end=True)
