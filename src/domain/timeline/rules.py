from __future__ import annotations

from typing import Callable

from .errors import InvalidTimelineOperation
from .models import CausalRelation, EventDraft, EventKind, TimelineEvent


MESSAGE_KINDS = frozenset({EventKind.PLAYER_MESSAGE, EventKind.CHARACTER_MESSAGE})
HISTORY_KINDS = MESSAGE_KINDS | {EventKind.SESSION_NOTE, EventKind.CHARACTER_OBSERVATION}


def validate_event(
    draft: EventDraft,
    resolve: Callable[[str], TimelineEvent],
    knows: Callable[[str, str], bool],
) -> None:
    """Validate an append against the exact preceding world, including batch prefixes."""
    counts: dict[CausalRelation, int] = {}
    for link in draft.links:
        target = resolve(link.event_id)
        counts[link.relation] = counts.get(link.relation, 0) + 1
        if link.relation is CausalRelation.REPLY_TO and target.kind not in MESSAGE_KINDS:
            raise InvalidTimelineOperation("reply_to must target a message")
        if link.relation in {CausalRelation.REPLY_TO, CausalRelation.REACT_TO}:
            if draft.kind is not EventKind.CHARACTER_MESSAGE:
                raise InvalidTimelineOperation("Only character messages reply or react")
            if not knows(draft.actor_id, target.event_id):
                raise InvalidTimelineOperation("A character cannot respond to an unknown event")
    for relation in (CausalRelation.REPLY_TO, CausalRelation.REACT_TO, CausalRelation.OBSERVES):
        if counts.get(relation, 0) > 1:
            raise InvalidTimelineOperation(f"Only one {relation.value} target is allowed")
    if counts.get(CausalRelation.REPLY_TO) and counts.get(CausalRelation.REACT_TO):
        raise InvalidTimelineOperation("A turn cannot be both reply and reaction")
    if draft.kind is EventKind.EVENT_OBSERVED:
        if not draft.observers or counts.get(CausalRelation.OBSERVES) != 1:
            raise InvalidTimelineOperation("Observation requires recipients and one observes link")
    elif counts.get(CausalRelation.OBSERVES):
        raise InvalidTimelineOperation("Only EventObserved may disclose a past event")
    if draft.kind in {EventKind.CHARACTER_JOINED, EventKind.CHARACTER_LEFT}:
        if not draft.actor_id or draft.actor_id not in draft.observers:
            raise InvalidTimelineOperation("Presence changes require the character as a witness")
    if draft.kind is EventKind.CHECKPOINT:
        if not isinstance(draft.payload.to_dict().get("snapshot"), dict):
            raise InvalidTimelineOperation("Checkpoint requires a world snapshot object")
    if draft.kind is EventKind.BRANCH_CREATED:
        raise InvalidTimelineOperation("Branch markers are created only by fork")
    if draft.kind in {EventKind.MESSAGE_HIDDEN, EventKind.MESSAGE_REVISED, EventKind.MESSAGE_RESTORED}:
        payload = draft.payload.to_dict()
        targets = payload.get("event_ids") if draft.kind is EventKind.MESSAGE_HIDDEN else [payload.get("event_id")]
        if not isinstance(targets, list) or not targets or not draft.observers:
            raise InvalidTimelineOperation("Message presentation changes require targets and observers")
        for target_id in targets:
            target = resolve(target_id)
            if target.kind not in HISTORY_KINDS:
                raise InvalidTimelineOperation("Message presentation changes must target a message")
            if any(not knows(observer, target_id) for observer in draft.observers):
                raise InvalidTimelineOperation("Cannot edit an unknown message")
        if draft.kind is EventKind.MESSAGE_REVISED:
            replacement = payload.get("message")
            if not isinstance(replacement, dict) or "content" not in replacement:
                raise InvalidTimelineOperation("Message revision requires replacement content")
            protected = {"role", "speaker", "sender", "timeline_event_id", "timeline_sequence",
                         "timeline_learned_at", "_history_row_id", "time"}
            if protected.intersection(replacement):
                raise InvalidTimelineOperation("Message revision cannot change identity, author or acquisition")
            if replacement.get("message_id", target.payload.to_dict().get("message_id")) != target.payload.to_dict().get("message_id"):
                raise InvalidTimelineOperation("Message revision cannot change its external identity")
    if draft.kind is EventKind.CONTEXT_RESET and not draft.observers:
        raise InvalidTimelineOperation("Context reset requires affected characters")
