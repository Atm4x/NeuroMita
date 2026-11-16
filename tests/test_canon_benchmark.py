import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/utils/Testing/rag_tester"))

from canon_benchmark import evaluate


def test_benchmark_does_not_count_a_history_row_with_a_memory_id_as_a_hit():
    conn = SimpleNamespace(execute=lambda *_: SimpleNamespace(fetchall=lambda: [(7, "Expected lore.")]))
    private = "PRIVATE"
    history = {"source": "history", "id": 7, "content": private, "score": 0.9}
    memory = {"source": "memory", "id": 7, "content": private, "score": 0.2}
    service = SimpleNamespace(
        db=SimpleNamespace(connection=lambda: nullcontext(conn)),
        _search_timed=lambda **kwargs: ([history] if kwargs["limit"] == 5 else [history, memory], {}),
    )
    diagnostics = []
    report = evaluate(service, [("A", "question", "variant", "Expected lore.")], "combined",
                      diagnostics=diagnostics)
    assert report["recall5"] == 0
    assert report["mrr5"] == 0
    assert report["no_hit"] == ["1.1", "1.2"]
    assert all(row["wide_target_ranks"] == [2] for row in diagnostics)
    assert all(not row["retrieved"][0]["expected"] for row in diagnostics)
    assert private not in str(diagnostics)
