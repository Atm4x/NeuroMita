from __future__ import annotations

from domain.timeline import EventKind, JsonDocument, TimelineEvent
from domain.timeline.projections import KnownEvent, message_projection
from services.conversation_timeline import semantic_message


def test_semantic_message_keeps_request_provenance() -> None:
    snapshot_id = "ctx_0123456789abcdef0123456789abcdef"
    result = semantic_message({
        "message_id": "out:1",
        "role": "assistant",
        "content": "Hi",
        "sample_id": "sample-1",
        "context_snapshot_id": snapshot_id,
        "temperature": 0.7,
    })

    assert result["sample_id"] == "sample-1"
    assert result["context_snapshot_id"] == snapshot_id
    assert "temperature" not in result


def test_cognitive_effect_session_note_projects_back_as_event() -> None:
    content = "[Cognitive Effect]\nТы чувствуешь, что внутри тебя изменилось:"
    event = TimelineEvent(
        event_id="event:1",
        session_id="session:1",
        branch_id="branch:1",
        sequence=4,
        kind=EventKind.SESSION_NOTE,
        payload=JsonDocument({
            "message_id": "event:1",
            "message": {
                "role": "system",
                "content": content,
                "notice_type": "cognitive_effect",
            },
            "content": content,
        }),
        actor_id=None,
        observers=frozenset({"Kind"}),
        links=(),
        occurred_at="2026-11-05T10:00:00+00:00",
    )

    projected = message_projection(KnownEvent(event, learned_at=4), "Kind")

    assert projected is not None
    assert projected["role"] == "event"
    assert projected["notice_type"] == "cognitive_effect"
