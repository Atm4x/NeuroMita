"""Compare lexical, Qwen ONNX, and graph profiles on a disposable world.

Requires the installed local ONNX runtime and model. Never installs models,
contacts a generation provider, or changes the input snapshot.
"""
from __future__ import annotations

import argparse
import gc
from collections import Counter
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[3] / "src")]

from canon_benchmark import evaluate, seed_character
from core.services import services
from handlers.embedding_presets import resolve_full_config
from managers.memory_manager import MemoryManager
from managers.rag.indexing import RagIndexer
from managers.rag.rag_manager import RAGManager
from rag_tester_core import RagTesterService, SettingsOverride, setup_test_db
from services.contracts import EmbeddingService

COMMON = {
    "RAG_ENABLED": True, "RAG_SEARCH_MEMORY": True, "RAG_MEMORY_MODE": "all",
    "RAG_SEARCH_HISTORY": False, "RAG_CROSS_ENCODER_ENABLED": False,
    "RAG_USE_RRF": False, "RAG_NOISE_MAX": 0, "RAG_DETAILED_LOGS": False,
    "RAG_COMBINE_MODE": "union",
    "RAG_EMBED_PRESET_ID": None, "RAG_EMBED_MODEL": "Qwen3-Embedding-0.6B (600M, 2025)",
    "RAG_QUERY_TAIL_MESSAGES": 0, "RAG_QUERY_EMBED_MODE": "concat",
}
PROFILES = {
    "lexical": {"RAG_VECTOR_SEARCH_ENABLED": False, "RAG_SEARCH_GRAPH": False, "RAG_GRAPH_VECTOR_SEARCH": False},
    "vector": {"RAG_VECTOR_SEARCH_ENABLED": True, "RAG_KEYWORD_SEARCH": False, "RAG_USE_FTS": False,
               "RAG_SEARCH_GRAPH": False, "RAG_GRAPH_VECTOR_SEARCH": False},
    "hybrid": {"RAG_VECTOR_SEARCH_ENABLED": True, "RAG_SEARCH_GRAPH": False, "RAG_GRAPH_VECTOR_SEARCH": False},
    "lexical_graph": {"RAG_VECTOR_SEARCH_ENABLED": False, "RAG_SEARCH_GRAPH": True, "RAG_GRAPH_VECTOR_SEARCH": False},
    "hybrid_graph": {"RAG_VECTOR_SEARCH_ENABLED": True, "RAG_SEARCH_GRAPH": True, "RAG_GRAPH_VECTOR_SEARCH": True},
}
TUNING_PROFILES = {
    "lexical_keyword": {**PROFILES["lexical_graph"], "RAG_WEIGHT_KEYWORDS": 0.8},
    "lexical_fts": {**PROFILES["lexical_graph"], "RAG_WEIGHT_LEXICAL": 0.5},
    "hybrid_lexical": {**PROFILES["hybrid_graph"], "RAG_WEIGHT_SIMILARITY": 0.35,
                       "RAG_WEIGHT_KEYWORDS": 0.8, "RAG_WEIGHT_LEXICAL": 0.5},
}


class LocalONNXService(EmbeddingService):
    """Use the application's real embedding handler without starting the desktop app."""
    def __init__(self, device):
        from handlers.ai_engine.rag_onnx import OnnxEmbeddingHandler
        cfg = resolve_full_config()
        self.handler = OnnxEmbeddingHandler(cfg["hf_name"], cfg["query_prefix"], device)
        self.cache = {}
        self.cache_indexing = True
        self.calls = 0

    def readiness(self):
        raise NotImplementedError("Benchmark never polls runtime readiness")

    def embed_one(self, text, prefix=""):
        return self.embed_many([text], prefix=prefix)[0]

    def embed_many(self, texts, prefix="", batch_size=None, priority="hot"):
        if not self.cache_indexing:
            self.calls += len(texts)
            return self.handler.get_embeddings(texts, prefix=prefix, batch_size=1)
        missing = list(dict.fromkeys(text for text in texts if (prefix, text) not in self.cache))
        if missing:
            self.calls += len(missing)
            vectors = self.handler.get_embeddings(missing, prefix=prefix, batch_size=1)
            for text, vector in zip(missing, vectors):
                self.cache[prefix, text] = vector
        return [self.cache[prefix, text] for text in texts]


def prepare_history_cases(tester, conversation, cases):
    labels = set()
    for case in cases:
        label, character, owner, message_id = (
            case[key] for key in ("label", "character", "source_character", "message_id")
        )
        if label in labels or len(case["questions"]) != 2 or not all(case["questions"]):
            raise ValueError(f"Expected a unique label and two formulations: {label}")
        labels.add(label)
        with tester.db.connection() as conn:
            archived = conn.execute(
                "SELECT 1 FROM history WHERE character_id=? AND message_id=? "
                "AND is_active=0 AND coalesce(is_deleted,0)=0",
                (owner, message_id),
            ).fetchone()
        source = conversation.retrieval_history(owner, {message_id}).get(message_id)
        if not archived or not source or not source["content"].strip():
            raise ValueError(f"Target is not archived and visible to source character: {label}")
        visible = bool(conversation.retrieval_history(character, {message_id}))
        if visible != case["visible"] or (visible and character != owner):
            raise ValueError(f"Target does not match annotated visibility or archive owner: {label}")
        case["expected_content"] = source["content"].strip()[:700]
    return cases


def evaluate_history(tester, cases, options):
    from controllers.model_controller import ModelController
    from controllers.prompt_controller import PromptController
    from managers.settings_manager import SettingsManager
    from services.contracts import PromptBuildRequest, RequestPolicy

    model = object.__new__(ModelController)
    model.settings = SettingsManager
    prompt = PromptController()
    prompt._build_system_messages = lambda *_a, **_k: ([], [], [])
    prompt._build_system_state_message = lambda *_a, **_k: {"role": "system", "content": "[test state]"}
    rows = []
    for case in cases:
        cid = case["character"]
        char = SimpleNamespace(char_id=cid, get_variable=lambda key, default=None: default)
        def search(question, limit, threshold):
            return tester._search_timed(cid=cid, query=question, limit=limit, threshold=threshold,
                                        use_overrides=True, overrides=options)[0]

        def target_rank(results):
            return next((i for i, result in enumerate(results, 1)
                         if result["source"] == "history" and result.get("message_id") == case["message_id"]), None)

        for number, question in enumerate(case["questions"], 1):
            results = search(question, 5, 0.4)
            rank = target_rank(results)
            wide_rank = target_rank(search(question, 100, 0)) if rank is None and case["visible"] else None
            with SettingsOverride({**options, "RAG_MAX_RESULTS": 5, "RAG_SIM_THRESHOLD": 0.4,
                                   "RAG_CLIP_MAX_CHARS": 700}):
                block = model.process_rag(cid, "", question) or ""
                built = prompt.build(PromptBuildRequest(
                    character=char, event_type="chat", user_input=question, rag_context=block,
                    policy=RequestPolicy(use_history_in_prompt=False),
                ))
            delivered = bool(block and any(
                item.get("role") == "system" and item.get("content") == block for item in built.messages
            ) and case["expected_content"] in block)
            rows.append({"case": case["label"], "variant": number, "visible": case["visible"],
                         "rank": rank, "wide_rank": wide_rank, "delivered": delivered,
                         "sources": dict(Counter(result["source"] for result in results))})
    positives = [row for row in rows if row["visible"]]
    negatives = [row for row in rows if not row["visible"]]
    return {
        "visible_queries": len(positives), "hidden_queries": len(negatives),
        "hits_at_3": sum(row["rank"] is not None and row["rank"] <= 3 for row in positives),
        "hits_at_5": sum(row["rank"] is not None for row in positives),
        "mrr_at_5": round(sum(1 / row["rank"] for row in positives if row["rank"]) / max(1, len(positives)), 4),
        "hidden_hits": sum(row["rank"] is not None for row in negatives),
        "visible_delivered": sum(row["delivered"] for row in positives),
        "hidden_delivered": sum(row["delivered"] for row in negatives),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "dml", "auto"), default="cpu")
    choices = {**PROFILES, **TUNING_PROFILES}
    parser.add_argument("--profiles", nargs="+", choices=tuple(choices), default=list(PROFILES))
    parser.add_argument("--cases", choices=("all", "original", "new"), default="all")
    parser.add_argument("--search-history", action="store_true",
                        help="Include archived dialogue from an existing timeline in lexical profiles")
    parser.add_argument("--history-cases", type=Path, help="Local annotated questions for archived dialogue")
    parser.add_argument("--history-only", action="store_true", help="Skip the synthetic canon questions")
    parser.add_argument("--cache-queries", action="store_true",
                        help="Reuse query vectors for a quality sweep; reported wall time is not a latency benchmark")
    args = parser.parse_args()
    if args.output.resolve() in {path.resolve() for path in (args.snapshot, args.history_cases) if path}:
        parser.error("The report path must differ from all input files")
    if args.history_cases and not args.search_history:
        parser.error("--history-cases requires --search-history")
    if args.history_only and not args.history_cases:
        parser.error("--history-only requires --history-cases")
    logging.disable(logging.CRITICAL)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    cases = []
    if args.cases in ("all", "original"):
        cases += json.loads((HERE / "canon_cases.json").read_text(encoding="utf-8"))
    if args.cases in ("all", "new"):
        cases += json.loads((HERE / "zero_memory_cases.json").read_text(encoding="utf-8"))
    if args.history_only:
        cases = []
    needs_vectors = any(choices[name]["RAG_VECTOR_SEARCH_ENABLED"] for name in args.profiles)
    if args.search_history and (not args.snapshot or needs_vectors):
        parser.error("--search-history requires a timeline snapshot and lexical profiles")
    common = {**COMMON, "RAG_SEARCH_HISTORY": args.search_history}
    history_scope = "archived dialogue verified by timeline" if args.search_history else "history disabled"
    report = {"scope": f"all character memories and seeded graph; {history_scope}",
              "cases": len(cases), "case_set": args.cases, "cached_queries": args.cache_queries,
              "settings": common, "profiles": {}, "diagnostics": {}}

    def forbidden(*_args, **_kwargs):
        raise RuntimeError("Network access is forbidden in the offline memory benchmark")

    with tempfile.TemporaryDirectory(prefix="nm_profiles_", ignore_cleanup_errors=True) as directory, patch.object(socket.socket, "connect", forbidden):
        path = Path(directory) / "world.db"
        if args.snapshot:
            with closing(sqlite3.connect(args.snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(path)) as copy:
                    original.backup(copy)
        setup_test_db(str(path))
        tester = RagTesterService(bootstrap_engine=False)
        if args.search_history:
            from infrastructure.timeline.sqlite import SQLiteTimelineRepository
            from services.conversation_timeline import ConversationTimeline
            from services.timeline_runtime import SessionTimelineRuntime

            repository = SQLiteTimelineRepository(connection_factory=tester.db.get_connection)
            if repository.selection("desktop") is None:
                parser.error("--search-history requires an existing desktop timeline")
            runtime = SessionTimelineRuntime(repository, repository)
            conversation = ConversationTimeline(runtime)
            services().register(ConversationTimeline, conversation)
        history_cases = prepare_history_cases(
            tester, conversation, json.loads(args.history_cases.read_text(encoding="utf-8-sig")),
        ) if args.history_cases else []
        with SettingsOverride({**common, "RAG_VECTOR_SEARCH_ENABLED": needs_vectors,
                               "RAG_SEARCH_GRAPH": True, "RAG_GRAPH_VECTOR_SEARCH": needs_vectors}):
            started = time.perf_counter()
            embedder = LocalONNXService(args.device) if needs_vectors else None
            if embedder:
                report["model_load_seconds"] = time.perf_counter() - started
                services().register(EmbeddingService, embedder)
            characters = sorted({case[0] for case in cases} | {case["character"] for case in history_cases})
            with patch.object(MemoryManager, "_schedule_embed"):
                for cid in characters:
                    seed_character(cid)
            started = time.perf_counter()
            indexed = {}
            for cid in characters if embedder else ():
                rag = RAGManager(cid)
                indexer = RagIndexer(rag)
                pending = indexer.store.sources("memories", rag._current_model_name(), missing=True)
                records = [(source.identity, source.content) for source in pending]
                count = indexer.documents("memories", records, priority="bulk")
                if count != len(records):
                    raise RuntimeError(f"Incomplete vector index for {cid}: {count}/{len(records)}")
                with tester.db.connection() as conn:
                    total = conn.execute(
                        "SELECT count(*) FROM embeddings WHERE character_id=? AND source_table='memories' AND model_name=?",
                        (cid, rag._current_model_name()),
                    ).fetchone()[0]
                indexed[cid] = {"new_memories": count, "total_memories": total,
                                "new_graph_entities": rag.index_graph_entity_embeddings()}
                print(json.dumps({"indexed": cid, **indexed[cid]}), flush=True)
            report["indexed"] = indexed
            report["index_seconds"] = time.perf_counter() - started
            if embedder:
                report["unique_index_texts"] = len(embedder.cache)
                embedder.cache.clear()
                embedder.cache_indexing = args.cache_queries
            for name in args.profiles:
                options = {**common, "RAG_KEYWORD_SEARCH": True, "RAG_USE_FTS": True, **choices[name]}
                diagnostics = []
                if cases:
                    report["profiles"][name] = evaluate(
                        tester, cases, "combined", diagnostics=diagnostics, profile_options=options,
                    )
                if history_cases:
                    report.setdefault("history", {})[name] = evaluate_history(tester, history_cases, options)
                report.setdefault("profile_settings", {})[name] = options
                report["diagnostics"][name] = diagnostics
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps({"profile_done": name}), flush=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if RAGManager._ACCESS_EXECUTOR is not None:
            RAGManager._ACCESS_EXECUTOR.shutdown(wait=True)
            RAGManager._ACCESS_EXECUTOR = None
        gc.collect()
    summary = {"profiles": report["profiles"], "index_seconds": report["index_seconds"]}
    if history_cases:
        summary["history"] = {
            name: {key: value for key, value in stats.items() if key != "rows"}
            for name, stats in report["history"].items()
        }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
