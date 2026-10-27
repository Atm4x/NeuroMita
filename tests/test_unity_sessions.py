from contextlib import nullcontext
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.state_barrier import StateUnavailable
from domain.timeline import JsonDocument, TimelineConflict, InvalidTimelineOperation
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from infrastructure.timeline.restoration import SQLiteRestorationJournal
from infrastructure.timeline.unity_sessions import SQLiteUnitySessions
from services.timeline_runtime import SessionTimelineRuntime
from services.session_restoration import SessionRestoration
from services.unity_sessions import UnitySessions


class Cell:
    key, version = "state", 1
    value = "original"
    def paused(self): return nullcontext()
    def capture(self): return JsonDocument({"value": self.value})
    def validate(self, state):
        if set(state.to_dict()) != {"value"}: raise ValueError("Invalid cell")
    def apply(self, state, *, branch_id): self.value = state.to_dict()["value"]


class UnitySessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.db"
        self.cell = Cell()
        self.restart()

    def restart(self):
        repo = SQLiteTimelineRepository(self.path)
        self.runtime = SessionTimelineRuntime(repo, repo)
        restoration = SessionRestoration(self.runtime, (self.cell,),
            SQLiteRestorationJournal(lambda: sqlite3.connect(self.path)))
        restoration.recover()
        self.store = SQLiteUnitySessions(lambda: sqlite3.connect(self.path))
        self.service = UnitySessions(restoration, self.store)

    def call(self, command, **values):
        with self.runtime.state.bind(self.runtime.state.current_ticket()):
            return self.service.handle(dict(protocol_version=1, command=command, **values))

    def prepare(self, identity, kind="checkpoint", **values):
        snapshot = dict(snapshot_id="world_" + identity, sha256="a" * 64, version=1, scene="CappieHouse")
        return self.call("prepare", operation_id=identity, kind=kind, snapshot=snapshot,
                         expected_branch_id=self.runtime.selection.branch_id, **values)

    def finish(self, identity):
        operation = self.call("commit", operation_id=identity)
        self.call("ack", operation_id=identity)
        return operation

    def test_checkpoint_suspends_admission_until_ack(self):
        self.prepare("save", legacy_save_id="default")
        with self.assertRaises(StateUnavailable): self.runtime.capture()
        self.call("commit", operation_id="save")
        with self.assertRaises(StateUnavailable): self.runtime.capture()
        self.call("ack", operation_id="save")
        self.runtime.capture()
        self.assertEqual(self.call("catalog")["branches"][0]["session_name"], "Песочница")

    def test_repeated_fork_resume_a_b_a_preserves_branch_identity_and_state(self):
        root = self.runtime.selection.branch_id
        self.prepare("fork", "fork", name="Другой мир")
        child = self.finish("fork")["target_branch_id"]
        self.cell.value = "child"
        self.prepare("to-root", "resume", target_branch_id=root)
        self.finish("to-root")
        self.assertEqual(self.cell.value, "original")
        self.cell.value = "root"
        self.prepare("to-child", "resume", target_branch_id=child)
        self.finish("to-child")
        self.assertEqual(self.cell.value, "child")
        self.assertEqual(len(self.runtime.repository.list_branches()), 2)

    def test_restart_after_prepare_keeps_admission_closed_and_can_abort(self):
        self.prepare("save")
        self.restart()
        with self.assertRaises(StateUnavailable): self.runtime.capture()
        self.call("abort", operation_id="save")
        self.runtime.capture()

    def test_restart_after_python_commit_reconciles_without_second_fork(self):
        self.prepare("fork", "fork")
        committed = self.call("commit", operation_id="fork")
        self.restart()
        self.assertEqual(self.call("status", operation_id="fork")["state"], "committed")
        self.assertEqual(self.call("commit", operation_id="fork"), committed)
        self.call("ack", operation_id="fork")
        self.assertEqual(len(self.runtime.repository.list_branches()), 2)

    def test_receipt_rejects_changed_snapshot_and_parallel_operation(self):
        self.prepare("save")
        with self.assertRaises(TimelineConflict): self.prepare("save", label="different")
        with self.assertRaises(TimelineConflict): self.prepare("other")
        self.finish("save")
        self.assertEqual(self.call("commit", operation_id="save")["state"], "complete")

    def test_reject_corruption_and_unknown_target_before_suspending(self):
        with self.assertRaises(InvalidTimelineOperation):
            self.call("prepare", operation_id="bad", kind="checkpoint", expected_branch_id=self.runtime.selection.branch_id,
                      snapshot=dict(snapshot_id="../escape", sha256="x", version=1, scene="test"))
        with self.assertRaises(InvalidTimelineOperation): self.prepare("bad-target", "resume", target_branch_id="missing")
        self.assertFalse(self.runtime.state.poisoned)
        self.assertIsNone(self.store.pending("desktop"))

    def test_new_session_has_independent_identity_and_keeps_original(self):
        initial = self.runtime.timeline.branch.session_id
        self.prepare("new", "new_session", name="История")
        self.finish("new")
        self.assertNotEqual(self.runtime.timeline.branch.session_id, initial)
        self.assertEqual(len(self.runtime.repository.list_branches()), 2)

    def test_applied_transition_cannot_be_aborted(self):
        self.prepare("fork", "fork")
        self.call("commit", operation_id="fork")
        with self.assertRaises(TimelineConflict): self.call("abort", operation_id="fork")


if __name__ == "__main__": unittest.main()
