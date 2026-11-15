"""Compare lexical, Qwen ONNX, and graph profiles on a disposable world.

Requires the installed local ONNX runtime and model. Never installs models,
contacts a generation provider, or changes the input snapshot.
"""
from __future__ import annotations

import argparse
import gc
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "dml", "auto"), default="cpu")
    parser.add_argument("--profiles", nargs="+", choices=tuple(PROFILES), default=list(PROFILES))
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    cases = json.loads((HERE / "canon_cases.json").read_text(encoding="utf-8"))
    cases += json.loads((HERE / "zero_memory_cases.json").read_text(encoding="utf-8"))
    report = {"scope": "all character memories and seeded graph; history retrieval disabled",
              "cases": len(cases), "settings": COMMON, "profiles": {}, "diagnostics": {}}

    def forbidden(*_args, **_kwargs):
        raise RuntimeError("Network access is forbidden in the offline memory benchmark")

    with tempfile.TemporaryDirectory(prefix="nm_profiles_", ignore_cleanup_errors=True) as directory, patch.object(socket.socket, "connect", forbidden):
        path = Path(directory) / "world.db"
        if args.snapshot:
            with closing(sqlite3.connect(args.snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(path)) as copy:
                    original.backup(copy)
        setup_test_db(str(path))
        tester = RagTesterService()
        with SettingsOverride({**COMMON, "RAG_VECTOR_SEARCH_ENABLED": True,
                               "RAG_SEARCH_GRAPH": True, "RAG_GRAPH_VECTOR_SEARCH": True}):
            started = time.perf_counter()
            embedder = LocalONNXService(args.device)
            report["model_load_seconds"] = time.perf_counter() - started
            services().register(EmbeddingService, embedder)
            characters = sorted({case[0] for case in cases})
            with patch.object(MemoryManager, "_schedule_embed"):
                for cid in characters:
                    seed_character(cid)
            started = time.perf_counter()
            indexed = {}
            for cid in characters:
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
            report["unique_index_texts"] = len(embedder.cache)
            embedder.cache_indexing = False
            for name in args.profiles:
                options = PROFILES[name]
                diagnostics = []
                report["profiles"][name] = evaluate(
                    tester, cases, "combined", diagnostics=diagnostics,
                    profile_options={**COMMON, **options},
                )
                report.setdefault("profile_settings", {})[name] = {**COMMON, **options}
                report["diagnostics"][name] = diagnostics
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps({"profile_done": name}), flush=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if RAGManager._ACCESS_EXECUTOR is not None:
            RAGManager._ACCESS_EXECUTOR.shutdown(wait=True)
            RAGManager._ACCESS_EXECUTOR = None
        gc.collect()
    print(json.dumps({"profiles": report["profiles"], "index_seconds": report["index_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
