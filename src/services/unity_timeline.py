from __future__ import annotations

from typing import Any

from domain.timeline import EventKind, JsonDocument, TimelineConflict, new_id
from services.contracts import parse_dialogue_turn_context
from .timeline_runtime import SessionTimelineRuntime


class UnityTimelineIngress:
    """Persist semantic Unity facts before deciding whether to generate a reaction."""

    def __init__(self, runtime: SessionTimelineRuntime):
        self.runtime = runtime

    @staticmethod
    def _trigger(events, character_id):
        kinds = {EventKind.UNITY_EVENT, EventKind.PLAYER_INACTIVE, EventKind.PROACTIVE_OPPORTUNITY}
        return next((event.event_id for event in reversed(events)
                     if event.kind in kinds and character_id in event.observers), None)

    def ingest(self, request: dict[str, Any], character_id: str, recipients: list[str]) -> str | None:
        context = request.get("context") or {}
        data = request.get("data") or {}
        request_id = str(request.get("req_id") or new_id())
        request["req_id"] = request_id
        dialogue = parse_dialogue_turn_context(context.get("dialogue"))
        kind = str(request.get("type") or "answer")
        command = JsonDocument({
            "kind": kind, "character_id": character_id, "recipients": recipients,
            "dialogue": context.get("dialogue"), "runtime_events": context.get("runtime_events", []),
            "reaction_events": data.get("reaction_events", []),
            "reason": data.get("reason_content") or data.get("reason") or "",
            "reason_type": data.get("reason_type", "UnityEvent"),
        })
        with self.runtime.writing() as timeline:
            key = f"unity-ingress:{request_id}"
            receipt = timeline.repository.receipt(timeline.branch_id, key)
            if receipt is not None:
                if receipt.command != command:
                    raise TimelineConflict("Unity request identity was reused for different session facts")
                return self._trigger(receipt.events, character_id)
            head = timeline.branch.head_sequence
            present = set(timeline.present())
            witnesses = {character_id}
            drafts = []
            if dialogue is not None:
                for participant in dialogue.participants:
                    character = participant.character_id
                    if not character or character.casefold() in {"player", "gamemaster"}:
                        continue
                    if participant.is_active and participant.can_hear_speaker:
                        witnesses.add(character)
                    if participant.is_active and character not in present:
                        drafts.append(timeline.draft(
                            EventKind.CHARACTER_JOINED, {"conversation_id": dialogue.conversation_id},
                            actor_id=character, observers=present | {character},
                            key=f"{key}:joined:{character}",
                        ))
                        present.add(character)
                    elif not participant.is_active and character in present:
                        drafts.append(timeline.draft(
                            EventKind.CHARACTER_LEFT, {"conversation_id": dialogue.conversation_id},
                            actor_id=character, observers=present, key=f"{key}:left:{character}",
                        ))
                        present.discard(character)
            else:
                witnesses.update(recipients)
            raw_events = context.get("runtime_events", [])
            if not isinstance(raw_events, (list, tuple)):
                raw_events = [raw_events] if raw_events else []
            reaction_events = data.get("reaction_events")
            if isinstance(reaction_events, (list, tuple)):
                raw_events = [*raw_events, *reaction_events]
            elif kind == "react":
                reason = data.get("reason_content") or data.get("reason")
                if reason:
                    raw_events = [*raw_events, {"name": data.get("reason_type", "UnityEvent"), "description": reason}]
            for index, raw in enumerate(raw_events):
                if isinstance(raw, dict):
                    name = str(raw.get("name") or raw.get("type") or raw.get("reason_type") or "UnityEvent")
                    description = str(raw.get("description") or raw.get("reason_content") or raw.get("reason") or "")
                    payload = {"name": name, "description": description}
                    if isinstance(raw.get("data"), dict):
                        payload["data"] = raw["data"]
                    observers = raw.get("observers")
                    audience = witnesses.intersection(observers) if isinstance(observers, list) else witnesses
                else:
                    payload = {"name": "UnityEvent", "description": str(raw)}
                    audience = witnesses
                if payload.get("description") or "data" in payload or payload["name"] != "UnityEvent":
                    drafts.append(timeline.draft(EventKind.UNITY_EVENT, payload, observers=audience,
                                                 key=f"{key}:event:{index}"))
            if kind in {"idle", "idle_timeout", "periodic", "proactive"}:
                event_kind = (EventKind.PLAYER_INACTIVE if kind in {"idle", "idle_timeout"}
                              else EventKind.PROACTIVE_OPPORTUNITY)
                drafts.append(timeline.draft(event_kind, {"name": kind}, observers=witnesses, key=f"{key}:timer"))
            events = timeline.append(drafts, expected_head=head, key=key, command=command)
            return self._trigger(events, character_id)
