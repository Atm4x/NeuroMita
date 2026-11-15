"""Measure lexical retrieval against the actual bundled lore and an optional world copy.

Run with an empty scratch --db, or with a disposable SQLite backup at --db
and --existing. Prints aggregate results; private result text stays out of JSON.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))

from DSL.dsl_engine import DslInterpreter
from DSL.path_resolver import LocalPathResolver
from managers.memory_manager import MemoryManager
from rag_tester_core import RagTesterService, SettingsOverride, TestSuite, setup_test_db

PROMPTS = ROOT / "extra" / "Prompts"
MODES = {"keyword": (True, False), "fts": (False, True), "combined": (True, True)}
OPTIONS = {"RAG_MEMORY_MODE": "all", "RAG_SEARCH_MEMORY": True, "RAG_SEARCH_HISTORY": True,
           "RAG_USE_RRF": False, "RAG_NOISE_MAX": 0, "RAG_DETAILED_LOGS": False}


def seed_character(cid):
    memory = MemoryManager(cid)
    char = SimpleNamespace(variables={}, memory_system=memory, character_id=cid)
    dsl = DslInterpreter(char, LocalPathResolver(str(PROMPTS), str(PROMPTS)))
    dsl.process_file("Common/world_knowledge.script")
    dsl.process_file(f"Common/CharacterSeeds/{cid}.script")


def evaluate(service, cases, mode):
    kw, fts = MODES[mode]
    stats = defaultdict(list)
    failures = []
    negative_nonempty = []
    for number, (cid, query, variant, pattern) in enumerate(cases, 1):
        with service.db.connection() as conn:
            rows = conn.execute(
                "SELECT eternal_id,content FROM memories WHERE character_id=? "
                "AND type='seed_lore' AND is_deleted=0", (cid,),
            ).fetchall()
        needles = pattern.casefold().split("|") if pattern else []
        targets = {str(eid) for eid, content in rows if any(s in content.casefold() for s in needles)}
        for wording, question in enumerate((query, variant), 1):
            batch = service.run_batch(
                TestSuite.from_json(json.dumps({
                    "character_id": cid, "cases": [{"query": question, "expected_ids": sorted(targets)}],
                })), limit=5, threshold=0.4, use_overrides=True,
                overrides={**OPTIONS, "RAG_KEYWORD_SEARCH": kw, "RAG_USE_FTS": fts},
            )
            result = batch.results[0]
            ids = result.retrieved_ids
            case_id = f"{number}.{wording}"
            stats["latency"].append(result.elapsed_ms)
            stats["empty"].append(not ids)
            if not pattern:
                if ids:
                    negative_nonempty.append(case_id)
                continue
            if not targets or not set(ids) & targets:
                failures.append(case_id)
            gains = [1 / math.log2(i + 2) for i, eid in enumerate(ids) if eid in targets]
            stats["recall3"].append(len(set(ids[:3]) & targets) / max(len(targets), 1))
            stats["recall5"].append(len(set(ids) & targets) / max(len(targets), 1))
            stats["mrr5"].append(result.reciprocal_rank)
            stats["ndcg5"].append(sum(gains) / (sum(1 / math.log2(i + 2)
                                    for i in range(min(len(targets), 5))) or 1))
            stats["precision5"].append(len(gains) / 5)
    latency = sorted(stats.pop("latency"))
    return {**{k: round(statistics.mean(v), 4) for k, v in stats.items()},
            "p50_ms": round(statistics.median(latency), 2),
            "p95_ms": round(latency[math.ceil(0.95 * len(latency)) - 1], 2),
            "no_hit": failures, "negative_nonempty": negative_nonempty}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--existing", action="store_true", help="Apply seeds to a disposable old-world backup")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.db.exists() != args.existing:
        parser.error("pass a new SQLite path, or --existing with a disposable backup")
    logging.disable(logging.CRITICAL)
    setup_test_db(str(args.db.resolve()))
    service = RagTesterService(lexical_only=True)
    cases = json.loads((HERE / "canon_cases.json").read_text(encoding="utf-8"))
    with SettingsOverride({"RAG_ENABLED": False}):
        for cid in sorted({case[0] for case in cases}):
            seed_character(cid)
    report = {mode: evaluate(service, cases, mode) for mode in MODES}
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
