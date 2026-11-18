from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.rag.pipeline.config import RAGConfig
from managers.rag.pipeline.enrichers.common import PriorityEnricher, TimeEnricher
from managers.rag.pipeline.reranker import LinearReranker
from managers.rag.pipeline.types import Candidate, QueryState


class SeedLoreRankingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = RAGConfig(K2=0.3, K3=0.5, decay_rate=0.05, noise_max=0.0)
        self.qs = QueryState(
            character_id="test", user_query="memory", expanded_query_text="memory",
            query_vec=None, keywords=[], now_ts=datetime.datetime(2026, 11, 9, 12),
        )

    def test_seed_has_no_time_bonus_but_lived_memory_and_history_do(self):
        timestamp = "09.11.2026 12:00:00"
        seed = Candidate(source="memory", id=1,
                         meta={"type": "seed_lore", "priority": "normal", "date_created": timestamp})
        lived = Candidate(source="memory", id=2,
                          meta={"type": "fact", "priority": "normal", "date_created": timestamp})
        history = Candidate(source="history", id=3, meta={"date": timestamp})
        TimeEnricher(rag=None, cfg=self.cfg).enrich(self.qs, [seed, lived, history])
        self.assertEqual(seed.features["time"], 0.0)
        self.assertAlmostEqual(lived.features["time"], 1.0)
        self.assertAlmostEqual(history.features["time"], 1.0)

    def test_equally_relevant_personal_fact_outranks_recent_seed(self):
        timestamp = "09.11.2026 12:00:00"
        seed = Candidate(source="memory", id=1, features={"sim": 0.8},
                         meta={"type": "seed_lore", "priority": "normal", "date_created": timestamp})
        lived = Candidate(source="memory", id=2, features={"sim": 0.8},
                          meta={"type": "fact", "priority": "normal", "date_created": timestamp})
        TimeEnricher(rag=None, cfg=self.cfg).enrich(self.qs, [seed, lived])
        PriorityEnricher(rag=None, cfg=self.cfg).enrich(self.qs, [seed, lived])
        LinearReranker(cfg=self.cfg).score_all([seed, lived])
        self.assertGreater(lived.score, seed.score)
        self.assertAlmostEqual(lived.score - seed.score, self.cfg.K2)

    def test_high_priority_character_lore_still_has_priority_but_no_recency(self):
        seed = Candidate(source="memory", id=1,
                         meta={"type": "seed_lore", "priority": "high",
                               "date_created": "09.11.2026 12:00:00"})
        TimeEnricher(rag=None, cfg=self.cfg).enrich(self.qs, [seed])
        PriorityEnricher(rag=None, cfg=self.cfg).enrich(self.qs, [seed])
        self.assertEqual(seed.features["time"], 0.0)
        self.assertEqual(seed.features["prio"], 0.25)


if __name__ == "__main__":
    unittest.main()
