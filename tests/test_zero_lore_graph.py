import sys
from pathlib import Path
from types import SimpleNamespace

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"),
               str(Path(__file__).resolve().parents[1] / "src/utils/Testing/rag_tester")]

from canon_benchmark import seed_character
from controllers.model_controller import ModelController
from controllers.prompt_controller import PromptController
from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from managers.rag.graph.graph_store import GraphStore
from managers.rag.rag_manager import RAGManager
from managers.rag.pipeline.retrievers.graph import GraphRetriever
from managers.rag.pipeline.types import QueryState
from rag_tester_core import SettingsOverride, setup_test_db
from managers.settings_manager import SettingsManager
from services.contracts import PromptBuildRequest, RequestPolicy


def test_character_seed_graphs_keep_reported_knowledge_and_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", None)
    monkeypatch.setattr(RAGManager, "_INSTANCES", {})
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
    controller = object.__new__(ModelController)
    controller.settings = SettingsManager
    builder = PromptController()
    builder._build_system_messages = lambda *_a, **_k: ([], [], [])
    builder._build_system_state_message = lambda *_a, **_k: {"role": "system", "content": "[System state]"}
    with SettingsOverride({
        "RAG_ENABLED": True, "RAG_VECTOR_SEARCH_ENABLED": False, "RAG_SEARCH_MEMORY": False,
        "RAG_SEARCH_HISTORY": False, "RAG_SEARCH_GRAPH": True, "RAG_GRAPH_VECTOR_SEARCH": False,
        "RAG_CROSS_ENCODER_ENABLED": False, "RAG_MAX_RESULTS": 5, "RAG_SIM_THRESHOLD": 0.4,
    }):
        for cid in graphs:
            query = "Исследователь" if cid != "ShortHair" else "Коротковолосая"
            block = controller.process_rag(cid, "", query) or ""
            character = SimpleNamespace(char_id=cid, get_variable=lambda key, default=None: default)
            built = builder.build(PromptBuildRequest(
                character=character, event_type="chat", user_input=query, rag_context=block,
                policy=RequestPolicy(use_history_in_prompt=False),
            ))
            text = "\n".join(str(m.get("content") or "") for m in built.messages)
            if cid == "Crazy":
                assert "носитель_недоступен" in text
            elif cid == "ShortHair":
                assert "слышала_о_прежней_силе" in text
            else:
                assert "носитель_недоступен" not in text
