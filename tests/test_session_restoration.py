from __future__ import annotations

from contextlib import nullcontext
import asyncio
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.state_barrier import StateBarrier, StateUnavailable
from domain.timeline import ConcurrentTimelineWrite, EventKind, JsonDocument, TimelineConflict
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from services.session_restoration import RestorationFailed, SessionRestoration
from services.timeline_runtime import SessionTimelineRuntime


class _Cell:
    version = 1

    def __init__(self, key, value):
        self.key, self.value = key, value
        self.fail = set()

    def paused(self):
        return nullcontext()

    def capture(self):
        return JsonDocument({"value": self.value})

    def validate(self, state):
        if set(state.to_dict()) != {"value"}:
            raise ValueError("Invalid cell")

    def apply(self, state, *, branch_id):
        self.value = state.to_dict()["value"]
        if self.value in self.fail:
            raise RuntimeError("Injected failure after mutation")


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = self.path = Path(self.temp.name) / "world.db"
        repository = SQLiteTimelineRepository(path)
        self.runtime = SessionTimelineRuntime(repository, repository)
        self.journal = SQLiteRestorationJournal(lambda: sqlite3.connect(path))
        self.first = _Cell("first", "saved")
        self.second = _Cell("second", "saved")
        self.coordinator = SessionRestoration(self.runtime, (self.first, self.second), self.journal)

    def test_full_checkpoint_restores_all_participants_and_retains_abandoned_state(self):
        checkpoint = self.runtime.checkpoint(label="save")
        source = self.runtime.selection.branch_id
        turn = self.runtime.capture(character_id="A")
        ticket = self.runtime.state.ticket()
        self.first.value = self.second.value = "future"
        self.runtime.restore(checkpoint.event_id, branch_id="restored")
        self.assertEqual((self.first.value, self.second.value), ("saved", "saved"))
        self.assertEqual(self.runtime.selection.branch_id, "restored")
        with self.assertRaises(ConcurrentTimelineWrite):
            with self.runtime.turn_scope(turn):
                self.fail("Old generation must be rejected")
        with self.runtime.state.bind(ticket), self.assertRaises(StateUnavailable):
            with self.runtime.writing():
                self.fail("Old background state work must be rejected")
        self.assertIsNone(self.journal.pending("desktop"))
        source_events = self.runtime.repository.read(source)
        self.assertEqual(source_events[-1].payload.to_dict()["snapshot"]["participants"]["first"]["state"]["value"], "future")

    def test_failed_participant_is_compensated_and_branch_is_not_activated(self):
        checkpoint = self.runtime.checkpoint()
        source = self.runtime.selection.branch_id
        self.first.value = self.second.value = "future"
        self.second.fail.add("saved")
        with self.assertRaises(RestorationFailed) as failure:
            self.runtime.restore(checkpoint.event_id)
        self.assertFalse(failure.exception.recovery_required)
        self.assertEqual((self.first.value, self.second.value), ("future", "future"))
        self.assertEqual(self.runtime.selection.branch_id, source)
        self.assertIsNone(self.journal.pending("desktop"))

    def test_failed_compensation_blocks_access_until_durable_recovery(self):
        checkpoint = self.runtime.checkpoint()
        self.first.value = self.second.value = "future"
        self.second.fail.update({"saved", "future"})
        with self.assertRaises(RestorationFailed) as failure:
            self.runtime.restore(checkpoint.event_id)
        self.assertTrue(failure.exception.recovery_required)
        self.assertIsNotNone(self.journal.pending("desktop"))
        with self.assertRaises(StateUnavailable):
            with self.runtime.writing():
                self.fail("Incomplete compensation must fail closed")
        self.second.fail.clear()
        self.assertTrue(self.coordinator.recover())
        self.assertEqual((self.first.value, self.second.value), ("future", "future"))
        self.assertIsNone(self.journal.pending("desktop"))
        with self.runtime.writing():
            pass

    def test_checkpoint_does_not_invalidate_background_tickets(self):
        ticket = self.runtime.state.ticket()
        self.runtime.checkpoint()
        with self.runtime.state.bind(ticket), self.runtime.writing():
            pass

    def test_named_checkpoint_retry_returns_the_original_capture_after_state_advances(self):
        checkpoint = self.runtime.checkpoint(key="save-command", label="Named")
        self.first.value = "later"
        head = self.runtime.timeline.branch.head_sequence
        self.assertEqual(self.runtime.checkpoint(key="save-command", label="Named"), checkpoint)
        self.assertEqual(self.runtime.timeline.branch.head_sequence, head)
        with self.assertRaises(TimelineConflict):
            self.runtime.checkpoint(key="save-command", label="Different")

    def test_snapshot_from_another_retained_branch_can_restore_the_abandoned_future(self):
        checkpoint = self.runtime.checkpoint()
        source = self.runtime.selection.branch_id
        self.first.value = self.second.value = "future"
        self.runtime.restore(checkpoint.event_id)
        previous = self.runtime.repository.read(source)[-1]
        self.runtime.restore(previous.event_id, checkpoint_branch_id=source)
        self.assertEqual((self.first.value, self.second.value), ("future", "future"))

    def test_raw_branch_switching_cannot_bypass_registered_state_owners(self):
        with self.assertRaises(RuntimeError):
            self.runtime.activate(self.runtime.selection.branch_id)
        with self.assertRaises(ValueError):
            self.runtime.start_session()

    def test_new_session_has_explicit_initial_state_and_presence_without_inheriting_conversation(self):
        self.runtime.timeline.join("A", key="present")
        self.runtime.timeline.publish(EventKind.PLAYER_MESSAGE, {"content": "old conversation"},
                                      actor_id="Player", observers=("A",), key="old")
        self.first.value = "carried state"
        original = self.runtime.selection.branch_id
        new = self.runtime.start_session(inherit_current=True)
        self.assertEqual(self.runtime.selection.branch_id, new.branch_id)
        self.assertNotEqual(new.branch_id, original)
        self.assertIsNone(new.branch.parent_branch_id)
        self.assertEqual(new.present(), frozenset({"A"}))
        self.assertEqual(new.messages("A"), ())
        self.assertEqual(self.first.value, "carried state")
        self.assertEqual(tuple(new.events())[-1].kind, EventKind.CHECKPOINT)

    def test_new_session_can_initialize_from_a_saved_snapshot(self):
        checkpoint = self.runtime.checkpoint()
        initial = JsonDocument(checkpoint.payload.to_dict()["snapshot"])
        self.first.value = "future"
        new = self.runtime.start_session(initial_snapshot=initial)
        self.assertEqual(self.first.value, "saved")
        self.assertIsNone(new.branch.parent_branch_id)

    def test_obsolete_bound_operation_cannot_start_a_restore(self):
        checkpoint = self.runtime.checkpoint()
        ticket = self.runtime.state.ticket()
        self.runtime.restore(checkpoint.event_id)
        with self.runtime.state.bind(ticket), self.assertRaises(StateUnavailable):
            self.runtime.restore(checkpoint.event_id)

    def test_failed_preflight_does_not_invalidate_other_state_work(self):
        checkpoint = self.runtime.timeline.checkpoint({}, key="not-full")
        ticket = self.runtime.state.ticket()
        selection = self.runtime.selection
        with self.assertRaises(ValueError):
            self.runtime.restore(checkpoint.event_id)
        self.assertEqual(self.runtime.state.ticket(), ticket)
        self.assertEqual(self.runtime.selection, selection)

    def test_journal_admission_failure_does_not_poison_unchanged_state(self):
        checkpoint = self.runtime.checkpoint()
        self.first.value = self.second.value = "future"
        with patch.object(self.journal, "begin", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.runtime.restore(checkpoint.event_id)
        self.assertFalse(self.runtime.state.poisoned)
        self.assertEqual((self.first.value, self.second.value), ("future", "future"))

    def test_completion_failure_recovers_the_applied_target_instead_of_the_abandoned_source(self):
        checkpoint = self.runtime.checkpoint()
        self.first.value = self.second.value = "future"
        with patch.object(self.journal, "complete", side_effect=OSError("disk full")):
            with self.assertRaises(RestorationFailed):
                self.runtime.restore(checkpoint.event_id, branch_id="target")
        self.assertEqual(self.runtime.selection.branch_id, "target")
        self.assertTrue(self.runtime.state.poisoned)
        self.assertTrue(self.coordinator.recover())
        self.assertEqual((self.first.value, self.second.value), ("saved", "saved"))
        self.assertFalse(self.runtime.state.poisoned)

    def test_uncertain_admission_is_resolved_from_the_retained_journal(self):
        checkpoint = self.runtime.checkpoint()
        self.first.value = self.second.value = "future"
        begin = self.journal.begin

        def uncertain(operation):
            begin(operation)
            raise OSError("Response lost after commit")

        with patch.object(self.journal, "begin", side_effect=uncertain):
            with self.assertRaises(RestorationFailed):
                self.runtime.restore(checkpoint.event_id)
        self.assertTrue(self.runtime.state.poisoned)
        self.assertTrue(self.coordinator.recover())
        self.assertEqual((self.first.value, self.second.value), ("future", "future"))

    def test_new_runtime_recovers_the_durable_source_after_incomplete_compensation(self):
        checkpoint = self.runtime.checkpoint()
        source = self.runtime.selection.branch_id
        self.first.value = self.second.value = "future"
        self.second.fail.update({"saved", "future"})
        with self.assertRaises(RestorationFailed):
            self.runtime.restore(checkpoint.event_id)
        self._recover_with_new_owners(source, "future")

    def test_new_runtime_recovers_the_durable_target_after_lost_completion(self):
        checkpoint = self.runtime.checkpoint()
        self.first.value = self.second.value = "future"
        with patch.object(self.journal, "complete", side_effect=OSError("disk full")):
            with self.assertRaises(RestorationFailed):
                self.runtime.restore(checkpoint.event_id, branch_id="restored")
        self._recover_with_new_owners("restored", "saved")

    def _recover_with_new_owners(self, branch, value):
        repository = SQLiteTimelineRepository(self.path)
        runtime = SessionTimelineRuntime(repository, repository)
        journal = SQLiteRestorationJournal(lambda: sqlite3.connect(self.path))
        pending = journal.pending("desktop")
        journal.begin(pending)
        journal.begin(pending)
        first, second = _Cell("first", "process default"), _Cell("second", "process default")
        coordinator = SessionRestoration(runtime, (first, second), journal)
        self.assertTrue(coordinator.recover())
        self.assertEqual(runtime.selection.branch_id, branch)
        self.assertEqual((first.value, second.value), (value, value))
        self.assertIsNone(journal.pending("desktop"))
        self.assertFalse(coordinator.recover())

    def test_uncertain_completion_can_unblock_when_storage_confirms_no_pending_transition(self):
        checkpoint = self.runtime.checkpoint()
        complete = self.journal.complete

        def uncertain(identity):
            complete(identity)
            raise OSError("Response lost after commit")

        with patch.object(self.journal, "complete", side_effect=uncertain):
            with self.assertRaises(RestorationFailed):
                self.runtime.restore(checkpoint.event_id)
        self.assertTrue(self.runtime.state.poisoned)
        self.assertFalse(self.coordinator.recover())
        self.assertFalse(self.runtime.state.poisoned)

    def test_exclusive_state_drains_active_work_without_holding_runtime_locks(self):
        barrier = StateBarrier()
        entered, release, restored = Event(), Event(), Event()

        def active():
            with barrier.access():
                entered.set()
                release.wait(2)

        def restore():
            with barrier.exclusive(invalidate=True):
                restored.set()

        worker = Thread(target=active)
        worker.start()
        self.assertTrue(entered.wait(1))
        restorer = Thread(target=restore)
        restorer.start()
        self.assertFalse(restored.wait(.05))
        release.set()
        worker.join(2)
        restorer.join(2)
        self.assertTrue(restored.is_set())

    def test_completed_model_write_waits_for_a_checkpoint_capture_without_losing_its_turn(self):
        written = Event()
        errors = []

        def complete():
            try:
                with self.runtime.writing():
                    written.set()
            except BaseException as exc:
                errors.append(exc)

        with self.runtime.state.exclusive():
            worker = Thread(target=complete)
            worker.start()
            self.assertFalse(written.wait(.05))
        worker.join(2)
        self.assertTrue(written.is_set())
        self.assertEqual(errors, [])

    def test_async_child_cannot_inherit_its_parents_active_access_depth(self):
        barrier = StateBarrier()
        started, release = Event(), Event()

        def transition():
            with barrier.exclusive():
                started.set()
                release.wait(2)

        async def child():
            self.assertTrue(await asyncio.to_thread(started.wait, 1))
            with self.assertRaises(StateUnavailable):
                with barrier.access():
                    self.fail("A copied context is not a nested state operation")

        async def scenario():
            with barrier.access():
                pending = asyncio.create_task(child())
            worker = Thread(target=transition)
            worker.start()
            try:
                await pending
            finally:
                release.set()
                worker.join(2)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
