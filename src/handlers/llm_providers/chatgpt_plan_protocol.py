from __future__ import annotations

import json
from typing import Any, Mapping


_UNSUPPORTED_RESPONSE_FIELDS = {
    "background", "conversation", "max_output_tokens", "max_tool_calls", "metadata",
    "moderation", "multi_agent", "previous_response_id", "prompt", "prompt_cache_retention",
    "safety_identifier", "temperature", "top_logprobs", "top_p", "truncation", "user",
}


def _message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
            continue
        if not isinstance(part, Mapping):
            continue
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def build_responses_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the restricted Responses payload accepted by ChatGPT plan sharing.

    NeuroMita owns conversation history, so every request sends the complete context.
    System messages are moved to ``instructions`` because explicit system-role input
    items are rejected by the current preview endpoint.
    """
    instructions: list[str] = []
    input_items: list[dict[str, str]] = []

    for message in messages or []:
        role = str(message.get("role") or "user").strip().lower()
        text = _message_text(message)
        if not text:
            continue
        if role in {"system", "developer"}:
            instructions.append(text)
        elif role in {"user", "assistant"}:
            input_items.append({"role": role, "content": text})
        else:
            # Limited mode does not execute provider-native tools. Preserve useful
            # history instead of emitting an unsupported role to Responses.
            input_items.append({"role": "user", "content": f"[{role}]\n{text}"})

    payload: dict[str, Any] = {
        "model": str(model or "").strip(),
        "input": input_items,
        "store": False,
        "stream": True,
    }
    if instructions:
        payload["instructions"] = "\n\n".join(instructions)

    for field in _UNSUPPORTED_RESPONSE_FIELDS:
        payload.pop(field, None)
    return payload


def normalize_responses_usage(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    input_details = payload.get("input_tokens_details")
    output_details = payload.get("output_tokens_details")
    input_details = input_details if isinstance(input_details, Mapping) else {}
    output_details = output_details if isinstance(output_details, Mapping) else {}
    return {
        "prompt_tokens": int(payload.get("input_tokens") or 0),
        "completion_tokens": int(payload.get("output_tokens") or 0),
        "total_tokens": int(payload.get("total_tokens") or 0),
        "cached_prompt_tokens": int(input_details.get("cached_tokens") or 0),
        "cache_write_tokens": int(input_details.get("cache_write_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
        "raw": dict(payload),
    }


def parse_sse_data_line(line: str) -> dict[str, Any] | None:
    line = str(line or "").strip()
    if not line.startswith("data:"):
        return None
    raw = line[5:].strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


__all__ = ["build_responses_payload", "normalize_responses_usage", "parse_sse_data_line"]
