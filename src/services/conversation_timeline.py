from __future__ import annotations

from typing import Iterable

from domain.timeline import (
    CausalLink, CausalRelation, EventKind, InvalidTimelineOperation,
    TimelineConflict, TimelineEvent, TimelineNotFound,
)
from domain.timeline.rules import MESSAGE_KINDS
from domain.timeline.models import TimelineTurn, TurnKind, observer_ids
from domain.timeline.projections import character_messages
from domain.timeline.projections import KnownEvent, message_projection
from domain.timeline.time import display_timestamp, message_timestamp
from .timeline_runtime import SessionTimelineRuntime
from .timeline_history_queries import TimelineHistoryQueries
from .timeline_assets import TimelineContent
from domain.timeline.assets import TimelineAssetStore


def semantic_message(message: dict) -> dict:
    """Retain conversation meaning without persisting transport/provider diagnostics."""
    allowed = (
        "message_id", "content", "target", "participants", "event_type",
        "structured_data", "image_source", "image_descriptions", "tv_observation",
        "conversation_id", "conversation_epoch", "turn_index", "speaker_actor_id",
        "source_actor_id", "responder_actor_id", "participant_actor_ids",
        "context_world",
    )
    result = {key: message[key] for key in allowed if key in message}
    structured = result.get("structured_data")
    if isinstance(structured, dict):
        result["structured_data"] = {key: value for key, value in structured.items()
                                     if not key.startswith("_") and key != "reasoning"}
    return result


class ConversationTimeline:
    """Translate application conversation vocabulary into one authoritative timeline."""

    def __init__(self, runtime: SessionTimelineRuntime, assets: TimelineAssetStore | None = None):
        self.runtime = runtime
        self.history_queries = TimelineHistoryQueries(runtime.repository)
        self.content = TimelineContent(assets)

    def find_message(self, message_id: str) -> TimelineEvent:
        timeline = self.runtime.timeline
        return timeline.repository.find_message(timeline.branch_id, message_id)

    def resolve_message(self, identity: str) -> TimelineEvent:
        try:
            event = self.runtime.timeline.event(identity)
        except TimelineNotFound:
            event = self.find_message(identity)
        if event.kind not in MESSAGE_KINDS:
            raise InvalidTimelineOperation("Reply target must be a message")
        return event

    def record_message(
        self, message: dict, recipients: Iterable[str], *, actor_id: str, player: bool = False,
        links: Iterable[CausalLink] = (), note: bool = False, observation: bool = False,
    ) -> TimelineEvent:
        message = self.content.freeze_message(message)
        message_id = str(message.get("message_id") or "").strip()
        if not message_id:
            raise InvalidTimelineOperation("Conversation messages require a stable message_id")
        audience = observer_ids(recipients)
        if not player and not note:
            audience = audience | {actor_id}
        with self.runtime.writing() as timeline:
            kind = (EventKind.CHARACTER_OBSERVATION if observation else EventKind.SESSION_NOTE if note else
                    EventKind.PLAYER_MESSAGE if player else EventKind.CHARACTER_MESSAGE)
            links = tuple(links)
            try:
                existing = self.find_message(message_id)
            except TimelineNotFound:
                existing = None
            if existing is not None:
                original = existing.payload.to_dict()
                if (existing.actor_id != actor_id or existing.kind is not kind
                        or original.get("content") != message.get("content", "")
                        or (links and set(existing.links) != set(links))):
                    raise TimelineConflict("A message identity was reused for a different fact")
                if kind is EventKind.CHARACTER_MESSAGE:
                    previous = original.get("message", {}).get("structured_data")
                    if previous != semantic_message(message).get("structured_data"):
                        raise TimelineConflict("A character message cannot change its structured meaning on retry")
                for observer in sorted(audience):
                    if not timeline.knows(observer, existing.event_id):
                        timeline.disclose(existing.event_id, (observer,),
                                          key=f"message-observation:{message_id}:{observer}:{timeline.branch.head_sequence}")
                return existing
            return timeline.publish(
                kind,
                {"message_id": message_id, "content": message.get("content", ""),
                 "message": semantic_message(message)}, actor_id=actor_id,
                observers=audience, links=links, key=f"message:{message_id}",
                occurred_at=message_timestamp(message.get("time")),
            )

    def begin_turn(
        self, *, character_id: str, recipients: Iterable[str], incoming: dict | None,
        actor_id: str, player: bool, origin_message_id: str | None,
        event_type: str, instruction: str, operation_id: str,
        target_event_id: str | None = None, initiate: bool = False,
        observation_message: dict | None = None,
    ) -> TimelineTurn:
        if incoming is not None:
            incoming = self.content.freeze_message(incoming)
        if observation_message is not None:
            observation_message = self.content.freeze_message(observation_message)
        with self.runtime.writing() as timeline:
            trigger = None
            reply = False
            input_event_ids = []
            if target_event_id:
                trigger = timeline.event(target_event_id)
                if not timeline.knows(character_id, trigger.event_id):
                    raise InvalidTimelineOperation("The reacting character does not know the target event")
            if origin_message_id:
                try:
                    trigger = self.resolve_message(origin_message_id)
                except TimelineNotFound:
                    if incoming is None or not player:
                        raise
                    incoming = dict(incoming, message_id=origin_message_id)
                    trigger = self.record_message(incoming, recipients, actor_id=actor_id, player=True)
                if trigger.kind not in MESSAGE_KINDS or not timeline.knows(character_id, trigger.event_id):
                    raise InvalidTimelineOperation("Reply target is not a known message")
                if incoming is not None and trigger.payload.to_dict().get("content") != incoming.get("content", ""):
                    raise TimelineConflict("Reply input differs from the referenced message")
                if incoming is not None:
                    input_event_ids.append(trigger.event_id)
                reply = True
            elif incoming is not None:
                trigger = self.record_message(incoming, recipients, actor_id=actor_id, player=player)
                input_event_ids.append(trigger.event_id)
                reply = trigger.kind in MESSAGE_KINDS
            if observation_message is not None:
                observation = self.record_message(observation_message, (character_id,), actor_id=character_id,
                                                  observation=True)
                input_event_ids.append(observation.event_id)
                if trigger is None:
                    trigger = observation
            if trigger is None and (instruction or initiate or event_type in {"idle", "idle_timeout", "periodic"}):
                kind = (EventKind.PLAYER_INACTIVE if event_type in {"idle", "idle_timeout"}
                        else EventKind.PROACTIVE_OPPORTUNITY if initiate or event_type == "periodic"
                        else EventKind.UNITY_EVENT)
                trigger = timeline.publish(
                    kind, {"name": event_type, "description": instruction},
                    observers=recipients, key=f"trigger:{operation_id}",
                )
            turn_kind = (TurnKind.REPLY if reply else
                         TurnKind.INITIATE if initiate or trigger is None or trigger.kind is EventKind.PROACTIVE_OPPORTUNITY
                         else TurnKind.REACT)
            return self.runtime.capture(trigger_id=trigger.event_id if trigger else None, kind=turn_kind,
                                        character_id=character_id,
                                        include_target=trigger is not None and trigger.event_id not in input_event_ids,
                                        input_event_ids=tuple(input_event_ids))

    def complete_turn(
        self, user_event: dict | None, assistant_event: dict, recipients: Iterable[str], *,
        player: bool, origin_message_id: str | None,
    ) -> tuple[TimelineEvent | None, TimelineEvent | None]:
        with self.runtime.writing():
            incoming = None
            turn = self.runtime.turn
            if turn is not None and turn.trigger_id:
                trigger = self.runtime.timeline.event(turn.trigger_id)
            elif origin_message_id:
                trigger = self.find_message(origin_message_id)
            elif user_event is not None:
                incoming = self.record_message(user_event, recipients,
                                               actor_id=user_event["speaker"], player=player)
                trigger = incoming
            else:
                trigger = None
            if assistant_event.get("_history_is_deleted"):
                return incoming, None
            links = ()
            if trigger is not None:
                if turn is not None:
                    relation = {TurnKind.REPLY: CausalRelation.REPLY_TO, TurnKind.REACT: CausalRelation.REACT_TO,
                                TurnKind.INITIATE: CausalRelation.CAUSED_BY}[turn.kind]
                else:
                    relation = CausalRelation.REPLY_TO if trigger.kind in MESSAGE_KINDS else CausalRelation.REACT_TO
                links = (CausalLink(relation, trigger.event_id),)
            if turn is not None:
                assistant_event = dict(assistant_event, context_world={
                    "branch_id": turn.selection.branch_id, "through": turn.context_head,
                })
            outgoing = self.record_message(assistant_event, recipients,
                                            actor_id=assistant_event["speaker"], links=links)
            return incoming, outgoing

    def import_history(self, character_id: str, messages: Iterable[dict]) -> int:
        """Conservatively import one existing character view without guessing witnesses."""
        imported = 0
        for message in messages:
            if message.get("role") not in {"user", "assistant", "system", "event"}:
                continue
            message = self.content.freeze_message(message)
            message_id = str(message.get("message_id") or "").strip()
            if not message_id:
                message_id = f"history:{character_id}:{message['_history_row_id']}"
            actor = str(message.get("speaker") or message.get("sender")
                        or (character_id if message["role"] == "assistant" else "Player"))
            payload = dict(message, message_id=message_id)
            try:
                existing = self.find_message(message_id)
            except TimelineNotFound:
                self.record_message(payload, (character_id,), actor_id=actor, player=actor == "Player",
                                    note=message.get("role") in {"system", "event"})
                imported += 1
            else:
                original = existing.payload.to_dict()
                if (existing.actor_id != actor or original.get("content") != message.get("content", "")
                        or original.get("message", {}).get("structured_data") != semantic_message(message).get("structured_data")):
                    raise TimelineConflict(f"Conflicting imported message identity: {message_id}")
                if not self.runtime.timeline.knows(character_id, existing.event_id):
                    self.runtime.timeline.disclose(existing.event_id, (character_id,),
                                                   key=f"import-observation:{character_id}:{message_id}")
        return imported

    def messages(self, character_id: str, *, before_turn: bool = True) -> tuple[dict, ...]:
        turn = self.runtime.turn
        through = turn.context_head if turn is not None and before_turn else None
        messages = self.history_queries.messages(self.runtime.timeline.branch_id, character_id, through=through)
        if before_turn and turn is not None and turn.trigger_id:
            excluded = {*turn.input_event_ids, turn.trigger_id}
            messages = tuple(message for message in messages if message["timeline_event_id"] not in excluded)
        return messages

    def append_history(self, character_id: str, messages: Iterable[dict]) -> list[int]:
        """Compatibility ingress for manual notes and character-owned callers."""
        from domain.timeline import new_id

        sources = []
        drafts = []
        planned = {}
        with self.runtime.writing() as timeline:
            head = timeline.branch.head_sequence
            visible = {message["timeline_event_id"] for message in timeline.messages(character_id)}
            for message in messages:
                message = self.content.freeze_message(message)
                if message.get("_history_is_deleted"):
                    sources.append(head)
                    continue
                message_id = str(message.get("message_id") or "").strip()
                if not message_id:
                    message_id = new_id()
                    message = dict(message, message_id=message_id)
                if message_id in planned:
                    prior, sequence = planned[message_id]
                    if prior != message.get("content", ""):
                        raise TimelineConflict("Conflicting message identities in one history batch")
                    sources.append(sequence)
                    continue
                try:
                    event = self.find_message(message_id)
                except TimelineNotFound:
                    role = str(message.get("role") or "user")
                    actor = str(message.get("speaker") or message.get("sender")
                                or (character_id if role == "assistant" else "Player"))
                    kind = (EventKind.SESSION_NOTE if role in {"system", "event"} else
                            EventKind.PLAYER_MESSAGE if actor == "Player" else EventKind.CHARACTER_MESSAGE)
                    audience = {character_id, actor} if kind is EventKind.CHARACTER_MESSAGE else {character_id}
                    drafts.append(timeline.draft(
                        kind, {"message_id": message_id, "content": message.get("content", ""),
                               "message": semantic_message(message)},
                        actor_id=actor, observers=audience, key=f"message:{message_id}",
                    ))
                    sequence = head + len(drafts)
                else:
                    if event.payload.to_dict().get("content") != message.get("content", ""):
                        raise TimelineConflict("A message identity cannot be appended with different content")
                    if not timeline.knows(character_id, event.event_id):
                        drafts.append(timeline.draft(
                            EventKind.EVENT_OBSERVED, observers=(character_id,),
                            links=(CausalLink(CausalRelation.OBSERVES, event.event_id),),
                        ))
                    elif event.event_id not in visible:
                        drafts.append(timeline.draft(EventKind.MESSAGE_RESTORED, {"event_id": event.event_id},
                                                     observers=(character_id,)))
                    sequence = event.sequence
                planned[message_id] = (message.get("content", ""), sequence)
                sources.append(sequence)
            if drafts:
                timeline.append(drafts, expected_head=head, key=f"history-batch:{new_id()}")
        return sources

    def replace_history(self, character_id: str, desired: Iterable[dict]) -> None:
        """Translate one full character-view replacement into one atomic semantic append."""
        from domain.timeline import new_id

        messages = tuple(self.content.freeze_message(message) for message in desired)
        with self.runtime.writing() as timeline:
            head = timeline.branch.head_sequence
            current = {message["message_id"]: message for message in timeline.messages(character_id)}
            identities = [message.get("message_id") for message in messages if message.get("message_id")]
            if len(set(identities)) != len(identities):
                raise TimelineConflict("A replacement contains duplicate message identities")
            removed = [message["timeline_event_id"] for identity, message in current.items() if identity not in identities]
            drafts = []
            if removed:
                drafts.append(timeline.draft(EventKind.MESSAGE_HIDDEN, {"event_ids": removed}, observers=(character_id,)))
            for message in messages:
                message_id = str(message.get("message_id") or new_id())
                message["message_id"] = message_id
                previous = current.get(message_id)
                if previous is not None:
                    event_id = previous["timeline_event_id"]
                else:
                    try:
                        existing = self.find_message(message_id)
                    except TimelineNotFound:
                        role = str(message.get("role") or "user")
                        actor = str(message.get("speaker") or message.get("sender")
                                    or (character_id if role == "assistant" else "Player"))
                        kind = (EventKind.SESSION_NOTE if role in {"system", "event"} else
                                EventKind.PLAYER_MESSAGE if actor == "Player" else EventKind.CHARACTER_MESSAGE)
                        audience = {character_id, actor} if kind is EventKind.CHARACTER_MESSAGE else {character_id}
                        drafts.append(timeline.draft(
                            kind, {"message_id": message_id, "content": message.get("content", ""),
                                   "message": semantic_message(message)},
                            actor_id=actor, observers=audience, key=f"message:{message_id}",
                        ))
                        continue
                    event_id = existing.event_id
                    if timeline.knows(character_id, event_id):
                        drafts.append(timeline.draft(EventKind.MESSAGE_RESTORED, {"event_id": event_id},
                                                     observers=(character_id,)))
                    else:
                        drafts.append(timeline.draft(EventKind.EVENT_OBSERVED, observers=(character_id,),
                                                     links=(CausalLink(CausalRelation.OBSERVES, event_id),)))
                    previous = dict(existing.payload.to_dict().get("message") or {})
                    previous.setdefault("content", existing.payload.to_dict().get("content", ""))
                if semantic_message(previous) != semantic_message(message):
                    drafts.append(timeline.draft(
                        EventKind.MESSAGE_REVISED, {"event_id": event_id, "message": semantic_message(message)},
                        observers=(character_id,),
                    ))
            if drafts:
                timeline.append(drafts, expected_head=head, key=f"replace-history:{new_id()}")

    def context_messages(self, character_id: str, *, after: int = 0) -> tuple[dict, ...]:
        timeline = self.runtime.timeline
        turn = self.runtime.turn
        through = turn.context_head if turn else None
        known_events = timeline.character_view(character_id, through=through, after=after)
        excluded = {*turn.input_event_ids, turn.trigger_id} if turn else set()
        messages = {message["timeline_event_id"]: message for message in character_messages(known_events, character_id)
                    if message["timeline_event_id"] not in excluded}
        facts = {
            EventKind.UNITY_EVENT, EventKind.GAME_STARTED, EventKind.GAME_ACTION, EventKind.GAME_ENDED,
            EventKind.CHARACTER_JOINED, EventKind.CHARACTER_LEFT, EventKind.PLAYER_INACTIVE,
        }
        for known in known_events:
            event = known.event
            if event.kind not in facts or (turn and event.event_id == turn.trigger_id):
                continue
            payload = event.payload.to_dict()
            description = payload.get("description") or payload.get("name") or event.kind.value
            details = {key: value for key, value in payload.items() if key not in {"description", "name"}}
            from domain.timeline import JsonDocument
            content = f"[Past session event: {event.kind.value}] {description}"
            if details:
                content += " " + JsonDocument(details).canonical
            messages[event.event_id] = {
                "role": "event", "content": content, "time": display_timestamp(event.occurred_at),
                "timeline_event_id": event.event_id, "timeline_learned_at": known.learned_at,
                "_history_row_id": known.learned_at,
            }
        return tuple(sorted(messages.values(), key=lambda item: item["timeline_learned_at"]))

    def filter_retrieval(self, character_id: str, results: Iterable[dict]) -> list[dict]:
        """A history index may nominate IDs; only this character's world supplies content."""
        from core.message_content import MessageContentCodec

        messages = {message["message_id"]: message for message in self.messages(character_id)}
        filtered = []
        for result in results:
            if not isinstance(result, dict):
                continue
            if result.get("source") != "history":
                filtered.append(result)
                continue
            message = messages.get(result.get("message_id"))
            if message is None:
                continue
            filtered.append({**result, "content": MessageContentCodec.to_embedding_text(message["content"]),
                             "role": message["role"], "speaker": message.get("speaker"),
                             "target": message.get("target"), "date": message.get("time")})
        return filtered

    def target_context(self, character_id: str) -> dict | None:
        turn = self.runtime.turn
        if turn is None or not turn.trigger_id or not turn.include_target:
            return None
        event = self.runtime.timeline.event(turn.trigger_id)
        if event.kind is EventKind.PROACTIVE_OPPORTUNITY:
            return None
        message = message_projection(KnownEvent(event, event.sequence), character_id)
        if message is not None:
            current = next((item for item in self.runtime.timeline.messages(character_id, through=turn.context_head)
                            if item["timeline_event_id"] == event.event_id), None)
            if current is not None:
                message = dict(current)
            message["role"] = "user"
            return message
        return {"role": "event", "content": f"[Current {event.kind.value}] {event.payload.canonical}",
                "time": display_timestamp(event.occurred_at)}
