from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.services import services
from core.state_barrier import StateBarrier, StateUnavailable
from infrastructure.timeline.character_state import SQLiteCharacterState
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from managers.character_resource_manager import CharacterResourceManager
from managers.database_manager import DatabaseManager
from managers.rag.rag_manager import RAGManager
from managers.session_state_participants import CharacterRuntimeSnapshot
from managers.settings_manager import SettingsManager
from services.conversation_timeline import ConversationTimeline
from services.session_restoration import SessionRestoration
from services.timeline_runtime import SessionTimelineRuntime


class SessionRagTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        environment = patch.dict(os.environ, {"NEUROMITA_HISTORIES_DIR": self.folder.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.previous_db = DatabaseManager._instance, DatabaseManager._path_override
        DatabaseManager._instance = None
        DatabaseManager._path_override = str(Path(self.folder.name) / "world.db")
        self.addCleanup(self._restore_database)
        self.db = DatabaseManager()
        self.resources = CharacterResourceManager()
        for identity in ("A", "B"):
            self.resources.register_character(identity, identity)
            self.resources.history_for(identity).rag = None
            self.resources.memory_for(identity).rag = None
        repository = SQLiteTimelineRepository(connection_factory=self.db.get_connection)
        self.runtime = SessionTimelineRuntime(repository, repository)
        previous = services().get_optional(StateBarrier)
        services().register(StateBarrier, self.runtime.state, replace=True)

        def restore_service():
            services().unregister(StateBarrier)
            if previous is not None:
                services().register(StateBarrier, previous)

        self.addCleanup(restore_service)
        manager = SimpleNamespace(get_all_characters=lambda: ["A", "B"], get_loaded_character=lambda _identity: None,
            resources=self.resources)
        self.conversation = ConversationTimeline(self.runtime)
        SessionRestoration(self.runtime, (SQLiteCharacterState(self.db.get_connection, manager.get_all_characters),
            CharacterRuntimeSnapshot(manager, self.conversation)), SQLiteRestorationJournal(self.db.get_connection))
        self.rag = RAGManager("A")
        self.rag._current_model_name = lambda: "test-model"
        self.rag._current_dimensions = lambda: 2
        self.rag._get_reindex_batch_size = lambda: 2
        self.rag._get_embedding = lambda _text: np.array([1, 0], dtype=np.float32)
        self.rag._get_embeddings = lambda texts, **_options: [self.rag._get_embedding(text) for text in texts]
        self.config = {"RAG_SENTENCE_LEVEL": False, "RAG_GRAPH_VECTOR_SEARCH": False}
        settings = patch.object(SettingsManager, "get", side_effect=lambda key, default=None: self.config.get(key, default))
        settings.start()
        self.addCleanup(settings.stop)

    def _restore_database(self):
        DatabaseManager._instance, DatabaseManager._path_override = self.previous_db

    def _vectors(self):
        with closing(self.db.get_connection()) as connection:
            return connection.execute("SELECT source_table, source_id FROM embeddings WHERE character_id='A' ORDER BY source_id").fetchall()

    def test_invisible_history_cannot_take_a_retrieval_slot(self):
        self.config.update({
            "RAG_ENABLED": True, "RAG_VECTOR_SEARCH_ENABLED": False, "RAG_USE_FTS": True,
            "RAG_KEYWORD_SEARCH": True, "RAG_SEARCH_HISTORY": True, "RAG_SEARCH_MEMORY": True,
            "RAG_SEARCH_GRAPH": False, "RAG_NOISE_MAX": 0, "RAG_DETAILED_LOGS": False,
            "RAG_QUERY_TAIL_MESSAGES": 0,
        })
        cache = self.resources.history_for("A")
        private = {"role": "assistant", "message_id": "private-orchid",
                   "content": "orchid orchard private agreement"}
        self.conversation.record_message(private, ("B",), actor_id="B")
        cache._insert_history_row(msg=private, is_active=0)
        visible = {"role": "user", "message_id": "visible-orchid", "content": "An orchid bloomed."}
        self.conversation.record_message(visible, ("A",), actor_id="Player", player=True)
        cache._insert_history_row(msg={**visible, "content": "Stale orchid report."}, is_active=0)
        turn = self.runtime.capture(character_id="A")
        future = {**private, "message_id": "future-orchid"}
        self.conversation.record_message(future, ("A",), actor_id="B")
        cache._insert_history_row(msg=future, is_active=0)
        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        try:
            with self.runtime.turn_scope(turn):
                results = self.rag.search_relevant("orchid orchard private agreement", limit=1, threshold=0)
        finally:
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.assertEqual([row.get("message_id") for row in results], ["visible-orchid"])
        self.assertEqual(results[0]["speaker"], "Player")
        self.assertEqual(results[0]["content"], "An orchid bloomed.")
        self.assertEqual(results[0]["features"]["lex"], 1.0)

    def test_query_tail_uses_only_visible_history_at_turn_start(self):
        from managers.rag.pipeline.config import RAGConfig
        from managers.rag.pipeline.query_builder import QueryBuilder

        visible = {"role": "user", "message_id": "visible-tail", "content": "orchid garden"}
        hidden = {"role": "user", "message_id": "private-tail", "content": "blackmail ransom"}
        late = {"role": "user", "message_id": "future-tail", "content": "volcano eruption"}
        self.conversation.record_message(visible, ("A",), actor_id="Player", player=True)
        self.conversation.record_message(hidden, ("B",), actor_id="Player", player=True)
        turn = self.runtime.capture(character_id="A")
        self.conversation.record_message(late, ("A",), actor_id="Player", player=True)
        cache = self.resources.history_for("A")
        for message in ({**visible, "content": "stale archive", "speaker": "Wrong"}, hidden, late):
            cache._insert_history_row(msg=message, is_active=1)
        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        try:
            with self.runtime.turn_scope(turn):
                cfg = RAGConfig(tail_messages=1, kw_enabled=True, vector_search_enabled=False)
                query = QueryBuilder(rag=self.rag, cfg=cfg).build("What happened?")
                weighted_tail = self.rag._get_recent_active_contents(1, role_filter="user_only")
        finally:
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.assertEqual(query.expanded_query_text, "User: orchid garden\nUser: What happened?")
        self.assertIn("orchid", query.keywords)
        self.assertEqual(query.ctx_speaker, "Player")
        self.assertEqual(weighted_tail, ["orchid garden"])

    def test_rag_continuity_rehydrates_and_expires_without_duplicates(self):
        from services.rag_continuity import RagContinuity

        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        def restore():
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.addCleanup(restore)
        self.config.update({"RAG_ENABLED": True, "RAG_CONTINUITY_ENABLED": True, "RAG_CONTINUITY_TURNS": 4,
                            "RAG_CONTINUITY_MAX_RECORDS": 4, "RAG_MEMORY_MODE": "all"})
        memory = self.resources.memory_for("A")
        identity = memory.add_memory("Mila visited the orchid garden.")
        fresh = {"source": "memory", "id": identity, "content": "Mila visited the orchid garden.",
                 "score": 0.9, "features": {"kw": 0.7}}
        cache = RagContinuity()
        with patch.object(self.rag, "search_relevant", return_value=[fresh]):
            self.assertEqual(len(cache.search(self.rag, "Mila?", limit=5, threshold=0.3,
                                             settings=SettingsManager)), 1)
        with self.db.connection() as conn:
            conn.execute("UPDATE memories SET content='Updated Mila account.' WHERE character_id='A' AND eternal_id=?",
                         (identity,))
            conn.commit()
        with patch.object(self.rag, "search_relevant", return_value=[]):
            retained = cache.search(self.rag, "Tell me more", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertEqual(retained[0]["content"], "Updated Mila account.")
            self.assertEqual(retained[0]["retained_age"], 1)
            repeated = cache.search(self.rag, "Tell me more", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertEqual(repeated[0]["retained_age"], 1)
            cache.search(self.rag, "What happened next?", limit=5, threshold=0.3, settings=SettingsManager)
            cache.search(self.rag, "Go on", limit=5, threshold=0.3, settings=SettingsManager)
            expired = cache.search(self.rag, "Why did she?", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertEqual(expired, [])
        with patch.object(self.rag, "search_relevant", return_value=[fresh]):
            confirmed = cache.search(self.rag, "Mila again", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertEqual(len(confirmed), 1)
        with self.db.connection() as conn:
            conn.execute("UPDATE memories SET is_deleted=1 WHERE character_id='A' AND eternal_id=?", (identity,))
            conn.commit()
        with patch.object(self.rag, "search_relevant", return_value=[]):
            self.assertEqual(cache.search(self.rag, "Tell me more", limit=5, threshold=0.3,
                                          settings=SettingsManager), [])

    def test_rag_continuity_scopes_history_and_expands_followup_for_search(self):
        from services.rag_continuity import RagContinuity

        self.config["RAG_ENABLED"] = True
        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        def restore():
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.addCleanup(restore)
        message = {"message_id": "mila-story", "role": "user", "content": "What happened to Mila?"}
        self.conversation.record_message(message, ("A",), actor_id="Player", player=True)
        identity = self.resources.history_for("A")._insert_history_row(msg=message, is_active=0)
        fresh = {"source": "history", "id": identity, "message_id": "mila-story", "content": message["content"],
                 "score": 0.9, "features": {"kw": 0.8}}
        cache = RagContinuity()
        with patch.object(self.rag, "search_relevant", return_value=[fresh]):
            cache.search(self.rag, "Mila", limit=5, threshold=0.3, settings=SettingsManager)
        with patch.object(self.rag, "search_relevant", return_value=[]) as search:
            with patch.object(self.rag, "recent_query_rows", return_value=[{
                "role": "assistant", "speaker": "A", "content": "С Милой? Та история...",
            }]):
                retained = cache.search(self.rag, "Расскажи подробности этой истории", limit=5,
                                        threshold=0.3, settings=SettingsManager)
            self.assertIn("Милой", search.call_args.args[0])
            self.assertEqual(retained[0]["speaker"], "Player")
            self.runtime.start_session(inherit_current=True)
            self.assertEqual(cache.search(self.rag, "А потом?", limit=5, threshold=0.3,
                                          settings=SettingsManager), [])

    def test_rag_continuity_shrinks_on_topic_change_and_can_be_disabled(self):
        from services.rag_continuity import RagContinuity

        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        def restore():
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.addCleanup(restore)
        self.config.update({"RAG_ENABLED": True, "RAG_CONTINUITY_TURNS": 5, "RAG_CONTINUITY_DECAY": 0.7,
                            "RAG_CONTINUITY_MAX_RECORDS": 4, "RAG_MEMORY_MODE": "all"})
        fresh = []
        for number in range(4):
            identity = self.resources.memory_for("A").add_memory(f"Mila visited garden {number}.")
            fresh.append({"source": "memory", "id": identity, "content": f"garden {number}",
                          "score": 1 - number * 0.1, "features": {"kw": 0.8}})
        cache = RagContinuity()
        with patch.object(self.rag, "search_relevant", return_value=fresh):
            cache.search(self.rag, "Mila garden", limit=5, threshold=0.3, settings=SettingsManager)
        with patch.object(self.rag, "search_relevant", return_value=[]):
            rows = cache.search(self.rag, "Tell me more", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertEqual(len(rows), 3)
            rows = cache.search(self.rag, "Play rock music", limit=5, threshold=0.3, settings=SettingsManager)
            self.assertLess(len(rows), 3)
            self.config["RAG_CONTINUITY_ENABLED"] = False
            self.assertEqual(cache.search(self.rag, "Go on", limit=5, threshold=0.3, settings=SettingsManager), [])
            self.config["RAG_CONTINUITY_ENABLED"] = True
            self.assertEqual(cache.search(self.rag, "Go on", limit=5, threshold=0.3, settings=SettingsManager), [])

    def test_retained_evidence_is_delivered_in_production_rag_block(self):
        from controllers.model_controller import ModelController

        self.config.update({"RAG_ENABLED": True, "RAG_MEMORY_MODE": "all"})
        previous = services().get_optional(ConversationTimeline)
        services().register(ConversationTimeline, self.conversation, replace=True)
        def restore():
            services().unregister(ConversationTimeline)
            if previous is not None:
                services().register(ConversationTimeline, previous)
        self.addCleanup(restore)
        identity = self.resources.memory_for("A").add_memory("Mila visited the orchid garden.")
        record = {"source": "memory", "id": identity, "content": "Mila visited the orchid garden.",
                  "type": "fact", "priority": "Normal", "score": 0.9, "features": {"kw": 0.8}}
        controller = object.__new__(ModelController)
        controller.settings = SettingsManager
        with patch.object(RAGManager, "for_character", return_value=self.rag), \
                patch.object(self.rag, "search_relevant", side_effect=[[record], []]):
            initial = controller.process_rag("A", "", "Mila garden")
            continuation = controller.process_rag("A", "", "Tell me more")
        self.assertIn("Mila visited", initial)
        self.assertIn("Mila visited", continuation)
        self.assertIn("retained for topic continuity", continuation)
        self.assertEqual(continuation.count("Mila visited"), 1)

    def _while_embedding(self, operation, transition, *, sentences=False):
        started, release = Event(), Event()
        errors = []

        def provider(_text, **_options):
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test provider was not released")
            return [np.array([1, 0], dtype=np.float32)] if sentences else np.array([1, 0], dtype=np.float32)

        setattr(self.rag, "_get_embeddings" if sentences else "_get_embedding", provider)

        def execute():
            try:
                operation()
            except BaseException as exc:
                errors.append(exc)

        worker = Thread(target=execute)
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            transition()
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        return errors

    def test_memory_embedding_does_not_block_restore_and_cannot_write_to_the_restored_world(self):
        identity = self.resources.memory_for("A").add_memory("Saved memory")
        checkpoint = self.runtime.checkpoint()
        self.resources.memory_for("A").update_memory(identity, "Future memory")
        errors = self._while_embedding(lambda: self.rag.update_memory_embedding(identity, "Future memory"),
            lambda: self.runtime.restore(checkpoint.event_id))
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], StateUnavailable)
        self.assertEqual(self.resources.memory_for("A").get_memory_content(identity), "Saved memory")
        self.assertEqual(self._vectors(), [])

    def test_checkpoint_can_capture_while_inference_runs_without_invalidating_its_result(self):
        identity = self.resources.memory_for("A").add_memory("Saved memory")
        errors = self._while_embedding(lambda: self.rag.update_memory_embedding(identity, "Saved memory"),
            self.runtime.checkpoint)
        self.assertEqual(errors, [])
        self.assertEqual(self._vectors(), [("memories", identity)])

    def test_sentence_embedding_holds_neither_the_barrier_nor_a_sqlite_write_transaction(self):
        self.config["RAG_SENTENCE_LEVEL"] = True
        identity = self.resources.memory_for("A").add_memory("A saved sentence with enough characters.")
        checkpoint = self.runtime.checkpoint()
        errors = self._while_embedding(lambda: self.rag.update_memory_embedding(identity, "A saved sentence with enough characters."),
            lambda: self.runtime.restore(checkpoint.event_id), sentences=True)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], StateUnavailable)
        self.assertEqual(self._vectors(), [])

    def test_same_world_edit_during_inference_rejects_the_outdated_vector(self):
        identity = self.resources.memory_for("A").add_memory("Old content")
        errors = self._while_embedding(lambda: self.rag.update_memory_embedding(identity, "Old content"),
            lambda: self.resources.memory_for("A").update_memory(identity, "Edited content"))
        self.assertEqual(errors, [])
        self.assertEqual(self._vectors(), [])

    def test_already_stale_input_and_another_characters_row_are_not_embedded(self):
        identity = self.resources.memory_for("A").add_memory("Current content")
        other = self.resources.history_for("B").add_message({"role": "user", "content": "Other content"})
        with patch.object(self.rag, "_get_embedding") as provider:
            self.rag.update_memory_embedding(identity, "Old content")
            self.rag.update_history_embedding(other, "Other content")
        provider.assert_not_called()
        self.assertEqual(self._vectors(), [])

    def test_bulk_indexing_uses_batches_and_missing_pass_keeps_current_vectors(self):
        for text in ("A dragon guards the mountain pass", "The player enjoys fresh lemonade",
                     "Yesterday the spaceship lost its engine", "A violin plays a melody in the attic",
                     "The library opens at half past eight"):
            self.resources.memory_for("A").add_memory(text)
        calls = []

        def provider(texts, **options):
            calls.append((list(texts), options))
            return [np.array([1, 0], dtype=np.float32) for _text in texts]

        self.rag._get_embeddings = provider
        self.assertEqual(self.rag.index_all(), 5)
        self.assertEqual([len(texts) for texts, _options in calls], [2, 2, 1])
        self.assertTrue(all(options["batch_size"] == 2 for _texts, options in calls))
        self.assertEqual(len(self._vectors()), 5)
        calls.clear()
        self.assertEqual(self.rag.index_all_missing(), 0)
        self.assertEqual(calls, [])

    def test_missing_sentence_pass_runs_even_when_all_document_vectors_exist(self):
        text = "First sentence with enough characters. Second sentence with enough characters."
        identity = self.resources.memory_for("A").add_memory(text)
        self.rag.update_memory_embedding(identity, text)
        self.config["RAG_SENTENCE_LEVEL"] = True
        self.assertEqual(self.rag.index_all_missing(), 2)
        with closing(self.db.get_connection()) as connection:
            count = connection.execute("SELECT COUNT(*) FROM sentence_embeddings WHERE character_id='A'").fetchone()[0]
        self.assertEqual(count, 2)
        self.assertEqual(len(self._vectors()), 1)

    def test_invalid_provider_vectors_do_not_leave_partial_derived_rows(self):
        identity = self.resources.memory_for("A").add_memory("Memory")
        for vector in (np.array([float("nan"), 1]), np.array([1]), np.array([[1, 0]])):
            self.rag._get_embedding = lambda _text, vector=vector: vector
            self.rag.update_memory_embedding(identity, "Memory")
        self.assertEqual(self._vectors(), [])

    def test_history_embedding_accepts_the_existing_multipart_and_summary_serialization(self):
        history = self.resources.history_for("A")
        multipart = history.add_message({"role": "user", "content": [
            {"type": "text", "text": "  First part  "}, {"type": "text", "text": "  Second part  "}]})
        summary = history.add_message({"role": "system", "content": {"summary": "Saved summary"}})
        self.assertEqual(self.rag.update_history_embeddings([(multipart, "First part\nSecond part"),
            (summary, json.dumps({"summary": "Saved summary"}))]), 2)
        self.assertEqual(len(self._vectors()), 2)


if __name__ == "__main__":
    unittest.main()
