from typing import Any, Iterable, Protocol

from ..base import LLMRequest, LLMResponse


class ProtocolAdapter(Protocol):
    dialect_id: str

    def encode(self, request: LLMRequest, *, wire_stream: bool) -> dict[str, Any]: ...

    def decode(self, request: LLMRequest, payload: dict[str, Any]) -> LLMResponse: ...

    def consume_stream(self, request: LLMRequest, chunks: Iterable[dict[str, Any]]) -> LLMResponse: ...
