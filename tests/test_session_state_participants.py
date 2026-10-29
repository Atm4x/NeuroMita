from __future__ import annotations

from contextlib import closing
import datetime
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from threading import Event, RLock, Thread
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.services import services
from core.state_barrier import StateBarrier, StateUnavailable, bind_state_job, state_job, state_operation
from domain.timeline import JsonDocument, new_id
from domain.timeline.restoration import PendingRestore
from infrastructure.timeline.character_state import SQLiteCharacterState
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from managers.character_resource_manager import CharacterResourceManager
from managers.database_manager import DatabaseManager
from managers.session_state_participants import CharacterRuntimeSnapshot
from services.session_restoration import SessionRestoration
from services.timeline_runtime import SessionTimelineRuntime
from services.conversation_timeline import ConversationTimeline
from characters.character import Character


class _Character(SimpleNamespace):
    restore_session_runtime = Character.restore_session_runtime


class StateParticipantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {"NEUROMITA_HISTORIES_DIR": self.temp.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.previous_db = DatabaseManager._instance
        self.previous_path = DatabaseManager._path_override
        DatabaseManager._instance = None
        DatabaseManager._path_override = str(Path(self.temp.name) / "world.db")
        self.addCleanup(self._reset_database)
        self.resources = CharacterResourceManager()
        self.database = DatabaseManager()
        self.characters = {identity: _Character(variables={"mood": 5}, app_vars={"focus": "saved"},
            _dirty_vars={"mood"}, history_epoch=0, _initial_session_variables={"mood": 0}) for identity in ("A", "B")}
        for identity in self.characters:
            self.resources.register_character(identity, identity)
            self.resources.memory_for(identity).rag = None
            self.resources.history_for(identity).rag = None
        self.manager = SimpleNamespace(resources=self.resources, get_all_characters=lambda: ["A", "B"],
            get_loaded_character=self.characters.get)
        repository = SQLiteTimelineRepository(connection_factory=self.database.get_connection)
        self.runtime = SessionTimelineRuntime(repository, repository)
        self.previous_barrier = services().get_optional(StateBarrier)
        services().register(StateBarrier, self.runtime.state, replace=True)
        self.addCleanup(self._reset_barrier)
        self.store = SQLiteCharacterState(self.database.get_connection, self.manager.get_all_characters,
            lambda identity: self.characters[identity].variables if identity in self.characters else None)
        self.journal = SQLiteRestorationJournal(self.database.get_connection)
        self.conversation = ConversationTimeline(self.runtime)
        self.coordinator = SessionRestoration(self.runtime, (self.store, CharacterRuntimeSnapshot(self.manager, self.conversation)), self.journal)

    def _reset_database(self):
        DatabaseManager._instance = self.previous_db
        DatabaseManager._path_override = self.previous_path

    def _reset_barrier(self):
        services().unregister(StateBarrier)
        if self.previous_barrier is not None:
            services().register(StateBarrier, self.previous_barrier)

    def test_dirty_variables_memory_working_state_and_reminders_restore_together(self):
        self.resources.history_for("A").update_variables_batch({"mood": 1, "removed": "old"})
        memory_id = self.resources.memory_for("A").add_memory("A saved memory")
        self.resources.working_state_for("A").update({"focus": "saved focus", "open_loops": ["one"]})
        reminder_id = self.resources.reminders_for("A").add_reminder("Saved reminder", "2099-01-01T12:00:00")
        checkpoint = self.runtime.checkpoint()
        self.characters["A"].variables = {"mood": 99, "future": True}
        self.characters["A"].app_vars = {"focus": "future"}
        self.resources.memory_for("A").update_memory(memory_id, "Future memory")
        self.resources.working_state_for("A").clear()
        self.resources.reminders_for("A").delete_reminder(reminder_id)
        self.resources.reminders_for("A").add_reminder("Future reminder", "2099-02-01T12:00:00")
        self.runtime.restore(checkpoint.event_id)
        self.assertEqual(self.characters["A"].variables, {"mood": 5})
        self.assertEqual(self.resources.history_for("A").load_variables(), {"mood": 5})
        self.assertEqual(self.characters["A"].app_vars, {"focus": "saved"})
        self.assertEqual(self.characters["A"].history_epoch, 1)
        self.assertEqual(self.characters["A"]._dirty_vars, set())
        self.assertEqual(self.resources.memory_for("A").get_memory_content(memory_id), "A saved memory")
        self.assertEqual(self.resources.working_state_for("A").snapshot()["focus"], "saved focus")
        reminders = self.resources.reminders_for("A").snapshot()
        self.assertEqual([item["text"] for item in reminders["reminders"]], ["Saved reminder"])
        self.assertEqual(reminders["next_number"], reminder_id + 1)
        with open(Path(self.temp.name) / "A/A_reminders.json", encoding="utf-8") as source:
            self.assertIn("Saved reminder", source.read())

    def test_graph_identity_is_rebuilt_without_reusing_other_characters_physical_ids(self):
        from managers.rag.graph.graph_store import GraphStore
        graph = GraphStore(self.database, "A")
        subject = graph.upsert_entity("Player", "person")
        target = graph.upsert_entity("Kitchen", "place")
        graph.add_alias(subject, "the player")
        graph.upsert_relation(subject, "visited", target)
        saved = self.store.capture()
        graph.clear_for_character()
        other = GraphStore(self.database, "C")
        other_id = other.upsert_entity("Unrelated", "person")
        graph.upsert_entity("Future", "thing")
        self.store.apply(saved)
        restored = self.store.capture()
        self.assertEqual(restored.to_dict()["characters"]["A"]["graph"], saved.to_dict()["characters"]["A"]["graph"])
        with closing(self.database.get_connection()) as connection:
            self.assertEqual(connection.execute("SELECT name FROM graph_entities WHERE id=?", (other_id,)).fetchone()[0], "unrelated")
            entities = connection.execute("SELECT id FROM graph_entities WHERE character_id='A'").fetchall()
        self.assertNotIn((other_id,), entities)

    def test_old_background_job_cannot_write_memory_after_restore(self):
        checkpoint = self.runtime.checkpoint()
        job = bind_state_job(lambda: self.resources.memory_for("A").add_memory("Obsolete future"))
        self.runtime.restore(checkpoint.event_id)
        with self.assertRaises(StateUnavailable):
            job()
        self.assertNotIn("Obsolete future", self.resources.memory_for("A").get_memories_formatted())

    def test_obsolete_queued_callback_is_rejected_before_unguarded_side_effects(self):
        effects = []
        checkpoint = self.runtime.checkpoint()
        job = bind_state_job(state_job(lambda: effects.append("old UI callback")))
        self.runtime.restore(checkpoint.event_id)
        with self.assertRaises(StateUnavailable):
            job()
        self.assertEqual(effects, [])

    def test_a_transition_command_can_finish_after_it_invalidates_its_origin(self):
        checkpoint = self.runtime.checkpoint()
        command = bind_state_job(state_job(lambda: self.runtime.restore(checkpoint.event_id)))
        self.assertEqual(command().to_dict()["snapshot_version"], 1)

    def test_snapshot_waits_until_a_new_character_finishes_loading_its_persistent_state(self):
        from managers.character_manager import CharacterManager
        entered, release, captured = Event(), Event(), Event()
        character = SimpleNamespace(variables={"mood": 0})

        def load():
            entered.set()
            if not release.wait(2):
                raise TimeoutError("Character load was not released")
            character.variables = {"mood": 42}

        character.ensure_runtime_loaded = load
        manager = CharacterManager.__new__(CharacterManager)
        manager._lock = RLock()
        manager._definitions = {"A": object()}
        manager.characters = {}
        manager._create_character = lambda _definition: manager.characters.setdefault("A", character)
        values = []

        def capture():
            with self.runtime.state.exclusive():
                values.append(dict(manager.get_loaded_character("A").variables))
                captured.set()

        loader = Thread(target=lambda: manager.get_character("A"))
        loader.start()
        self.assertTrue(entered.wait(1))
        reader = Thread(target=capture)
        reader.start()
        try:
            self.assertFalse(captured.wait(.05))
        finally:
            release.set()
            loader.join(2)
            reader.join(2)
        self.assertEqual(values, [{"mood": 42}])

    def test_bound_job_does_not_hold_the_barrier_while_waiting_for_a_provider(self):
        operation = bind_state_job(lambda: state_operation(lambda: "state")())
        with self.runtime.state.exclusive(invalidate=True):
            pass
        with self.assertRaises(StateUnavailable):
            operation()

    def test_invalid_store_snapshot_is_rejected_before_deleting_records(self):
        identity = self.resources.memory_for("A").add_memory("Keep me")
        saved = self.store.capture().to_dict()
        saved["characters"]["A"]["memories"][0]["content"] = 5
        with self.assertRaises(ValueError):
            self.store.apply(JsonDocument(saved))
        self.assertEqual(self.resources.memory_for("A").get_memory_content(identity), "Keep me")

    def test_character_materialized_after_checkpoint_restores_initial_defaults_and_saved_overrides(self):
        del self.characters["B"]
        self.resources.history_for("B").update_variables_batch({"mood": 8})
        checkpoint = self.runtime.checkpoint()
        self.characters["B"] = _Character(variables={"mood": 99, "future": True}, app_vars={"future": True},
            _dirty_vars={"future"}, history_epoch=0, _initial_session_variables={"mood": 0, "default": True})
        self.runtime.restore(checkpoint.event_id)
        self.assertEqual(self.characters["B"].variables, {"mood": 8, "default": True})
        self.assertEqual(self.characters["B"].app_vars, {})

    def test_jobs_from_a_replaced_runtime_cannot_write_or_rebind_into_the_new_runtime(self):
        job = bind_state_job(lambda: bind_state_job(lambda: self.resources.memory_for("A").add_memory("old runtime"))())
        services().register(StateBarrier, StateBarrier(), replace=True)
        with self.assertRaises(StateUnavailable):
            job()

    def test_reminder_snapshot_counter_survives_reopening_the_file(self):
        reminder = self.resources.reminders_for("A")
        reminder.restore_snapshot({"reminders": [], "next_number": 17, "timer_remaining": {}})
        from managers.reminder_manager import ReminderManager
        reopened = ReminderManager("A")
        self.assertEqual(reopened.snapshot(), {"reminders": [], "next_number": 17, "timer_remaining": {}})
        self.assertEqual(reopened.add_reminder("Next", "2099-01-01T12:00:00"), 17)

    def test_disposable_history_and_search_rows_are_rebuilt_from_the_restored_branch(self):
        history = self.resources.history_for("A")
        saved = {"message_id": "saved", "role": "user", "speaker": "Player", "content": "Saved fact"}
        self.conversation.record_message(saved, ("A",), actor_id="Player", player=True)
        history.add_message(saved)
        checkpoint = self.runtime.checkpoint()
        future = dict(saved, message_id="future", content="Future secret")
        self.conversation.record_message(future, ("A",), actor_id="Player", player=True)
        row_id = history.add_message(future)
        with closing(self.database.get_connection()) as connection:
            connection.execute("UPDATE history SET embedding=? WHERE id=?", (b"stale vector", row_id))
            connection.commit()
        self.runtime.restore(checkpoint.event_id)
        self.assertEqual([message["content"] for message in history.load_history()["messages"]], ["Saved fact"])
        with closing(self.database.get_connection()) as connection:
            self.assertEqual(connection.execute("SELECT is_deleted, embedding FROM history WHERE id=?", (row_id,)).fetchone(), (1, None))

    def test_countdown_timers_restore_remaining_time_while_appointments_keep_their_date(self):
        import managers.reminder_manager as module

        class Clock(datetime.datetime):
            value = datetime.datetime(2026, 10, 22, 10)

            @classmethod
            def now(cls, tz=None):
                return cls.value if tz is None else cls.value.replace(tzinfo=datetime.timezone.utc).astimezone(tz)

        reminder = self.resources.reminders_for("A")
        with patch.object(module, "datetime", SimpleNamespace(datetime=Clock, timedelta=datetime.timedelta)):
            timer = reminder.add_timer("Count down", 15)
            appointment = reminder.add_reminder("Appointment", "2099-01-01T12:00:00")
            checkpoint = self.runtime.checkpoint()
            Clock.value += datetime.timedelta(hours=1)
            self.runtime.restore(checkpoint.event_id)
            by_id = {record["N"]: record for record in reminder.load_reminders()}
            self.assertEqual(Clock.fromisoformat(by_id[timer]["due_iso"]), Clock.value + datetime.timedelta(seconds=15))
            self.assertEqual(by_id[appointment]["due_iso"], "2099-01-01T12:00:00")
            self.assertEqual(reminder.get_due_reminders(), [])

    def test_offset_reminder_deadlines_are_compared_in_local_time(self):
        reminder = self.resources.reminders_for("A")
        record = reminder.add_reminder("Past", "2000-01-01T10:00:00+03:00")
        self.assertEqual([item["N"] for item in reminder.get_due_reminders()], [record])
        self.assertIsNone(reminder.get_next_due_at().tzinfo)

    def test_full_composition_restores_storage_model_context_and_a_live_game_together(self):
        from controllers.model_controller import ModelController
        from managers.game_manager import GameManager
        from managers.game_state_manager import GameState
        from managers.session_state_participants import GamesSnapshot, ModelContextSnapshot
        from modules.SeaBattle.seabattle_instance import SeaBattleGame

        model = ModelController.__new__(ModelController)
        model._game_states_lock = RLock()
        model._temporary_system_infos_lock = RLock()
        model._context_snapshot_lock = RLock()
        model._context_snapshot_cache = {("A", "chat"): [{"content": "Future prompt"}]}
        model._game_states_by_character_id = {"A": GameState(roomPlayer=2, nearObjects="Saved room")}
        model._shared_world_info = {"roomPlayer": 2}
        model._temporary_system_infos = {"A": [{"role": "system", "content": "Saved instruction"}]}
        model._last_token_stats = {"old": 1}
        context = model.snapshot_session_context()
        for identity, character in self.characters.items():
            character.char_id = identity
            character.get_variable = lambda key, default=None, owner=character: owner.variables.get(key, default)
            character.set_variable = lambda key, value, owner=character: owner.variables.update({key: value})
            character.game_manager = GameManager(character)
        self.manager.get_loaded_characters = lambda: list(self.characters.values())
        self.manager.get_character = self.characters.__getitem__
        previous = services().get_optional(SessionTimelineRuntime)
        services().register(SessionTimelineRuntime, self.runtime, replace=True)

        def restore_service():
            services().unregister(SessionTimelineRuntime)
            if previous is not None:
                services().register(SessionTimelineRuntime, previous)

        self.addCleanup(restore_service)
        SessionRestoration(self.runtime, (self.store, GamesSnapshot(self.manager, self.runtime),
            CharacterRuntimeSnapshot(self.manager, self.conversation), ModelContextSnapshot(model)), self.journal)
        owner = self.characters["A"]
        game = SeaBattleGame(owner, "seabattle", host=owner.game_manager)
        owner.game_manager.active_game = game
        game.timeline_selection = self.runtime.selection
        self.addCleanup(lambda: owner.game_manager.active_game.cleanup() if owner.game_manager.active_game else None)
        game.start({})
        memory = self.resources.memory_for("A").add_memory("Saved memory")
        self.conversation.record_message({"message_id": "saved", "content": "Saved message", "role": "user"},
            ("A",), actor_id="Player", player=True)
        working = self.resources.working_state_for("A").snapshot()
        checkpoint = self.runtime.checkpoint()
        board = checkpoint.payload.to_dict()["snapshot"]["participants"]["games"]["state"]["games"]["A"]
        owner.variables["mood"] = 99
        self.resources.memory_for("A").update_memory(memory, "Future memory")
        self.resources.working_state_for("A").update({"focus": "Future focus"})
        self.resources.reminders_for("A").add_timer("Future timer", 60)
        model._game_states_by_character_id["A"].roomPlayer = 4
        model._temporary_system_infos.clear()
        self.conversation.record_message({"message_id": "future", "content": "Future message", "role": "user"},
            ("A",), actor_id="Player", player=True)
        game.command_queue.put({"action": "mita_place_ship", "spec": "A1,1,H"})
        changed = self.runtime.checkpoint()
        self.assertNotEqual(board, changed.payload.to_dict()["snapshot"]["participants"]["games"]["state"]["games"]["A"])
        self.runtime.restore(checkpoint.event_id)
        self.assertEqual(owner.variables["mood"], 5)
        self.assertEqual(self.resources.memory_for("A").get_memory_content(memory), "Saved memory")
        self.assertEqual(self.resources.working_state_for("A").snapshot(), working)
        self.assertEqual(self.resources.reminders_for("A").load_reminders(), [])
        self.assertEqual(model.snapshot_session_context(), context)
        self.assertEqual(model._last_token_stats, {})
        self.assertEqual(model._context_snapshot_cache, {})
        self.assertEqual([item["content"] for item in self.conversation.messages("A")], ["Saved message"])
        restored = self.runtime.checkpoint().payload.to_dict()["snapshot"]["participants"]["games"]["state"]
        self.assertEqual(restored["games"]["A"], board)
        self.assertFalse(owner.game_manager.active_game.snapshot_paused)

    def test_restart_repairs_real_owners_after_a_crash_between_store_and_runtime_application(self):
        self._restart_with_partial_transition(forward=False)

    def test_restart_reconstructs_volatile_owners_after_target_activation_before_journal_completion(self):
        self._restart_with_partial_transition(forward=True)

    def _restart_with_partial_transition(self, *, forward):
        memory = self.resources.memory_for("A").add_memory("Saved memory")
        self.resources.working_state_for("A").update({"focus": "Saved focus"})
        reminder = self.resources.reminders_for("A")
        reminder.add_reminder("Saved reminder", "2099-01-01T12:00:00")
        saved = self.runtime.checkpoint()
        desired = JsonDocument(saved.payload.to_dict()["snapshot"])
        self.characters["A"].variables = {"mood": 99}
        self.resources.memory_for("A").update_memory(memory, "Future memory")
        self.resources.working_state_for("A").update({"focus": "Future focus"})
        reminder.delete_reminder(1)
        reminder.add_reminder("Future reminder", "2099-02-01T12:00:00")
        before = JsonDocument(self.runtime.checkpoint().payload.to_dict()["snapshot"])
        source = self.runtime.selection.branch_id
        target = self.runtime.timeline.fork(saved.event_id).timeline
        self.journal.begin(PendingRestore(new_id(), "desktop", source, target.branch_id, before, desired))
        with self.runtime.state.exclusive():
            self.store.apply(JsonDocument(desired.to_dict()["participants"]["character_store"]["state"]), branch_id=target.branch_id)
            if forward:
                CharacterRuntimeSnapshot(self.manager, self.conversation).apply(
                    JsonDocument(desired.to_dict()["participants"]["character_runtime"]["state"]), branch_id=target.branch_id)
                self.runtime.activate(target.branch_id)

        resources = CharacterResourceManager()
        characters = {identity: _Character(variables={"mood": -1}, app_vars={}, _dirty_vars=set(),
            history_epoch=0, _initial_session_variables={}) for identity in ("A", "B")}
        for identity in characters:
            resources.register_character(identity, identity)
            resources.memory_for(identity).rag = None
            resources.history_for(identity).rag = None
        manager = SimpleNamespace(resources=resources, get_all_characters=lambda: ["A", "B"],
            get_loaded_character=characters.get)
        repository = SQLiteTimelineRepository(connection_factory=self.database.get_connection)
        runtime = SessionTimelineRuntime(repository, repository)
        services().register(StateBarrier, runtime.state, replace=True)
        conversation = ConversationTimeline(runtime)
        coordinator = SessionRestoration(runtime, (SQLiteCharacterState(self.database.get_connection,
            manager.get_all_characters, lambda identity: characters[identity].variables),
            CharacterRuntimeSnapshot(manager, conversation)), SQLiteRestorationJournal(self.database.get_connection))
        self.assertTrue(coordinator.recover())
        self.assertEqual(runtime.selection.branch_id, target.branch_id if forward else source)
        self.assertEqual(characters["A"].variables, {"mood": 5 if forward else 99})
        expected = "Saved" if forward else "Future"
        self.assertEqual(resources.memory_for("A").get_memory_content(memory), f"{expected} memory")
        self.assertEqual(resources.working_state_for("A").snapshot()["focus"], f"{expected} focus")
        self.assertEqual([item["text"] for item in resources.reminders_for("A").load_reminders()], [f"{expected} reminder"])
        self.assertIsNone(self.journal.pending("desktop"))


if __name__ == "__main__":
    unittest.main()
