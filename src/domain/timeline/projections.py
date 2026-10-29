from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import CausalRelation, EventKind, JsonDocument, TimelineEvent
from .time import display_timestamp


@dataclass(frozen=True, slots=True)
class KnownEvent:
    event: TimelineEvent
    learned_at: int


def present_characters(events: Iterable[TimelineEvent]) -> frozenset[str]:
    present: set[str] = set()
    for event in events:
        if event.kind is EventKind.CHARACTER_JOINED:
            present.add(event.actor_id)
        elif event.kind is EventKind.CHARACTER_LEFT:
            present.discard(event.actor_id)
    return frozenset(present)


def message_projection(known: KnownEvent, character_id: str) -> dict | None:
    """Render a semantic message into the application's provider/UI vocabulary."""
    event = known.event
    if event.kind not in {EventKind.PLAYER_MESSAGE, EventKind.CHARACTER_MESSAGE,
                           EventKind.CHARACTER_OBSERVATION, EventKind.SESSION_NOTE}:
        return None
    payload = event.payload.to_dict()
    message = dict(payload.get("message") or {})
    message.update({
        "message_id": payload.get("message_id") or event.event_id,
        "role": ("system" if event.kind is EventKind.SESSION_NOTE else
                 "user" if event.kind is EventKind.CHARACTER_OBSERVATION else
                 "assistant" if event.actor_id == character_id else "user"),
        "speaker": event.actor_id, "sender": event.actor_id,
        "content": payload.get("content", message.get("content", "")),
        "timeline_event_id": event.event_id, "timeline_sequence": event.sequence,
        "timeline_learned_at": known.learned_at,
        "_history_row_id": known.learned_at,
    })
    if event.kind is EventKind.CHARACTER_OBSERVATION:
        message.update(speaker="World", sender="World")
    message.setdefault("time", display_timestamp(event.occurred_at))
    return message


def character_messages(known: Iterable[KnownEvent], character_id: str) -> tuple[dict, ...]:
    projection = CharacterMessageProjection(character_id)
    for item in known:
        projection.observe(item)
    return projection.messages()


@dataclass(frozen=True, slots=True)
class ProjectedMessage:
    event_id: str
    message_id: str
    learned_at: int
    sequence: int
    document: JsonDocument


class CharacterMessageProjection:
    """Disposable fold of a character's witnessed facts, with detached read results."""

    def __init__(self, character_id: str):
        self.character_id = character_id
        self.seen: set[str] = set()
        self._known: dict[str, ProjectedMessage] = {}
        self._visible: dict[str, ProjectedMessage] = {}
        self._ordered: tuple[ProjectedMessage, ...] | None = None
        self.estimated_bytes = 0

    def _record(self, message: dict) -> ProjectedMessage:
        document = JsonDocument(message)
        self.estimated_bytes += len(document.canonical.encode("utf-8"))
        return ProjectedMessage(message["timeline_event_id"], message["message_id"],
                                message["timeline_learned_at"], message["timeline_sequence"], document)

    def observe(self, item: KnownEvent) -> None:
        event = item.event
        direct = self.character_id in event.observers and item.learned_at == event.sequence
        if event.kind is EventKind.CONTEXT_RESET and direct:
            self.seen.clear()
            self._known.clear()
            self._visible.clear()
            self.estimated_bytes = 0
            self._ordered = None
        if event.event_id in self.seen:
            return
        self.seen.add(event.event_id)
        message = message_projection(item, self.character_id)
        if message is not None:
            record = self._record(message)
            self._known[event.event_id] = self._visible[event.event_id] = record
            self._ordered = None
        elif direct and event.kind is EventKind.MESSAGE_HIDDEN:
            for event_id in event.payload.to_dict()["event_ids"]:
                self._visible.pop(event_id, None)
            self._ordered = None
        elif direct and event.kind in {EventKind.MESSAGE_REVISED, EventKind.MESSAGE_RESTORED}:
            payload = event.payload.to_dict()
            target = payload["event_id"]
            if target in self._known:
                record = self._known[target]
                if event.kind is EventKind.MESSAGE_REVISED:
                    replacement = record.document.to_dict()
                    replacement.update(payload["message"])
                    record = self._record(replacement)
                    self._known[target] = record
                self._visible[target] = record
                self._ordered = None

    def _records(self) -> tuple[ProjectedMessage, ...]:
        if self._ordered is None:
            self._ordered = tuple(sorted(self._visible.values(), key=lambda record: (record.learned_at, record.sequence)))
        return self._ordered

    @property
    def count(self) -> int:
        return len(self._visible)

    def contains(self, message_id: str) -> bool:
        return any(record.message_id == message_id for record in self._visible.values())

    def messages(self) -> tuple[dict, ...]:
        return tuple(record.document.to_dict() for record in self._records())

    def page(self, limit: int, offset: int = 0) -> tuple[dict, ...]:
        records = self._records()
        end = max(0, len(records) - offset)
        return tuple(record.document.to_dict() for record in records[max(0, end - limit):end])


def causal_target(event: TimelineEvent, relation: CausalRelation) -> str | None:
    return next((link.event_id for link in event.links if link.relation is relation), None)
