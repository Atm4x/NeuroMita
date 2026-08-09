from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolExecutionContext:
    """Immutable context captured when a tool call starts."""

    character_id: str = ""
    request_id: str = ""
    origin_request_id: str = ""
    event_type: str = ""
    origin_message_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_request(cls, request: Any) -> "ToolExecutionContext":
        extra = getattr(request, "extra", None) or {}
        metadata = extra.get("tool_context_metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        return cls(
            character_id=str(extra.get("character_id") or ""),
            request_id=str(extra.get("request_id") or ""),
            origin_request_id=str(extra.get("origin_request_id") or ""),
            event_type=str(extra.get("event_type") or ""),
            origin_message_id=str(extra.get("origin_message_id") or ""),
            metadata=dict(metadata),
        )


__all__ = ["ToolExecutionContext"]
