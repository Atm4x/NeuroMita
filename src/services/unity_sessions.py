from __future__ import annotations

from dataclasses import asdict
from contextvars import ContextVar
import re
from threading import RLock, get_ident
from uuid import NAMESPACE_URL, uuid5

from domain.timeline import EventKind, InvalidTimelineOperation, TimelineConflict
from core.state_barrier import StateUnavailable


class UnitySessions:
    """A durable handshake around the existing Python restoration coordinator."""

    def __init__(self, restoration, store):
        self.restoration, self.store = restoration, store
        self.runtime = restoration.runtime
        self._lock = RLock()
        self._control_owner = ContextVar("unity_session_control", default=None)
        self.restoration.transition_guard = self._admit_restoration
        if store.pending(self.runtime.workspace_name):
            self.runtime.state.poison("Unity session transition requires reconciliation")

    @staticmethod
    def _identity(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", value):
            raise InvalidTimelineOperation("Invalid operation identity")
        return value

    @staticmethod
    def _name(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            raise InvalidTimelineOperation("A name must contain 1 to 120 characters")
        return value.strip()

    @staticmethod
    def _snapshot(value):
        if (not isinstance(value, dict) or set(value) != {"snapshot_id", "sha256", "version", "scene"}
                or type(value["version"]) is not int or value["version"] != 1
                or not isinstance(value["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", value["sha256"])
                or not isinstance(value["scene"], str) or not value["scene"] or len(value["scene"]) > 240):
            raise InvalidTimelineOperation("Unsupported Unity snapshot descriptor")
        UnitySessions._identity(value["snapshot_id"])
        return dict(value)

    def _admit_restoration(self):
        if self._control_owner.get() != get_ident() and self.store.pending(self.runtime.workspace_name):
            raise StateUnavailable("A joint Unity transition owns session restoration")

    def handle(self, request):
        token = self._control_owner.set(get_ident())
        try:
            return self._handle(request)
        finally:
            self._control_owner.reset(token)

    def _handle(self, request):
        if request.get("protocol_version") != 1:
            raise InvalidTimelineOperation("Unsupported Unity session protocol")
        with self._lock:
            command = request.get("command")
            if command == "catalog":
                return self.catalog()
            if command == "rename":
                if self.store.pending(self.runtime.workspace_name):
                    raise TimelineConflict("Finish the pending transition first")
                identity = request.get("identity")
                if identity not in {item for b in self.runtime.repository.list_branches()
                                    for item in (b.session_id, b.branch_id)}:
                    raise InvalidTimelineOperation("Unknown session or branch")
                self.store.rename(identity, self._name(request.get("name")))
                return self.catalog()
            operation_id = self._identity(request.get("operation_id"))
            operation = self.store.operation(operation_id)
            if command == "reconnect":
                return self._reconnect(operation_id, request, operation)
            if command == "prepare":
                return self._prepare(operation_id, request, operation)
            if operation is None:
                if command == "status":
                    return {"operation_id": operation_id, "state": "unknown"}
                raise InvalidTimelineOperation("Unknown Unity operation")
            if command == "status":
                return operation
            if command == "commit":
                return self._commit(operation)
            if command == "abort":
                return self._abort(operation)
            if command == "ack":
                if operation["state"] not in {"committed", "complete", "aborted"}:
                    raise TimelineConflict("Only a committed transition can be acknowledged")
                if operation["state"] == "committed":
                    operation["state"] = "complete"
                    self.store.put_operation(operation)
                if self.store.pending(self.runtime.workspace_name) is None:
                    with self.runtime.state.exclusive():
                        self.runtime.state.recovered()
                return operation
            raise InvalidTimelineOperation("Unknown Unity session command")

    def _reconnect(self, operation_id, request, operation):
        intent = {key: value for key, value in request.items() if key not in {"req_id", "action", "client_role"}}
        if operation:
            if operation["intent"] != intent:
                raise TimelineConflict("Operation identity was reused for another intent")
            return operation
        if self.store.pending(self.runtime.workspace_name) or self.runtime.state.poisoned:
            raise TimelineConflict("Recover the pending operation first")
        branch = self.runtime.timeline.branch
        if request.get("expected_branch_id") != branch.branch_id:
            raise TimelineConflict("The saved world belongs to another active branch")
        snapshot = self._snapshot(request.get("snapshot"))
        checkpoints = self.store.checkpoints(branch.branch_id)
        target = next((item for item in checkpoints if item["snapshot"] == snapshot), None)
        if target is None:
            raise InvalidTimelineOperation("The saved world has no joint Python checkpoint")
        kind = request.get("kind", "resume")
        if kind not in {"resume", "fork"}:
            raise InvalidTimelineOperation("Reconnect requires resume or fork")
        if kind == "resume" and any(event.kind is not EventKind.CHECKPOINT for event in
                self.runtime.timeline.events(after=target["sequence"])):
            raise InvalidTimelineOperation("The last saved world precedes later events; fork it to retain that future")
        target_branch = branch.branch_id if kind == "resume" else uuid5(NAMESPACE_URL, "unity-branch:" + operation_id).hex
        operation = {"operation_id": operation_id, "workspace": self.runtime.workspace_name, "state": "prepared",
                     "intent": intent, "kind": kind, "reconnect": True, "source_branch_id": branch.branch_id,
                     "target_branch_id": target_branch, "target_session_id": branch.session_id,
                     "source_snapshot": snapshot, "source": target, "target": target}
        with self.runtime.state.exclusive():
            self.store.put_operation(operation)
            self.runtime.state.invalidate()
            self.runtime.state.poison("Saved Unity world is being reconnected")
        return operation

    def catalog(self):
        names = self.store.names()
        branches = []
        for branch in self.runtime.repository.list_branches():
            row = asdict(branch)
            row.update(name=names.get(branch.branch_id, "Основная ветка" if branch.parent_branch_id is None else "Ответвление"),
                       session_name=names.get(branch.session_id, "История"),
                       checkpoints=self.store.checkpoints(branch.branch_id))
            branches.append(row)
        return {"branches": branches, "active_branch_id": self.runtime.selection.branch_id,
                "pending": self.store.pending(self.runtime.workspace_name)}

    def _prepare(self, operation_id, request, operation):
        intent = {key: value for key, value in request.items() if key not in {"req_id", "action", "client_role"}}
        if operation:
            if operation["intent"] != intent:
                raise TimelineConflict("Operation identity was reused for another intent")
            if operation["state"] != "preparing":
                return operation
        else:
            if self.runtime.state.poisoned or self.store.pending(self.runtime.workspace_name):
                raise TimelineConflict("Recover the pending transition first")
            source = self.runtime.timeline.branch
            if request.get("expected_branch_id") != source.branch_id:
                raise TimelineConflict("The active Python branch differs from Unity")
            kind = request.get("kind")
            if kind not in {"checkpoint", "fork", "resume", "new_session"}:
                raise InvalidTimelineOperation("Unsupported transition kind")
            snapshot = self._snapshot(request.get("snapshot"))
            if request.get("name") is not None:
                self._name(request["name"])
            legacy = request.get("legacy_save_id")
            if legacy:
                self._identity(legacy)
                bound = self.store.legacy_branch(legacy)
                if bound and bound != source.branch_id:
                    raise TimelineConflict("This legacy save belongs to another Python branch")
            target_branch = source.branch_id
            target_session = source.session_id
            target = None
            if kind in {"fork", "resume"}:
                selected = request.get("target_branch_id") or source.branch_id
                checkpoints = self.store.checkpoints(selected)
                selected_id = request.get("checkpoint_id")
                target = next((c for c in checkpoints if not selected_id or c["checkpoint_id"] == selected_id), None)
                if kind == "resume" and (target is None or selected_id and target != checkpoints[0]):
                    raise InvalidTimelineOperation("Resume requires the last joint checkpoint of a branch")
                if kind == "fork" and selected_id and target is None:
                    raise InvalidTimelineOperation("Unknown joint checkpoint")
                if target:
                    target_session = self.runtime.repository.get_branch(target["branch_id"]).session_id
                if kind == "resume":
                    target_branch = selected
                    target_session = self.runtime.repository.get_branch(selected).session_id
            if kind in {"fork", "new_session"}:
                target_branch = uuid5(NAMESPACE_URL, "unity-branch:" + operation_id).hex
            if kind == "new_session":
                target_session = uuid5(NAMESPACE_URL, "unity-session:" + operation_id).hex
            operation = {"operation_id": operation_id, "workspace": self.runtime.workspace_name,
                         "state": "preparing", "intent": intent, "kind": kind,
                         "source_branch_id": source.branch_id, "target_branch_id": target_branch,
                         "target_session_id": target_session, "source_snapshot": snapshot, "target": target}
            self.store.put_operation(operation)
        checkpoint = self.restoration.checkpoint(key="unity:" + operation_id,
            label=str(request.get("label") or "Контрольная точка")[:120],
            suspend_reason="Unity session operation awaits confirmation",
            expected_branch_id=operation["source_branch_id"])
        source = {"checkpoint_id": checkpoint.event_id, "branch_id": checkpoint.branch_id,
                  "sequence": checkpoint.sequence, "label": checkpoint.payload.to_dict()["label"],
                  "snapshot": operation["source_snapshot"]}
        self.store.put_checkpoint(source)
        operation["source"] = source
        if operation["target"] is None or (operation["kind"] == "fork" and not request.get("checkpoint_id")):
            operation["target"] = source
        operation["state"] = "prepared"
        self.store.put_operation(operation)
        legacy = request.get("legacy_save_id")
        if legacy:
            self.store.bind_legacy(self._identity(legacy), source["branch_id"])
            branch = self.runtime.repository.get_branch(source["branch_id"])
            if legacy == "default" and branch.session_id not in self.store.names():
                self.store.rename(branch.session_id, "Песочница")
        return operation

    def _commit(self, operation):
        if operation["state"] in {"committed", "complete"}:
            return operation
        if operation["state"] not in {"prepared", "applying"}:
            raise TimelineConflict("Transition is not prepared")
        operation["state"] = "applying"
        self.store.put_operation(operation)
        kind = operation["kind"]
        target = operation["target"]
        branch_id = operation["target_branch_id"]
        if self.runtime.selection.branch_id not in {operation["source_branch_id"], branch_id}:
            raise TimelineConflict("Selection differs from the pending transition")
        if kind == "checkpoint":
            pass
        elif self.runtime.selection.branch_id == branch_id and kind != "resume":
            pass  # Python journal recovery already committed this selection.
        elif kind == "fork":
            self.restoration.restore(target["checkpoint_id"], branch_id=branch_id,
                                     checkpoint_branch_id=target["branch_id"])
        elif kind == "resume":
            self.restoration.resume_branch(branch_id, target["checkpoint_id"])
        else:
            self.restoration.start_session(inherit_current=True, session_id=operation["target_session_id"], branch_id=branch_id)
        if kind in {"fork", "new_session"}:
            with self.runtime.state.bind(self.runtime.state.current_ticket()):
                checkpoint = self.restoration.checkpoint(key="unity-target:" + operation["operation_id"], label="Начало ветки")
            self.store.put_checkpoint({"checkpoint_id": checkpoint.event_id, "branch_id": branch_id,
                "sequence": checkpoint.sequence, "label": "Начало ветки", "snapshot": target["snapshot"]})
            self.store.rename(branch_id, self._name(operation["intent"].get("name") or "Ответвление"))
            if kind == "new_session":
                self.store.rename(operation["target_session_id"], self._name(operation["intent"].get("name") or "Новая история"))
        operation["state"] = "committed"
        self.store.put_operation(operation)
        return operation

    def _abort(self, operation):
        if operation["state"] == "aborted":
            return operation
        if operation["state"] not in {"prepared", "preparing"}:
            raise TimelineConflict("An applied transition must be completed, not cancelled")
        if "source" in operation and not operation.get("reconnect"):
            self.restoration.resume_branch(operation["source_branch_id"], operation["source"]["checkpoint_id"])
        operation["state"] = "aborted"
        self.store.put_operation(operation)
        with self.runtime.state.bind(self.runtime.state.current_ticket()), self.runtime.state.exclusive():
            self.runtime.state.recovered()
        return operation
