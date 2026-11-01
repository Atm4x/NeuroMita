from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, Sequence

from domain.timeline import JsonDocument
from .conversation_timeline import ConversationTimeline


@dataclass(frozen=True, slots=True)
class ContextSummary:
    through: int
    digest: str
    text: str
    source_head: int = 0


class ContextSummaryRepository(Protocol):
    def load(self, branch_id: str, character_id: str) -> ContextSummary | None: ...

    def save(self, branch_id: str, character_id: str, summary: ContextSummary) -> None: ...


def prefix_digest(messages: Sequence[dict]) -> str:
    facts = [{key: message.get(key) for key in (
        "timeline_event_id", "timeline_learned_at", "role", "speaker", "target", "content", "structured_data",
    )} for message in messages]
    return sha256(JsonDocument({"messages": facts}).canonical.encode("utf-8")).hexdigest()


class TimelineContext:
    """Branch-scoped, disposable context summaries verified against their exact facts."""

    def __init__(self, conversation: ConversationTimeline, summaries: ContextSummaryRepository):
        self.conversation = conversation
        self.summaries = summaries

    def unsummarized(self, character_id: str) -> tuple[str, list[dict]]:
        timeline = self.conversation.runtime.timeline
        branch_id = timeline.branch_id
        summary = self.summaries.load(branch_id, character_id)
        turn = self.conversation.runtime.turn
        head = turn.context_head if turn else timeline.branch.head_sequence
        if summary is not None and 0 < summary.source_head <= head:
            epoch = timeline.repository.presentation_epoch(branch_id, character_id, through=head)
            if epoch <= summary.source_head:
                return summary.text, list(self.conversation.context_messages(character_id, after=summary.through))
        messages = list(self.conversation.context_messages(character_id))
        if summary is None:
            return "", messages
        prefix = [message for message in messages if message["timeline_learned_at"] <= summary.through]
        if not prefix or prefix_digest(prefix) != summary.digest:
            return "", messages
        return summary.text, [message for message in messages if message["timeline_learned_at"] > summary.through]

    def store(self, character_id: str, prefix: Sequence[dict], text: str) -> None:
        if not prefix or not text.strip():
            return
        through = max(message["timeline_learned_at"] for message in prefix)
        with self.conversation.runtime.writing() as timeline:
            current = [message for message in self.conversation.context_messages(character_id)
                       if message["timeline_learned_at"] <= through]
            if prefix_digest(current) != prefix_digest(prefix):
                return
            self.summaries.save(timeline.branch_id, character_id, ContextSummary(
                through, prefix_digest(prefix), text.strip(),
                self.conversation.runtime.turn.context_head if self.conversation.runtime.turn else timeline.branch.head_sequence,
            ))
