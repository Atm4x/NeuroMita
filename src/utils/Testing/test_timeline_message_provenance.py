from __future__ import annotations

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
