from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Callable, TypeVar

from domain.timeline import CausalRelation, EventKind
from domain.timeline.models import require_id
from domain.timeline.ports import TimelineRepository
from domain.timeline.projections import CharacterMessageProjection, KnownEvent

T = TypeVar("T")


@dataclass(slots=True)
class _Entry:
    projection: CharacterMessageProjection
    head: int = 0
    lock: RLock = field(default_factory=RLock)


class TimelineHistoryQueries:
    """Bounded disposable projections for live history paging and identity lookup.

    A cache frontier always names a completed branch prefix. Older snapshots are
    reconstructed separately and never borrow mutable current-world state.
    """

    def __init__(
        self, repository: TimelineRepository, *, max_views: int = 32,
        budget_bytes: int = 32 * 1024 * 1024, budget_facts: int = 100000,
    ):
        self.repository = repository
        self.max_views = max_views
        self.budget_bytes = budget_bytes
        self.budget_facts = budget_facts
        self._guard = RLock()
        self._entries = OrderedDict()

    def _advance(self, entry: _Entry, branch_id: str, character_id: str, head: int) -> None:
        cursor = entry.head
        while True:
            events = self.repository.read(branch_id, observer=character_id, after=cursor, through=head)
            if not events:
                break
            for event in events:
                if event.kind is EventKind.EVENT_OBSERVED:
                    target_id = next(link.event_id for link in event.links if link.relation is CausalRelation.OBSERVES)
                    if target_id not in entry.projection.seen:
                        target = self.repository.get_event(branch_id, target_id)
                        entry.projection.observe(KnownEvent(target, event.sequence))
                entry.projection.observe(KnownEvent(event, event.sequence))
            cursor = events[-1].sequence
        entry.head = head

    def _trim(self):
        with self._guard:
            while self._entries and (
                len(self._entries) > self.max_views
                or sum(entry.projection.estimated_bytes for entry in self._entries.values()) > self.budget_bytes
                or sum(len(entry.projection.seen) for entry in self._entries.values()) > self.budget_facts
            ):
                self._entries.popitem(last=False)

    def _query(self, branch_id: str, character_id: str, through: int | None, operation: Callable[[CharacterMessageProjection], T]) -> T:
        require_id(character_id, "character_id")
        branch = self.repository.get_branch(branch_id)
        head = branch.head_sequence if through is None else min(through, branch.head_sequence)
        key = (branch_id, character_id)
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(CharacterMessageProjection(character_id))
                self._entries[key] = entry
            self._entries.move_to_end(key)
        with entry.lock:
            if head < entry.head:
                entry = _Entry(CharacterMessageProjection(character_id))
            try:
                if head > entry.head:
                    self._advance(entry, branch_id, character_id, head)
                result = operation(entry.projection)
            except BaseException:
                with self._guard:
                    self._entries.pop(key, None)
                raise
        self._trim()
        return result

    def messages(self, branch_id: str, character_id: str, *, through: int | None = None) -> tuple[dict, ...]:
        return self._query(branch_id, character_id, through, lambda projection: projection.messages())

    def page(self, branch_id: str, character_id: str, *, limit: int, offset: int = 0) -> tuple[dict, ...]:
        if type(limit) is not int or type(offset) is not int or limit <= 0 or offset < 0:
            return ()
        return self._query(branch_id, character_id, None, lambda projection: projection.page(limit, offset))

    def count(self, branch_id: str, character_id: str) -> int:
        return self._query(branch_id, character_id, None, lambda projection: projection.count)

    def contains(self, branch_id: str, character_id: str, message_id: str) -> bool:
        return self._query(branch_id, character_id, None, lambda projection: projection.contains(message_id))
