from __future__ import annotations

from dataclasses import dataclass
import base64

from .errors import InvalidTimelineOperation
from .models import Branch, CausalLink, CausalRelation, EventDraft, EventKind, JsonDocument, TimelineEvent, require_id
from .rules import HISTORY_KINDS, validate_event
from .assets import TimelineAsset, asset_references


@dataclass(frozen=True, slots=True)
class OperationArchive:
    branch_id: str
    key: str
    intent: JsonDocument
    event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionArchive:
    session_id: str
    root_branch_id: str
    branches: tuple[Branch, ...]
    events: tuple[TimelineEvent, ...]
    operations: tuple[OperationArchive, ...] = ()
    assets: tuple[TimelineAsset, ...] = ()

    def to_document(self) -> JsonDocument:
        return JsonDocument({
            "archive_version": 1, "session_id": self.session_id, "root_branch_id": self.root_branch_id,
            "branches": [{key: getattr(branch, key) for key in (
                "branch_id", "session_id", "parent_branch_id", "fork_sequence", "head_sequence", "checkpoint_id",
            )} for branch in self.branches],
            "events": [{
                "session_id": event.session_id, "branch_id": event.branch_id, "sequence": event.sequence,
                "occurred_at": event.occurred_at, **draft_from_event(event).intent(),
            } for event in self.events],
            "operations": [{"branch_id": operation.branch_id, "key": operation.key,
                            "intent": operation.intent.to_dict(), "event_ids": list(operation.event_ids)}
                           for operation in self.operations],
            "assets": [{"asset_id": asset.asset_id, "media_type": asset.media_type,
                        "base64": base64.b64encode(asset.data).decode("ascii")} for asset in self.assets],
        })

    @classmethod
    def from_document(cls, document: JsonDocument) -> SessionArchive:
        data = document.to_dict()
        if type(data.get("archive_version")) is not int or data["archive_version"] != 1:
            raise InvalidTimelineOperation("Unsupported session archive version")
        try:
            branches = tuple(Branch(**branch) for branch in data["branches"])
            events = []
            for event in data["events"]:
                draft = EventDraft(
                    kind=EventKind(event["kind"]), payload=JsonDocument(event["payload"]),
                    actor_id=event["actor_id"], observers=event["observers"],
                    links=tuple(CausalLink(CausalRelation(relation), target) for relation, target in event["links"]),
                    event_id=event["event_id"], occurred_at=event["occurred_at"],
                    schema_version=event["schema_version"],
                )
                events.append(TimelineEvent(
                    draft.event_id, event["session_id"], event["branch_id"], event["sequence"],
                    draft.kind, draft.payload, draft.actor_id, draft.observers, draft.links,
                    draft.occurred_at, draft.schema_version,
                ))
            operations = tuple(OperationArchive(
                operation["branch_id"], operation["key"], JsonDocument(operation["intent"]), tuple(operation["event_ids"]),
            ) for operation in data.get("operations", ()))
            assets = tuple(TimelineAsset(asset["asset_id"], asset["media_type"],
                                         base64.b64decode(asset["base64"], validate=True)) for asset in data.get("assets", ()))
            archive = cls(data["session_id"], data["root_branch_id"], branches, tuple(events), operations, assets)
            validate_archive(archive)
            return archive
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTimelineOperation("Malformed session archive") from exc


def draft_from_event(event: TimelineEvent) -> EventDraft:
    return EventDraft(event.kind, event.payload, event.actor_id, event.observers, event.links,
                      event.event_id, event.occurred_at, event.schema_version)


def validate_archive(archive: SessionArchive) -> tuple[Branch, ...]:
    """Certify one self-contained semantic world before touching destination storage."""
    require_id(archive.session_id, "session_id")
    require_id(archive.root_branch_id, "root_branch_id")
    branches = {branch.branch_id: branch for branch in archive.branches}
    events = {event.event_id: event for event in archive.events}
    assets = {asset.asset_id: asset for asset in archive.assets}
    if len(assets) != len(archive.assets):
        raise InvalidTimelineOperation("Duplicate archive attachments")
    for asset in assets.values():
        asset.validate()
    for event in archive.events:
        for reference in asset_references(event.payload.to_dict()).values():
            asset = assets.get(reference["asset_id"])
            if asset is None or asset.media_type != reference["media_type"] or len(asset.data) != reference["byte_size"]:
                raise InvalidTimelineOperation("Archive attachment closure is incomplete")
    if len(branches) != len(archive.branches) or len(events) != len(archive.events):
        raise InvalidTimelineOperation("Duplicate archive identities")
    root = branches.get(archive.root_branch_id)
    if root is None or root.parent_branch_id is not None or root.fork_sequence != 0 or root.checkpoint_id is not None:
        raise InvalidTimelineOperation("Invalid session root")
    ordered = []
    pending = dict(branches)
    while pending:
        ready = [branch for branch in pending.values()
                 if branch.branch_id == archive.root_branch_id or
                 any(parent.branch_id == branch.parent_branch_id for parent in ordered)]
        if not ready:
            raise InvalidTimelineOperation("Archive branches contain a cycle or missing parent")
        for branch in sorted(ready, key=lambda item: item.branch_id):
            require_id(branch.branch_id, "branch_id")
            if (branch.session_id != archive.session_id or type(branch.fork_sequence) is not int
                    or type(branch.head_sequence) is not int or not 0 <= branch.fork_sequence <= branch.head_sequence):
                raise InvalidTimelineOperation("Invalid branch sequence bounds")
            if branch is not root and branch.parent_branch_id is None:
                raise InvalidTimelineOperation("A session has exactly one root")
            ordered.append(branch)
            del pending[branch.branch_id]
    local = {branch.branch_id: [] for branch in ordered}
    for event in archive.events:
        if event.branch_id not in branches or event.session_id != archive.session_id or type(event.sequence) is not int:
            raise InvalidTimelineOperation("An event belongs to a different world")
        draft_from_event(event)
        local[event.branch_id].append(event)
    worlds = {}
    for branch in ordered:
        if branch.parent_branch_id is None:
            world = []
        else:
            parent = worlds[branch.parent_branch_id]
            world = [event for event in parent if event.sequence <= branch.fork_sequence]
            checkpoint = next((event for event in world if event.event_id == branch.checkpoint_id), None)
            if checkpoint is None or checkpoint.kind is not EventKind.CHECKPOINT or checkpoint.sequence != branch.fork_sequence:
                raise InvalidTimelineOperation("Fork does not identify an inherited checkpoint")
        additions = sorted(local[branch.branch_id], key=lambda event: event.sequence)
        if len(additions) != branch.head_sequence - branch.fork_sequence or any(
            event.sequence != branch.fork_sequence + index for index, event in enumerate(additions, 1)
        ):
            raise InvalidTimelineOperation("Branch events must be contiguous")
        if branch.parent_branch_id is not None and (not additions or additions[0].kind is not EventKind.BRANCH_CREATED):
            raise InvalidTimelineOperation("A fork requires a branch marker")
        visible = {event.event_id: event for event in world}
        message_keys = {event.payload.to_dict().get("message_id") for event in world if event.kind in HISTORY_KINDS}
        known = {}

        def observe(event):
            for character in event.observers:
                knowledge = known.setdefault(character, set())
                if event.kind is EventKind.CONTEXT_RESET:
                    knowledge.clear()
                knowledge.add(event.event_id)
                if event.kind is EventKind.EVENT_OBSERVED:
                    knowledge.update(link.event_id for link in event.links if link.relation is CausalRelation.OBSERVES)

        for event in world:
            observe(event)

        def resolve(event_id):
            if event_id not in visible:
                raise InvalidTimelineOperation("Archive causal target is outside its preceding world")
            return visible[event_id]

        for index, event in enumerate(additions):
            if event.kind in HISTORY_KINDS:
                message_id = event.payload.to_dict().get("message_id")
                if message_id:
                    require_id(message_id, "message_id")
                    if message_id in message_keys:
                        raise InvalidTimelineOperation("An external message identity names exactly one fact per branch world")
                    message_keys.add(message_id)
            if event.kind is EventKind.BRANCH_CREATED:
                if (branch.parent_branch_id is None or index != 0
                        or event.payload.to_dict() != {"checkpoint_id": branch.checkpoint_id}
                        or event.actor_id is not None or event.observers
                        or event.links != (CausalLink(CausalRelation.CAUSED_BY, branch.checkpoint_id),)):
                    raise InvalidTimelineOperation("Invalid branch marker")
            else:
                validate_event(draft_from_event(event), resolve,
                               lambda character, target: target in known.get(character, ()))
            visible[event.event_id] = event
            observe(event)
        worlds[branch.branch_id] = [*world, *additions]
    seen_operations = set()
    for operation in archive.operations:
        require_id(operation.key, "operation key")
        identity = (operation.branch_id, operation.key)
        if operation.branch_id not in branches or identity in seen_operations:
            raise InvalidTimelineOperation("Invalid or duplicate operation receipt")
        seen_operations.add(identity)
        committed = []
        for event_id in operation.event_ids:
            event = events.get(event_id)
            if event is None or event.branch_id != operation.branch_id:
                raise InvalidTimelineOperation("Receipt references a missing or inherited event")
            committed.append(event)
        if committed and [event.sequence for event in committed] != list(range(committed[0].sequence, committed[0].sequence + len(committed))):
            raise InvalidTimelineOperation("Receipt must identify one atomic append")
        intent = operation.intent.to_dict()
        expected_intent = JsonDocument({"command": intent.get("command", {}),
                                        "events": [draft_from_event(event).intent() for event in committed]})
        if expected_intent != operation.intent:
            raise InvalidTimelineOperation("Receipt intent differs from committed facts")
    return tuple(ordered)
