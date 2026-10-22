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
