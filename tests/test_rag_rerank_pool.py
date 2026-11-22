from unittest.mock import patch

from managers.rag.pipeline.cross_encoder import CrossEncoderReranker
from managers.rag.pipeline.types import Candidate


def test_unscored_candidates_cannot_outrank_the_reranked_pool():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.model_name = "fixture"
    reranker.runtime_epoch = lambda: 1
    reranker._ensure_runtime = lambda: True
    reranker._set_state = lambda *a, **kw: None
    candidates = [Candidate("memory", i, content="record", score=score)
                  for i, score in enumerate((0.9, 0.8, 0.7), 1)]
    response = {"updates": [{"index": 0, "score": 0.01, "cross_encoder": 0.01},
                            {"index": 1, "score": 0.6, "cross_encoder": 0.8}], "loaded": True}
    with patch("managers.rag.pipeline.cross_encoder.rerank_candidates", return_value=response):
        reranker.rerank("Core", candidates, top_k=2)
    assert [row.id for row in candidates] == [1, 2]
    assert candidates[0].features["cross_encoder"] == 0.01


def test_failed_reranker_preserves_linear_fallback():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.model_name = "fixture"
    reranker.runtime_epoch = lambda: 1
    reranker._ensure_runtime = lambda: True
    reranker._set_state = lambda *a, **kw: None
    candidates = [Candidate("memory", 1, content="record", score=0.9)]
    with patch("managers.rag.pipeline.cross_encoder.rerank_candidates", return_value={"updates": []}):
        reranker.rerank("Core", candidates)
    assert candidates[0].score == 0.9
