import datetime
from types import SimpleNamespace

from managers.rag.pipeline.config import RAGConfig
from managers.rag.pipeline.enrichers.common import TimeEnricher
from managers.rag.pipeline.retrievers.graph import GraphRetriever
from managers.rag.pipeline.reranker import LinearReranker
from managers.rag.pipeline.types import QueryState


def store(name="cappie", confidence=1):
    return SimpleNamespace(
        get_all_entities=lambda **_: [{"name": name}],
        query_by_entities=lambda _: [{
            "subject": name, "predicate": "reported_portal", "object": "portal",
            "confidence": confidence, "is_protected": True,
            "created_at": datetime.datetime.now().isoformat(),
        }],
    )


def test_graph_alias_and_evidence_survive_linear_ranking_without_ingestion_recency():
    cfg = RAGConfig()
    cfg.noise_max = 0
    query = QueryState("A", "Кепочка", "", None, ["кепочк"], datetime.datetime.now())
    candidates = GraphRetriever(graph_store=store(), cfg=cfg).retrieve(query)
    assert candidates
    TimeEnricher(rag=None, cfg=cfg).enrich(query, candidates)
    assert candidates[0].features["time"] == 0
    LinearReranker(cfg=cfg).score_all(candidates)
    assert candidates[0].score > 0


def test_graph_matches_inflected_names_without_prefix_collisions():
    cfg = RAGConfig()
    query = QueryState("A", "Поговорим с Кепочкой", "", None, ["кепочк"], datetime.datetime.now())
    assert GraphRetriever(graph_store=store("кепочка"), cfg=cfg).retrieve(query)
    assert not GraphRetriever(graph_store=store("кепочкин"), cfg=cfg)._match_entities(["кеп"], [])
    assert not GraphRetriever(graph_store=store(confidence=0), cfg=cfg).retrieve(query)
