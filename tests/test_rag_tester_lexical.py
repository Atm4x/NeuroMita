"""The offline CLI must exercise real SQLite search without invoking ML."""
import json
import socket
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path[:0] = [str(SRC), str(SRC / "utils" / "Testing" / "rag_tester")]

import rag_tester_cli as cli
from managers.database_manager import DatabaseManager
from managers.rag.rag_manager import RAGManager


@pytest.mark.parametrize("command", ["run", "sweep"])
def test_lexical_cli_runs_without_model_calls(monkeypatch, tmp_path, command):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("lexical search must not use ML or the network")

    from handlers.ai_engine import inprocess_engine
    from managers.rag.pipeline.cross_encoder import CrossEncoderReranker

    for attr in ("_build_query_embedding", "update_memory_embedding", "update_history_embedding",
                 "index_graph_entity_embeddings"):
        monkeypatch.setattr(RAGManager, attr, forbidden)
    monkeypatch.setattr(CrossEncoderReranker, "get", forbidden)
    monkeypatch.setattr(inprocess_engine, "register_inprocess_engine", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", None)

    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    scenario = write("scenario.json", {
        "character_id": "Kind", "memories": [{"content": "orchid conservation", "is_forgotten": 0}],
    })
    suite = write("suite.json", {"character_id": "Kind", "cases": [
        {"query": "orchid", "expected_ids": ["1"]},
    ]})
    overrides = {"RAG_VECTOR_SEARCH_ENABLED": True, "RAG_CROSS_ENCODER_ENABLED": True,
                 "RAG_GRAPH_VECTOR_SEARCH": True, "RAG_USE_FTS": True}
    output = tmp_path / "out.json"
    args = [command, "--scenario", scenario, "--suite", suite, "--lexical-only",
            "--db", str(tmp_path / "world.db"), "--format", "json", "--output", str(output)]
    if command == "run":
        args += ["--overrides", json.dumps(overrides)]
    else:
        args += ["--sweep-config", write("grid.json", {
            "fixed_overrides": overrides, "parameters": {"RAG_KEYWORD_SEARCH": [False, True]},
        })]
    monkeypatch.setattr(sys, "argv", ["rag_tester", *args])
    cli.main()
    assert not calls
    report = json.loads(output.read_text(encoding="utf-8"))
    batches = [report] if command == "run" else report["results"]
    assert batches and all(batch["mean_recall"] == 1 for batch in batches)
