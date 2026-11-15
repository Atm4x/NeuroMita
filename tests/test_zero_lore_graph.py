import sys
from pathlib import Path
from types import SimpleNamespace

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"),
               str(Path(__file__).resolve().parents[1] / "src/utils/Testing/rag_tester")]

from canon_benchmark import seed_character
from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from managers.rag.graph.graph_store import GraphStore
from managers.rag.pipeline.retrievers.graph import GraphRetriever
from managers.rag.pipeline.types import QueryState
from rag_tester_core import SettingsOverride, setup_test_db


def test_character_seed_graphs_keep_reported_knowledge_and_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", None)
    setup_test_db(str(tmp_path / "world.db"))
    db = DatabaseManager()
    graphs = {}
    for character in ("Crazy", "Kind", "ShortHair", "Cappie", "Mila", "Sleepy"):
        memory = MemoryManager(character)
        memory.rag = SimpleNamespace(db=db, character_id=character)
        monkeypatch.setattr("canon_benchmark.MemoryManager", lambda cid, m=memory: m)
        monkeypatch.setattr(memory, "_schedule_embed", lambda *_: None)
        with SettingsOverride({"RAG_ENABLED": True}):
            seed_character(character)
            graph = GraphStore(db, character)
            before = graph.get_all_relations()
            seed_character(character)
            after = graph.get_all_relations()
        assert len(before) == len(after)
        graphs[character] = graph
        with db.connection() as conn:
            seeds = conn.execute(
                "SELECT content, lore_age_days FROM memories WHERE character_id=? "
                "AND type='seed_lore' AND is_deleted=0 AND content LIKE '%общ%коридор%'", (character,),
            ).fetchall()
        if character != "Crazy":
            assert any(days == 14 for _, days in seeds), character
    cfg = SimpleNamespace(graph_vector_search=False)
    query = QueryState("ShortHair", "Кепочка", "", None, ["кепочка"], None)
    found = GraphRetriever(graph_store=graphs["ShortHair"], cfg=cfg).retrieve(query)
    assert any("слышала_о_прежней_силе" in row.content for row in found)
    for character in ("Kind", "Cappie", "Mila", "Sleepy"):
        found = GraphRetriever(graph_store=graphs[character], cfg=cfg).retrieve(
            QueryState(character, "Исследователь", "", None, ["исследователь"], None),
        )
        assert not found
    found = GraphRetriever(graph_store=graphs["Crazy"], cfg=cfg).retrieve(
        QueryState("Crazy", "Исследователь", "", None, ["исследователь"], None),
    )
    assert any("носитель_недоступен" in row.content for row in found)
