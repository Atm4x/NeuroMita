from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from .errors import InvalidTimelineOperation


def new_id() -> str:
    return uuid4().hex


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def require_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise InvalidTimelineOperation(f"{name} must be a non-empty canonical string")
    return value


def observer_ids(values) -> frozenset[str]:
    if isinstance(values, str):
        raise InvalidTimelineOperation("Observers must be a collection of character identities")
    result = frozenset(values)
    for value in result:
        require_id(value, "observer")
    return result


def _validate_json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json(item)
        return
    raise InvalidTimelineOperation("Payload must contain only finite JSON values and string keys")


@dataclass(frozen=True, slots=True, init=False)
class JsonDocument:
    """An immutable JSON object; reads return detached ordinary Python values."""

    canonical: str

    def __init__(self, value: Mapping[str, Any] | None = None):
        if value is not None and not isinstance(value, Mapping):
            raise InvalidTimelineOperation("A JSON document must be an object")
        data = dict(value or {})
        _validate_json(data)
        object.__setattr__(self, "canonical", json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))

    @classmethod
    def parse(cls, value: str) -> JsonDocument:
        data = json.loads(value)
        if not isinstance(data, dict):
            raise InvalidTimelineOperation("Payload must be a JSON object")
        return cls(data)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical)


class EventKind(str, Enum):
    PLAYER_MESSAGE = "PlayerMessage"
    CHARACTER_MESSAGE = "CharacterMessage"
    CHARACTER_OBSERVATION = "CharacterObservation"
    CHARACTER_JOINED = "CharacterJoined"
    CHARACTER_LEFT = "CharacterLeft"
    UNITY_EVENT = "UnityEvent"
    GAME_STARTED = "GameStarted"
    GAME_ACTION = "GameAction"
    GAME_ENDED = "GameEnded"
    PLAYER_INACTIVE = "PlayerInactive"
    PROACTIVE_OPPORTUNITY = "ProactiveOpportunity"
    EVENT_OBSERVED = "EventObserved"
    SESSION_NOTE = "SessionNote"
    MESSAGE_HIDDEN = "MessageHidden"
    MESSAGE_REVISED = "MessageRevised"
    MESSAGE_RESTORED = "MessageRestored"
    CONTEXT_RESET = "CharacterContextReset"
    CHECKPOINT = "Checkpoint"
    BRANCH_CREATED = "BranchCreated"


class CausalRelation(str, Enum):
    REPLY_TO = "reply_to"
    REACT_TO = "react_to"
    CAUSED_BY = "caused_by"
    OBSERVES = "observes"


class TurnKind(str, Enum):
    REPLY = "reply"
    REACT = "react"
    INITIATE = "initiate"


@dataclass(frozen=True, slots=True)
class CausalLink:
    relation: CausalRelation
    event_id: str

    def __post_init__(self) -> None:
        require_id(self.event_id, "causal target")
        object.__setattr__(self, "relation", CausalRelation(self.relation))


@dataclass(frozen=True, slots=True)
class EventDraft:
    kind: EventKind
    payload: JsonDocument = field(default_factory=JsonDocument)
    actor_id: str | None = None
    observers: frozenset[str] = frozenset()
    links: tuple[CausalLink, ...] = ()
    event_id: str = field(default_factory=new_id)
    occurred_at: str = field(default_factory=utc_now)
    schema_version: int = 1

    def __post_init__(self) -> None:
        require_id(self.event_id, "event_id")
        object.__setattr__(self, "kind", EventKind(self.kind))
        if not isinstance(self.payload, JsonDocument):
            raise InvalidTimelineOperation("Event payload must be a JsonDocument")
        if self.actor_id is not None:
            require_id(self.actor_id, "actor_id")
        object.__setattr__(self, "observers", observer_ids(self.observers))
        object.__setattr__(self, "links", tuple(self.links))
        if not all(isinstance(link, CausalLink) for link in self.links):
            raise InvalidTimelineOperation("Causality must contain typed event links")
        if len(set(self.links)) != len(self.links):
            raise InvalidTimelineOperation("Duplicate causal relation")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise InvalidTimelineOperation("Unsupported event schema version")
        try:
            timestamp = datetime.fromisoformat(self.occurred_at)
        except (ValueError, TypeError) as exc:
            raise InvalidTimelineOperation("Event time must be an ISO timestamp") from exc
        if timestamp.tzinfo is None:
            raise InvalidTimelineOperation("Event time must include its timezone")
        if self.kind in {EventKind.PLAYER_MESSAGE, EventKind.CHARACTER_MESSAGE, EventKind.CHARACTER_OBSERVATION}:
            if not self.actor_id:
                raise InvalidTimelineOperation("Messages require an author")
        if self.kind in {EventKind.CHARACTER_MESSAGE, EventKind.CHARACTER_OBSERVATION} and self.actor_id not in self.observers:
            raise InvalidTimelineOperation("A character must know its own message")

    def intent(self) -> dict[str, Any]:
        """Retry identity excludes wall-clock time, but preserves semantic identity."""
        return {
            "event_id": self.event_id, "kind": self.kind.value,
            "payload": self.payload.to_dict(), "actor_id": self.actor_id,
            "observers": sorted(self.observers), "schema_version": self.schema_version,
            "links": sorted((link.relation.value, link.event_id) for link in self.links),
        }


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    event_id: str
    session_id: str
    branch_id: str
    sequence: int
    kind: EventKind
    payload: JsonDocument
    actor_id: str | None
    observers: frozenset[str]
    links: tuple[CausalLink, ...]
    occurred_at: str
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class Branch:
    branch_id: str
    session_id: str
    parent_branch_id: str | None
    fork_sequence: int
    head_sequence: int
    checkpoint_id: str | None = None


@dataclass(frozen=True, slots=True)
class TimelineSelection:
    branch_id: str
    generation: int


@dataclass(frozen=True, slots=True)
class TimelineTurn:
    selection: TimelineSelection
    context_head: int
    trigger_id: str | None = None
    kind: TurnKind = TurnKind.INITIATE
    character_id: str = ""
    context_epoch: int = 0
    include_target: bool = False
    input_event_ids: tuple[str, ...] = ()

    @property
    def reply(self) -> bool:
        return self.kind is TurnKind.REPLY


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    command: JsonDocument
    events: tuple[TimelineEvent, ...]
