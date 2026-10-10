import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from handlers.llm_providers.base import LLMRequest, StreamChannel
from handlers.llm_providers.common_provider import CommonProvider
from handlers.llm_providers.errors import LLMProviderError
from handlers.llm_providers.openai_compatible import OpenAICompatibleProvider


def request(**kwargs):
    return LLMRequest(model="test", messages=[], api_url="https://example.test/v1",
                      provider_name="common", **kwargs)


@pytest.mark.parametrize("builder", [False, True])
def test_chat_encoder_projects_responses_history_without_mutating_it(builder):
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    messages = [{"role": "assistant", "content": None, "time": "local",
        "responses_output": [{"type": "reasoning", "encrypted_content": "opaque"}],
        "responses_reasoning_items": [{"type": "reasoning", "summary": []}],
        "tool_calls": [{"id": "call1", "type": "function",
            "function": {"name": "calculator", "arguments": "{}"},
            "extra_content": {"google": {"thought_signature": "signature"}}}]},
        {"role": "tool", "tool_call_id": "call1", "content": "2"}]
    original = copy.deepcopy(messages)
    req = request()
    req.messages = messages
    adapter = ChatCompletionsAdapter(payload_builder=(lambda _: {"model": "test", "messages": messages}) if builder else None)
    encoded = adapter.encode(req, wire_stream=False)["messages"]
    assert encoded[0] == {key: value for key, value in messages[0].items()
                          if key not in {"time", "responses_output", "responses_reasoning_items"}}
    assert encoded[1] == messages[1]
    assert messages == original
    encoded[0]["tool_calls"][0]["function"]["name"] = "changed"
    assert messages == original


def sdk_object(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{key: sdk_object(item) for key, item in value.items()})
    if isinstance(value, list):
        return [sdk_object(item) for item in value]
    return value


class SDK(OpenAICompatibleProvider):
    name = "sdk-test"

    def is_applicable(self, req):
        return True

    def _get_client(self, req):
        def create(**kwargs):
            self.captured = kwargs
            return iter(self.result) if req.stream else self.result
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
                               close=lambda: None)


def generate(transport, payload, req):
    if transport == "sdk":
        provider = SDK(http_transport=SimpleNamespace())
        provider.result = [sdk_object(item) for item in payload] if req.stream else sdk_object(payload)
    else:
        def handle(_):
            if req.stream:
                body = "".join(f"data: {json.dumps(item)}\n\n" for item in payload) + "data: [DONE]\n\n"
                return httpx.Response(200, text=body)
            return httpx.Response(200, json=payload)
        from handlers.llm_providers.http_transport import LLMHttpClient
        client = LLMHttpClient(client_factory=lambda _service_id, _http2: httpx.Client(transport=httpx.MockTransport(handle)))
        provider = CommonProvider(http_transport=client)
    try:
        return provider.generate(req)
    finally:
        provider.close()
        if transport == "http":
            client.close()


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_tool_only_completion_returns_normalized_calls_and_reasoning(transport):
    payload = {"model": "actual", "choices": [{"message": {"content": None,
        "reasoning": "considered", "tool_calls": [
            {"id": "call_a", "type": "function", "function": {"name": "clock", "arguments": '{"zone":"UTC"}'}},
            {"id": "call_b", "type": "function", "function": {"name": "timer", "arguments": "{}"}},
        ]}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 5, "completion_tokens": 3,
        "completion_tokens_details": {"reasoning_tokens": 2}, "prompt_tokens_details": {"cached_tokens": 4}}}
    result = generate(transport, payload, request())
    assert result.error_message is None
    assert result.text is None
    assert result.reasoning == "considered"
    assert [(c.name, c.arguments, c.id) for c in result.tool_calls] == [
        ("clock", {"zone": "UTC"}, "call_a"), ("timer", {}, "call_b")]
    assert result.model == "actual"
    assert result.usage.total_tokens == 8
    assert result.usage.reasoning_tokens == 2
    assert result.usage.cached_prompt_tokens == 4


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_interleaved_stream_tools_survive_usage_tail(transport):
    events = []
    chunks = [
        {"model": "actual", "choices": [{"delta": {"reasoning_content": "thinking", "tool_calls": [
            {"index": 1, "id": "call_b", "function": {"name": "timer", "arguments": '{"seconds":'}},
            {"index": 0, "id": "call_a", "function": {"name": "clock", "arguments": '{"zone":'}},
        ]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '"UTC"}'}},
            {"index": 1, "function": {"arguments": '12}'}},
        ]}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 4, "cost": 0.2}},
    ]
    req = request(stream=True, stream_event_cb=events.append)
    req.api_url = "https://openrouter.ai/api/v1/chat/completions"
    result = generate(transport, chunks, req)
    assert result.text is None
    assert result.error_message is None
    assert result.reasoning == "thinking"
    assert [(c.name, c.arguments, c.id) for c in result.tool_calls] == [
        ("clock", {"zone": "UTC"}, "call_a"), ("timer", {"seconds": 12}, "call_b")]
    assert result.usage.total_tokens == 11
    assert result.usage.cost_currency == "credits"
    assert len([e for e in events if e.type.value == "tool_call_completed"]) == 2


@pytest.mark.parametrize("transport", ["http", "sdk"])
@pytest.mark.parametrize("message,finish", [({"content": None, "refusal": "Denied"}, "stop"),
                                          ({"content": "partial"}, "length"),
                                          ({"content": "partial"}, "content_filter"),
                                          ({"content": None}, "stop")])
def test_refusal_truncation_and_empty_completions_are_errors(transport, message, finish):
    result = generate(transport, {"choices": [{"message": message, "finish_reason": finish}]}, request())
    assert result.error_message
    assert result.tool_calls == []


@pytest.mark.parametrize("transport", ["http", "sdk"])
@pytest.mark.parametrize("terminal", [
    {"error": {"message": "failed"}},
    {"choices": [{"delta": {"refusal": "Denied"}, "finish_reason": "stop"}]},
    {"choices": [{"delta": {}, "finish_reason": "length"}]},
])
def test_stream_terminal_failure_never_returns_partial_success(transport, terminal):
    with pytest.raises(LLMProviderError):
        generate(transport, [{"choices": [{"delta": {"content": "partial"}}]}, terminal], request(stream=True))


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_malformed_tool_arguments_are_not_executable(transport):
    payload = {"choices": [{"message": {"tool_calls": [
        {"id": "call_a", "function": {"name": "clock", "arguments": "[1]"}}
    ]}, "finish_reason": "tool_calls"}]}
    with pytest.raises(LLMProviderError):
        generate(transport, payload, request())


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_text_reasoning_and_multimodal_content_decode_identically(transport):
    payload = {"choices": [{"message": {"content": [{"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"}], "reasoning_content": "private"}, "finish_reason": "stop"}]}
    result = generate(transport, payload, request())
    assert result.text == "Hello world"
    assert result.reasoning == "private"


def test_adapter_wire_stream_is_independent_and_preserves_native_parameters():
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    req = request(stream=False, native_parameters={"custom": {"x": 2}},
                  capabilities={"supports_stream_usage": True, "structured_output": True,
                                "structured_output_mode": "json_object"},
                  tools_on=True, tools_payload=[{"type": "function", "function": {"name": "clock"}}])
    before = copy.deepcopy(req.native_parameters)
    payload = ChatCompletionsAdapter().encode(req, wire_stream=True)
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["tools"] == req.tools_payload
    assert payload["custom"] == {"x": 2}
    payload["custom"]["x"] = 3
    assert req.native_parameters == before
    assert "stream_options" not in ChatCompletionsAdapter().encode(req, wire_stream=False)


def test_sdk_preserves_unknown_native_parameters_in_extra_body():
    sdk = SDK(http_transport=SimpleNamespace())
    sdk.result = sdk_object({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
    sdk.generate(request(native_parameters={"unknown_extension": {"enabled": True}}))
    assert sdk.captured["extra_body"] == {"unknown_extension": {"enabled": True}}
    assert "unknown_extension" not in sdk.captured


@pytest.mark.parametrize("mode", ["native", "schema", "emulated"])
def test_canonical_flat_tools_are_wrapped_only_in_native_mode(mode):
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    declaration = {"name": "clock", "description": "Tell time", "parameters": {"type": "object"}}
    req = request(tools_on=True, tools_mode=mode, tools_payload=[declaration])
    payload = ChatCompletionsAdapter().encode(req, wire_stream=False)
    if mode == "native":
        assert payload["tools"] == [{"type": "function", "function": declaration}]
    else:
        assert "tools" not in payload
    assert req.tools_payload == [declaration]


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_stream_without_terminal_finish_is_not_partial_success(transport):
    with pytest.raises(LLMProviderError):
        generate(transport, [{"choices": [{"delta": {"content": "partial"}}]}], request(stream=True))


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_stream_malformed_tool_arguments_never_complete(transport):
    events = []
    with pytest.raises(LLMProviderError):
        generate(transport, [{"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_a", "function": {"name": "clock", "arguments": '{"x":'}}
        ]}, "finish_reason": "tool_calls"}]}], request(stream=True, stream_event_cb=events.append))
    assert not [event for event in events if event.type.value == "tool_call_completed"]


@pytest.mark.parametrize("payload", [{"choices": [None]}, {"choices": [{}], "model": "actual"},
                                     {"choices": [{"message": "wrong"}]}])
def test_adapter_invalid_completion_shapes_are_normalized(payload):
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    if payload == {"choices": [{}], "model": "actual"}:
        assert ChatCompletionsAdapter().decode(request(), payload).error_message
    else:
        with pytest.raises(LLMProviderError):
            ChatCompletionsAdapter().decode(request(), payload)


def test_custom_schema_fields_are_declared_in_chat_response_format():
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    req = request(capabilities={"structured_output": True, "custom_params": [
        {"name": "mood", "type": "int", "required": True}]})
    schema = ChatCompletionsAdapter().encode(req, wire_stream=False)["response_format"]["json_schema"]["schema"]
    custom = schema["properties"]["custom_fields"]
    custom = next((item for item in custom.get("anyOf", []) if item.get("type") == "object"), custom)
    assert custom["properties"]["mood"]["type"] == "integer"
    assert custom["additionalProperties"] is False


def test_real_sdk_model_keeps_extension_reasoning_and_usage_details():
    from openai.types.chat import ChatCompletion
    sdk = SDK(http_transport=SimpleNamespace())
    sdk.result = ChatCompletion.model_validate({"id": "completion", "object": "chat.completion",
        "created": 1, "model": "actual", "choices": [{"index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": "visible", "reasoning_content": "private"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8,
                  "completion_tokens_details": {"reasoning_tokens": 2}}})
    result = sdk.generate(request())
    assert result.text == "visible"
    assert result.reasoning == "private"
    assert result.usage.reasoning_tokens == 2


def test_forced_wire_stream_without_ui_streaming_emits_no_deltas():
    from handlers.llm_providers.protocols.chat_completions import ChatCompletionsAdapter
    events, deltas = [], []
    req = request(stream=False, stream_event_cb=events.append, stream_cb=lambda *delta: deltas.append(delta))
    response = ChatCompletionsAdapter().consume_stream(req, [
        {"choices": [{"delta": {"content": "visible"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ])
    assert response.text == "visible"
    assert not events
    assert not deltas


@pytest.mark.parametrize("transport", ["http", "sdk"])
def test_provider_encoder_accepts_canonical_native_tools(transport):
    provider = CommonProvider(http_transport=SimpleNamespace()) if transport == "http" else SDK(http_transport=SimpleNamespace())
    req = request(tools_on=True, tools_payload=[{"name": "clock", "parameters": {"type": "object"}}])
    payload = provider._protocol_adapter().encode(req, wire_stream=False)
    assert payload["tools"] == [{"type": "function", "function": {"name": "clock", "parameters": {"type": "object"}}}]


def test_disabled_structured_output_fallback_sends_only_strict_request():
    from handlers.llm_providers.http_transport import LLMHttpClient
    attempts = []
    def handle(http_request):
        attempts.append(json.loads(http_request.content))
        return httpx.Response(400, json={"error": {"message": "response_format json_schema unsupported"}})
    client = LLMHttpClient(client_factory=lambda _service_id, _http2: httpx.Client(transport=httpx.MockTransport(handle)))
    provider = CommonProvider(http_transport=client)
    try:
        with pytest.raises(LLMProviderError) as caught:
            provider.generate(request(capabilities={"structured_output": True, "structured_output_fallback": False}))
        assert caught.value.status_code == 400
        assert len(attempts) == 1
        assert attempts[0]["response_format"]["type"] == "json_schema"
    finally:
        client.close()


@pytest.mark.parametrize("transport", ["http", "sdk"])
@pytest.mark.parametrize("signature_chunk", [0, 1])
def test_stream_tool_extensions_preserve_google_thought_signature(transport, signature_chunk):
    deltas = [
        {"index": 0, "id": "google_call", "type": "function", "function": {"name": "clock", "arguments": '{"zone":'}},
        {"index": 0, "function": {"arguments": '"UTC"}'}},
    ]
    deltas[signature_chunk]["extra_content"] = {"google": {"thought_signature": "opaque-signature"}}
    deltas[0]["extra_content"] = {**deltas[0].get("extra_content", {}), "trace": {"origin": "first"}}
    deltas[1]["extra_content"] = {**deltas[1].get("extra_content", {}), "trace": {"tail": True}}
    chunks = [{"choices": [{"delta": {"tool_calls": [delta]},
                            "finish_reason": "tool_calls" if index == 1 else None}]}
              for index, delta in enumerate(deltas)]
    before = copy.deepcopy(chunks)
    result = generate(transport, chunks, request(stream=True))
    assert result.tool_calls[0].arguments == {"zone": "UTC"}
    call = result.raw["choices"][0]["message"]["tool_calls"][0]
    assert call["extra_content"] == {"google": {"thought_signature": "opaque-signature"},
                                     "trace": {"origin": "first", "tail": True}}
    assert call["function"] == {"name": "clock", "arguments": '{"zone":"UTC"}'}
    assert call["id"] == "google_call"
    assert call["type"] == "function"
    assert "index" not in call
    assert chunks == before
    followup = request()
    followup.messages = [result.raw["choices"][0]["message"],
                         {"role": "tool", "tool_call_id": "google_call", "content": "12:00"}]
    provider = CommonProvider(http_transport=SimpleNamespace()) if transport == "http" else SDK(http_transport=SimpleNamespace())
    encoded = provider._protocol_adapter().encode(followup, wire_stream=False)
    assert encoded["messages"][0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "opaque-signature"
