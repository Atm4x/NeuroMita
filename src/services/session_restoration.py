from __future__ import annotations

from contextlib import ExitStack
from typing import Iterable

from domain.timeline import EventKind, InvalidTimelineOperation, JsonDocument, TimelineConflict, new_id
from domain.timeline.models import observer_ids
from domain.timeline.restoration import PendingRestore, RestorationJournal, SnapshotParticipant
from core.state_barrier import StateUnavailable
from .session_timeline import SessionTimeline
from .timeline_runtime import SessionTimelineRuntime


class RestorationFailed(RuntimeError):
    """A restore failed; recovery_required distinguishes an incomplete rollback."""

    def __init__(self, message: str, *, recovery_required: bool):
        super().__init__(message)
        self.recovery_required = recovery_required


class SessionRestoration:
    """Coordinate explicit state owners and activate a branch only after success."""

    def __init__(self, runtime: SessionTimelineRuntime, participants: Iterable[SnapshotParticipant],
                 journal: RestorationJournal):
        self.runtime = runtime
        self.participants = tuple(participants)
        self.journal = journal
        keys = [participant.key for participant in self.participants]
        if not keys or any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("Snapshot participants require unique, nonempty keys")
        if any(type(participant.version) is not int or participant.version < 1 for participant in self.participants):
            raise ValueError("Snapshot participants require positive integer versions")
        self.runtime.restoration = self

    def _capture(self) -> JsonDocument:
        return JsonDocument({"snapshot_version": 1, "presence": sorted(self.runtime.timeline.present()), "participants": {
            participant.key: {"version": participant.version, "state": participant.capture().to_dict()}
            for participant in self.participants
        }})

    def _validate(self, snapshot: JsonDocument) -> dict[str, JsonDocument]:
        data = snapshot.to_dict()
        if (set(data) != {"snapshot_version", "presence", "participants"}
                or type(data.get("snapshot_version")) is not int or data["snapshot_version"] != 1):
            raise InvalidTimelineOperation("A full restore requires a supported session snapshot")
        presence = data["presence"]
        if not isinstance(presence, list) or len(observer_ids(presence)) != len(presence):
            raise InvalidTimelineOperation("Invalid initial scene presence")
        components = data.get("participants")
        if not isinstance(components, dict) or set(components) != {participant.key for participant in self.participants}:
            raise InvalidTimelineOperation("Snapshot participants differ from the active application")
        states = {}
        for participant in self.participants:
            component = components[participant.key]
            if (not isinstance(component, dict) or set(component) != {"version", "state"}
                    or type(component.get("version")) is not int or component["version"] != participant.version
                    or not isinstance(component["state"], dict)):
                raise InvalidTimelineOperation(f"Unsupported snapshot for {participant.key}")
            state = JsonDocument(component.get("state"))
            participant.validate(state)
            states[participant.key] = state
        return states

    def _paused(self, stack: ExitStack):
        for participant in self.participants:
            stack.enter_context(participant.paused())

    def checkpoint(self, *, key: str | None = None, label: str = ""):
        if self.runtime.turn is not None:
            raise InvalidTimelineOperation("Full snapshot coordination must run outside a model turn")
        with self.runtime.state.exclusive(), ExitStack() as stack:
            if self.journal.pending(self.runtime.workspace_name) is not None:
                raise StateUnavailable("An unfinished restore must be recovered first")
            operation_key = f"session-save:{key or new_id()}"
            command = JsonDocument({"operation": "capture-session", "label": label})
            receipt = self.runtime.repository.receipt(self.runtime.selection.branch_id, operation_key)
            if receipt is not None:
                if receipt.command != command or len(receipt.events) != 1 or receipt.events[0].kind is not EventKind.CHECKPOINT:
                    raise TimelineConflict("Session checkpoint key was reused for a different command")
                return receipt.events[0]
            self._paused(stack)
            snapshot = self._capture()
            self._validate(snapshot)
            with self.runtime.writing() as timeline:
                draft = timeline.draft(EventKind.CHECKPOINT, {"snapshot": snapshot.to_dict(), "label": label},
                                       observers=(), key=operation_key)
                return timeline.append((draft,), expected_head=timeline.branch.head_sequence,
                                       key=operation_key, command=command)[0]

    def restore(self, checkpoint_id: str, *, branch_id: str | None = None,
                checkpoint_branch_id: str | None = None) -> JsonDocument:
        if self.runtime.turn is not None:
            raise InvalidTimelineOperation("Full snapshot coordination must run outside a model turn")
        with self.runtime.state.exclusive():
            if self.journal.pending(self.runtime.workspace_name) is not None:
                raise StateUnavailable("An unfinished restore must be recovered first")
            source = SessionTimeline(self.runtime.repository, self.runtime.selection.branch_id)
            checkpoint_world = SessionTimeline(self.runtime.repository, checkpoint_branch_id or source.branch_id)
            checkpoint = checkpoint_world.event(checkpoint_id)
            if checkpoint.kind is not EventKind.CHECKPOINT:
                raise InvalidTimelineOperation("Restore target must be a checkpoint")
            desired = JsonDocument(checkpoint.payload.to_dict().get("snapshot"))
            states = self._validate(desired)
            if frozenset(desired.to_dict()["presence"]) != checkpoint_world.present(through=checkpoint.sequence):
                raise InvalidTimelineOperation("Snapshot presence differs from its checkpoint world")
            child = checkpoint_world.fork(checkpoint_id, branch_id=branch_id or new_id()).timeline
            if child.branch.head_sequence != child.branch.fork_sequence + 1:
                raise InvalidTimelineOperation("A restore cannot overwrite an already advanced child branch")
            return self._transition(source, child, desired, states)

    def start_session(self, *, initial_snapshot: JsonDocument | None = None, inherit_current: bool = False,
                      session_id: str | None = None, branch_id: str | None = None) -> SessionTimeline:
        if self.runtime.turn is not None:
            raise InvalidTimelineOperation("Session initialization must run outside a model turn")
        if (initial_snapshot is None) == (not inherit_current):
            raise InvalidTimelineOperation("Choose one initial-state policy: initial_snapshot or inherit_current=True")
        with self.runtime.state.exclusive():
            if self.journal.pending(self.runtime.workspace_name) is not None:
                raise StateUnavailable("An unfinished restore must be recovered first")
            states = self._validate(initial_snapshot) if initial_snapshot is not None else None
            source = SessionTimeline(self.runtime.repository, self.runtime.selection.branch_id)
            target = SessionTimeline.create(self.runtime.repository, session_id=session_id, branch_id=branch_id)
            if target.branch_id == source.branch_id or target.branch.head_sequence:
                raise TimelineConflict("Session initialization cannot overwrite an existing world")
            self._transition(source, target, initial_snapshot, states)
            return target

    @staticmethod
    def _initialize_world(target: SessionTimeline, snapshot: JsonDocument):
        presence = snapshot.to_dict()["presence"]
        drafts = [target.draft(EventKind.CHARACTER_JOINED, actor_id=identity, observers=presence,
                                key=f"initial-presence:{identity}") for identity in presence]
        if drafts:
            target.append(drafts, expected_head=0, key="initial-presence")
        target.checkpoint(snapshot.to_dict(), key="initial-state", label="Initial session state")

    def _transition(self, source, target, desired, states):
        operation = None
        failure = None
        try:
            with ExitStack() as stack:
                self._paused(stack)
                before = self._capture()
                rollback = self._validate(before)
                if desired is None:
                    desired, states = before, rollback
                if target.branch.head_sequence == 0:
                    self._initialize_world(target, desired)
                operation_id = new_id()
                source.checkpoint(before.to_dict(), key=f"restore-origin:{operation_id}", label="Before restore")
                pending = PendingRestore(operation_id, self.runtime.workspace_name, source.branch_id,
                                         target.branch_id, before, desired)
                try:
                    self.journal.begin(pending)
                except BaseException as admission_error:
                    try:
                        retained = self.journal.pending(self.runtime.workspace_name)
                    except BaseException:
                        retained = pending
                    if retained is not None:
                        operation = retained
                        self.runtime.state.poison("Restore journal admission is uncertain; recovery is required")
                        raise RestorationFailed("Restore journal admission requires recovery", recovery_required=True) from admission_error
                    raise
                operation = pending
                try:
                    self.runtime.state.invalidate()
                    self.runtime.activate(source.branch_id)
                    for participant in self.participants:
                        participant.apply(states[participant.key], branch_id=target.branch_id)
                    self.runtime.activate(target.branch_id)
                except BaseException as exc:
                    self.runtime.state.invalidate()
                    failures = []
                    for participant in self.participants:
                        try:
                            participant.apply(rollback[participant.key], branch_id=source.branch_id)
                        except BaseException as rollback_error:
                            failures.append(rollback_error)
                    if not failures and self.runtime.selection.branch_id != source.branch_id:
                        try:
                            self.runtime.activate(source.branch_id)
                        except BaseException as selection_error:
                            failures.append(selection_error)
                    if failures:
                        self.runtime.state.poison("Session rollback failed; recovery is required")
                        raise RestorationFailed("Session restore failed; rollback is incomplete", recovery_required=True) from exc
                    failure = exc
            self.journal.complete(operation.operation_id)
        except BaseException as exc:
            if operation is not None:
                self.runtime.state.poison("Session restore did not finish; journal recovery is required")
                raise RestorationFailed("Session restore requires journal recovery", recovery_required=True) from exc
            raise
        if failure is not None:
            raise RestorationFailed("Session restore failed; previous state restored", recovery_required=False) from failure
        return desired

    def recover(self) -> bool:
        if self.runtime.turn is not None:
            raise InvalidTimelineOperation("Session recovery must run outside a model turn")
        with self.runtime.state.exclusive():
            pending = self.journal.pending(self.runtime.workspace_name)
            if pending is None:
                self.runtime.state.recovered()
                return False
            selection = self.runtime.selection
            if selection.branch_id not in {pending.source_branch_id, pending.target_branch_id}:
                self.runtime.state.poison("Recovery cannot infer an externally changed branch selection")
                raise StateUnavailable("Recovery branch selection differs from the restore journal")
            try:
                snapshot = pending.desired if selection.branch_id == pending.target_branch_id else pending.before
                states = self._validate(snapshot)
                with ExitStack() as stack:
                    self._paused(stack)
                    self.runtime.state.invalidate()
                    self.runtime.activate(selection.branch_id)
                    for participant in self.participants:
                        participant.apply(states[participant.key], branch_id=selection.branch_id)
                    self.runtime.state.recovered()
                self.journal.complete(pending.operation_id)
            except BaseException:
                self.runtime.state.poison("Session recovery failed; application state remains unavailable")
                raise
            return True
