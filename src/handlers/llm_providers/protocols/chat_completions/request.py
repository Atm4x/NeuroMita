from __future__ import annotations

from copy import deepcopy

from ...base import LLMRequest
from schemas.structured_response import StructuredResponse
from schemas.sparse_structured_response import provider_structured_model
from services.structured_response_capabilities import provider_schema_options
from .tools import encode_tools


def apply_response_format(req: LLMRequest, payload: dict) -> None:
    caps = req.capabilities or {}
    if not (caps.get("structured_output") and caps.get("native_structured_output", True)):
        return
    if caps.get("structured_output_mode", "json_schema") == "json_object":
        payload["response_format"] = {"type": "json_object"}
        return
    model = provider_structured_model(req.structured_model or StructuredResponse, caps)
    options = provider_schema_options(caps)
    payload["response_format"] = model.openai_response_format(
        exclude_fields=options["exclude_fields"] or None,
        custom_params=caps.get("custom_params") or None,
        exclude_segment_fields=options["exclude_segment_fields"] or None,
        require_fields=options["require_fields"] or None,
    )


def encode_request(req: LLMRequest, *, wire_stream: bool, payload: dict | None = None,
                   supports_stream_usage: bool = False) -> dict:
    if payload is None:
        payload = {"model": req.model, "messages": deepcopy([
            {key: value for key, value in message.items() if key != "time"}
            for message in req.messages if isinstance(message, dict)
        ])}
        if req.native_parameters is not None:
            payload.update(deepcopy(req.native_parameters))
        else:
            payload.update({key: req.extra[key] for key in (
                "temperature", "max_tokens", "presence_penalty", "frequency_penalty", "top_p", "logprobs"
            ) if key in req.extra})
    else:
        payload = deepcopy(payload)
    payload["stream"] = bool(wire_stream)
    caps = req.capabilities or {}
    stream_usage = caps.get("supports_stream_usage")
    if stream_usage is None:
        stream_usage = caps.get("stream_usage", supports_stream_usage)
    if wire_stream and stream_usage:
        payload["stream_options"] = {**(payload.get("stream_options") or {}), "include_usage": True}
    elif not wire_stream:
        payload.pop("stream_options", None)
    apply_response_format(req, payload)
    if req.tools_on and req.tools_mode == "native" and req.tools_payload:
        if not caps.get("tools_native", True):
            raise ValueError("Native tools are not supported by this endpoint.")
        payload["tools"] = encode_tools(req.tools_payload)
    return payload
