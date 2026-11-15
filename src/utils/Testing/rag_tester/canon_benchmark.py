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
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))

from DSL.dsl_engine import DslInterpreter
from DSL.path_resolver import LocalPathResolver
from managers.memory_manager import MemoryManager
from rag_tester_core import RagTesterService, SettingsOverride, setup_test_db

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


def memory_hits(results, targets):
    """History IDs inhabit a different namespace from character memory IDs."""
    return [result.get("source") == "memory" and str(result.get("id")) in targets for result in results]


def evaluate(service, cases, mode, *, diagnostics=None, profile_options=None):
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
            overrides = {**OPTIONS, "RAG_KEYWORD_SEARCH": kw, "RAG_USE_FTS": fts, **(profile_options or {})}
            started = time.perf_counter()
            results, _ = service._search_timed(
                cid=cid, query=question, limit=5, threshold=0.4, use_overrides=True, overrides=overrides,
            )
            elapsed = (time.perf_counter() - started) * 1000
            hits = memory_hits(results, targets)
            case_id = f"{number}.{wording}"
            stats["latency"].append(elapsed)
            stats["empty"].append(not results)
            if diagnostics is not None:
                wide, _ = service._search_timed(
                    cid=cid, query=question, limit=100, threshold=0, use_overrides=True, overrides=overrides,
                ) if targets and not any(hits) else ([], {})
                diagnostics.append({
                    "mode": mode, "case": case_id, "target_count": len(targets),
                    "retrieved": [{
                        "source": result.get("source"), "score": result.get("score"), "expected": hit,
                    } for result, hit in zip(results, hits)],
                    "wide_target_ranks": [rank for rank, hit in enumerate(memory_hits(wide, targets), 1) if hit],
                })
            if not pattern:
                if results:
                    negative_nonempty.append(case_id)
                continue
            if not any(hits):
                failures.append(case_id)
            gains = [1 / math.log2(i + 2) for i, hit in enumerate(hits) if hit]
            found = {str(result.get("id")) for result, hit in zip(results, hits) if hit}
            found3 = {str(result.get("id")) for result, hit in zip(results[:3], hits[:3]) if hit}
            stats["recall3"].append(len(found3) / max(len(targets), 1))
            stats["recall5"].append(len(found) / max(len(targets), 1))
            stats["mrr5"].append(next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0))
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
    parser.add_argument("--diagnostics", type=Path, help="Aggregate ranks and sources per case, without result text or IDs")
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
    diagnostics = [] if args.diagnostics else None
    report = {mode: evaluate(service, cases, mode, diagnostics=diagnostics) for mode in MODES}
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.diagnostics:
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
