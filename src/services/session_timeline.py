from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Iterator, Mapping, Any
from uuid import NAMESPACE_URL, uuid5

from domain.timeline import (
    Branch, CausalLink, CausalRelation, EventDraft, EventKind,
    InvalidTimelineOperation, JsonDocument, TimelineEvent, TimelineNotFound, new_id,
)
from domain.timeline.models import observer_ids, require_id
from domain.timeline.ports import TimelineRepository
from domain.timeline.projections import KnownEvent, character_messages


@dataclass(frozen=True, slots=True)
class RestoredBranch:
    timeline: SessionTimeline
    snapshot: JsonDocument


class SessionTimeline:
    """Application operations bound to one explicit session branch.

    Branch identity never changes on an existing handle. Long-running work can
    therefore retain its world even if the application activates another branch.
    """

    def __init__(self, repository: TimelineRepository, branch_id: str):
        self.repository = repository
        self.branch_id = require_id(branch_id, "branch_id")

    @classmethod
    def create(
        cls, repository: TimelineRepository, *, session_id: str | None = None,
        branch_id: str | None = None,
    ) -> SessionTimeline:
        branch = repository.create_session(session_id or new_id(), branch_id or new_id())
        return cls(repository, branch.branch_id)

    @property
    def branch(self) -> Branch:
        return self.repository.get_branch(self.branch_id)

    def events(
        self, *, after: int = 0, through: int | None = None, observer: str | None = None,
    ) -> Iterator[TimelineEvent]:
        ceiling = self.branch.head_sequence if through is None else through
        cursor = after
        while True:
            page = self.repository.read(
                self.branch_id, after=cursor, through=ceiling, observer=observer,
            )
            if not page:
                return
            yield from page
            cursor = page[-1].sequence

    def event(self, event_id: str) -> TimelineEvent:
        return self.repository.get_event(self.branch_id, event_id)

    def character_view(
        self, character_id: str, *, through: int | None = None, after: int = 0,
    ) -> tuple[KnownEvent, ...]:
        require_id(character_id, "character_id")
        known: dict[str, KnownEvent] = {}
        baseline_forgotten = False
        for event in self.events(after=after, through=through, observer=character_id):
            if event.kind is EventKind.CONTEXT_RESET:
                known.clear()
                baseline_forgotten = True
            known.setdefault(event.event_id, KnownEvent(event, event.sequence))
            if event.kind is EventKind.EVENT_OBSERVED:
                target_id = next(link.event_id for link in event.links
                                 if link.relation is CausalRelation.OBSERVES)
                target = self.event(target_id)
                if target_id not in known:
                    previously_known = after > 0 and not baseline_forgotten and self.knows(character_id, target_id, through=after)
                    if not previously_known:
                        known[target_id] = KnownEvent(target, event.sequence)
        return tuple(sorted(known.values(), key=lambda item: (item.learned_at, item.event.sequence)))

    def messages(self, character_id: str, *, through: int | None = None, after: int = 0) -> tuple[dict, ...]:
        return character_messages(self.character_view(character_id, through=through, after=after), character_id)

    def knows(self, character_id: str, event_id: str, *, through: int | None = None) -> bool:
        return self.repository.knows(self.branch_id, character_id, event_id, through=through)

    def present(self, *, through: int | None = None) -> frozenset[str]:
        return self.repository.present(self.branch_id, through=through)

    def draft(
        self, kind: EventKind, payload: Mapping[str, Any] | None = None, *,
        actor_id: str | None = None, observers: Iterable[str] = (),
        links: Iterable[CausalLink] = (), key: str | None = None,
    ) -> EventDraft:
        event_id = self.event_id(key) if key is not None else new_id()
        return EventDraft(kind, JsonDocument(payload), actor_id, observer_ids(observers), tuple(links), event_id)

    def event_id(self, key: str) -> str:
        return uuid5(NAMESPACE_URL, JsonDocument({
            "branch": self.branch_id, "key": require_id(key, "event key"),
        }).canonical).hex

    def append(
        self, drafts: Iterable[EventDraft], *, expected_head: int, key: str,
        command: JsonDocument | None = None,
    ) -> tuple[TimelineEvent, ...]:
        return self.repository.append(
            self.branch_id, tuple(drafts), expected_head=expected_head, idempotency_key=key,
            command=command,
        )

    def publish(
        self, kind: EventKind, payload: Mapping[str, Any] | None = None, *,
        actor_id: str | None = None, observers: Iterable[str] | None = None,
        links: Iterable[CausalLink] = (), key: str, expected_head: int | None = None,
        occurred_at: str | None = None,
    ) -> TimelineEvent:
        head = self.branch.head_sequence if expected_head is None else expected_head
        if observers is None:
            identity = self.event_id(key)
            try:
                audience = self.event(identity).observers
            except TimelineNotFound:
                audience = self.present(through=head)
                if kind in {EventKind.CHARACTER_JOINED, EventKind.CHARACTER_LEFT} and actor_id:
                    audience = audience | {actor_id}
                if kind is EventKind.CHARACTER_MESSAGE and actor_id:
                    audience = audience | {actor_id}
        else:
            audience = observer_ids(observers)
        draft = self.draft(kind, payload, actor_id=actor_id, observers=audience, links=links, key=key)
        if occurred_at is not None:
            draft = replace(draft, occurred_at=occurred_at)
        return self.append((draft,), expected_head=head, key=key)[0]

    def join(self, character_id: str, *, key: str) -> TimelineEvent:
        require_id(character_id, "character_id")
        return self.publish(EventKind.CHARACTER_JOINED, actor_id=character_id, key=key)

    def leave(self, character_id: str, *, key: str) -> TimelineEvent:
        return self.publish(EventKind.CHARACTER_LEFT, actor_id=character_id, key=key)

    def disclose(self, event_id: str, recipients: Iterable[str], *, key: str) -> TimelineEvent:
        return self.publish(
            EventKind.EVENT_OBSERVED, observers=recipients,
            links=(CausalLink(CausalRelation.OBSERVES, event_id),), key=key,
        )

    def checkpoint(self, snapshot: Mapping[str, Any], *, key: str, label: str = "") -> TimelineEvent:
        return self.publish(EventKind.CHECKPOINT, {"snapshot": dict(snapshot), "label": label},
                            observers=(), key=key)

    def fork(self, checkpoint_id: str, *, branch_id: str | None = None) -> RestoredBranch:
        branch = self.repository.fork(self.branch_id, checkpoint_id, branch_id or new_id())
        checkpoint = self.event(checkpoint_id)
        snapshot = checkpoint.payload.to_dict().get("snapshot")
        if not isinstance(snapshot, dict):
            raise InvalidTimelineOperation("Checkpoint snapshot is unavailable")
        return RestoredBranch(SessionTimeline(self.repository, branch.branch_id), JsonDocument(snapshot))
