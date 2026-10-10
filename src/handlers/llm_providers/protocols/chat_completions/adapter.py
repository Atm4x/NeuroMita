from __future__ import annotations

from collections.abc import Callable, Iterable

from ...base import LLMRequest, LLMResponse
from .request import encode_request
from .response import decode_response
from .stream import consume_stream


class ChatCompletionsAdapter:
    dialect_id = "openai_chat_completions"

    def __init__(self, *, provider_name: str = "", payload_builder: Callable | None = None,
                 supports_stream_usage: bool = False) -> None:
        self.provider_name = provider_name
        self.payload_builder = payload_builder
        self.supports_stream_usage = supports_stream_usage

    def encode(self, req: LLMRequest, *, wire_stream: bool) -> dict:
        payload = self.payload_builder(req) if self.payload_builder else None
        return encode_request(req, wire_stream=wire_stream, payload=payload,
                              supports_stream_usage=self.supports_stream_usage)

    def decode(self, req: LLMRequest, payload: dict) -> LLMResponse:
        return decode_response(req, payload, provider=self.provider_name)

    def consume_stream(self, req: LLMRequest, chunks: Iterable[dict]) -> LLMResponse:
        return consume_stream(req, chunks, provider=self.provider_name)
