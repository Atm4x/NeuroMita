from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from schemas.structured_response import StructuredResponse, build_structured_response_model
from schemas.sparse_structured_response import build_sparse_response_model, normalize_sparse_response
from services.contracts import RuntimeCapabilities
from services.structured_response_capabilities import resolve_structured_response_capabilities
from utils.structured_response_parser import parse_structured_response_with_meta, StructuredResponseParseError


def profile(**settings):
    return resolve_structured_response_capabilities(
        settings=settings, runtime=RuntimeCapabilities(connected=True, remote_only=False),
        character=SimpleNamespace(secret_capable=False, secret_revealed=False),
        structured_output=True, tools_enabled=True, enabled_tools=("calculator",),
        tools_mode="schema", tool_depth=0, tool_max_depth=2, images_available=True,
        has_custom_params=False, schema_reasoning=False,
    ).with_prompt_intents(True)


def test_neutral_reply_has_only_two_root_fields_and_normalizes_defaults():
    caps = profile()
    wire = build_sparse_response_model(StructuredResponse, caps)
    schema = wire.openai_response_format()["json_schema"]
    assert schema["strict"] is True
    assert set(schema["schema"]["properties"]) == {"segments", "events"}
    assert set(schema["schema"]["properties"]["segments"]["items"]["properties"]) == {"text"}
    outcome = parse_structured_response_with_meta(
        '{"segments":[{"text":"Hello"}],"events":[]}', profile=caps,
    )
    assert outcome.control_plane_trusted
    assert outcome.response.full_text() == "Hello"
    assert outcome.response.attitude_change == 0
    assert outcome.response.memory_add is None


def test_events_preserve_segment_positions_lists_and_memory_semantics():
    data = {"segments": [{"text": "First"}, {"text": "Second"}], "events": [
        {"type": "commands", "segment": 1, "value": "camera_snapshot"},
        {"type": "music", "segment": 0, "value": "Calm"},
        {"type": "target", "segment": 1, "value": "Kind"},
        {"type": "memory_add", "value": "island:language|Русский"},
        {"type": "memory_add", "value": "normal|Tea"},
        {"type": "attitude_change", "value": 1.5},
        {"type": "intents", "segment": 1, "intent_type": "inventory.collect", "payload": '{"object":"Cat"}'},
    ]}
    response = StructuredResponse.model_validate(normalize_sparse_response(data, StructuredResponse, profile()))
    assert response.segments[0].commands == []
    assert response.segments[1].commands == ["camera_snapshot"]
    assert response.segments[1].target == "Kind"
    assert response.segments[1].intents[0].payload == {"object": "Cat"}
    assert response.memory_add == ["island:language|Русский", "normal|Tea"]
    assert response.attitude_change == 1.5


@pytest.mark.parametrize("event", [
    {"type": "commands", "segment": -1, "value": "x"},
    {"type": "commands", "segment": 1, "value": "x"},
    {"type": "commands", "segment": True, "value": "x"},
    {"type": "memory_add", "value": 12},
    {"type": "unknown", "value": "x"},
    {"type": "tool_call", "name": "calculator", "args": "[]"},
    {"type": "intents", "segment": 0, "intent_type": "x", "payload": "broken"},
])
def test_invalid_sparse_event_is_rejected_before_execution(event):
    raw = json.dumps({"segments": [{"text": "Hi"}], "events": [event]})
    with pytest.raises(StructuredResponseParseError) as exc:
        parse_structured_response_with_meta(raw, profile=profile())
    assert exc.value.code == "structured_sparse_invalid"


def test_duplicates_and_mixed_formats_are_rejected():
    for data in (
        {"segments": [{"text": "Hi"}], "events": [
            {"type": "stress_change", "value": 1}, {"type": "stress_change", "value": 2}]},
        {"segments": [{"text": "Hi", "commands": ["x"]}], "events": []},
        {"segments": [{"text": "Hi"}], "events": [], "memory_add": ["x"]},
    ):
        with pytest.raises((ValidationError, ValueError)):
            normalize_sparse_response(data, StructuredResponse, profile())


def test_schema_contains_only_enabled_events_and_all_objects_are_closed():
    caps = profile(REMINDERS_ENABLED=False, ENABLE_GAMES=False)
    schema = build_sparse_response_model(StructuredResponse, caps).gemini_schema_dict()
    variants = schema["properties"]["events"]["items"]["anyOf"]
    names = {variant["properties"]["type"]["enum"][0] for variant in variants}
    assert "memory_add" in names
    assert not names & {"entities", "relations", "reminder_add", "reminder_delete", "timer_add", "start_game", "end_game"}
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            assert "$ref" not in node
            assert "default" not in node
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(schema)
    exhausted = build_sparse_response_model(StructuredResponse, caps.at_tool_depth(2)).gemini_schema_dict()
    assert "tool_call" not in {v["properties"]["type"]["enum"][0] for v in exhausted["properties"]["events"]["items"]["anyOf"]}


def test_secret_and_custom_fields_keep_their_explicit_decisions_and_constraints():
    from dataclasses import replace
    caps = replace(profile(), excluded_fields=tuple(n for n in profile().excluded_fields if n not in {"secret_exposed", "custom_fields"}),
        required_fields=("secret_exposed",), has_custom_params=True)
    internal = build_structured_response_model([{"name": "trust", "type": "float", "required": True, "change_min": 0, "change_max": 10}])
    wire = build_sparse_response_model(internal, caps)
    data = {"segments": [{"text": "Hi"}], "events": [], "secret_exposed": None, "custom_fields": {"trust": 3}}
    response = internal.model_validate(normalize_sparse_response(data, internal, caps))
    assert response.custom_fields.trust == 3
    schema = wire.openai_response_format()["json_schema"]["schema"]
    assert "secret_exposed" in schema["required"]
    assert {"type": "null"} in schema["properties"]["secret_exposed"]["anyOf"]
    with pytest.raises(ValidationError):
        wire.model_validate({k: v for k, v in data.items() if k != "secret_exposed"})
    with pytest.raises(ValidationError):
        wire.model_validate({**data, "custom_fields": {"trust": 99}})


def test_legacy_and_repaired_trust_are_preserved():
    legacy = parse_structured_response_with_meta('{"segments":[{"text":"Hi","commands":["x"]}],"attitude_change":1}')
    assert legacy.response.segments[0].commands == ["x"]
    assert legacy.control_plane_trusted
    repaired = parse_structured_response_with_meta('{"segments":[{"text":"Hi"}],"events":[],}', profile=profile())
    assert repaired.response.full_text() == "Hi"
    assert not repaired.control_plane_trusted


def test_disabled_variant_is_rejected_and_internal_result_shape_stays_full():
    from utils.structured_response_parser import structured_response_to_result_dict
    caps = profile(REMINDERS_ENABLED=False)
    with pytest.raises(StructuredResponseParseError):
        parse_structured_response_with_meta(json.dumps({"segments": [{"text": "Hi"}], "events": [
            {"type": "timer_add", "value": "5|Hello"}]}), profile=caps)
    response = parse_structured_response_with_meta('{"segments":[{"text":"Hi"}],"events":[]}', profile=caps).response
    saved = structured_response_to_result_dict(response)
    assert "events" not in saved
    assert saved["memory_add"] == []
    assert saved["attitude_change"] == 0
    assert "commands" not in saved["segments"][0]


def test_working_state_and_image_events_normalize_to_full_models():
    caps = profile(ENABLE_WORKING_STATE=True, IMAGE_INLINE_DESCRIPTION=True)
    data = {"segments": [{"text": "Hello"}], "events": [
        {"type": "image_description", "value": "A cat"},
        {"type": "working_state", "value": {"focus": "Tea", "situation": [], "assumptions": [], "open_loops": [], "next_steps": []}},
    ]}
    response = parse_structured_response_with_meta(json.dumps(data), profile=caps).response
    assert response.working_state.focus == "Tea"
    assert response.image_description == "A cat"


def test_sparse_contract_and_stream_filter_do_not_expose_events_as_speech():
    from services.sparse_response_prompt import render_sparse_response_contract
    from controllers.chat_controller import StructuredJsonStreamFilter
    contract = render_sparse_response_contract(profile())
    assert '"type": "memory_add"' in contract
    assert '"type": "timer_add"' in contract
    assert '"type": "entities"' not in contract
    assert "primary conversation language" in contract
    assert "zero-based" in contract
    state_contract = render_sparse_response_contract(profile(ENABLE_WORKING_STATE=True))
    assert '"focus"' in state_contract
    assert '"next_steps"' in state_contract
    exhausted = render_sparse_response_contract(profile().at_tool_depth(2))
    assert '"type": "tool_call"' not in exhausted
    raw = json.dumps({"segments": [{"text": "Hello"}], "events": [{"type": "memory_add", "value": "normal|secret technical text"}]})
    stream = StructuredJsonStreamFilter()
    pieces = []
    for char in raw:
        pieces.extend(stream.feed(char))
    pieces.extend(stream.flush_visible())
    assert "".join(value for channel, value in pieces if channel == "content").strip() == "Hello"


def test_gamemaster_and_legacy_provider_selection_remain_unchanged():
    from schemas.game_master_response import GameMasterResponse
    from schemas.sparse_structured_response import provider_structured_model
    assert provider_structured_model(GameMasterResponse, {"structured_response_profile": profile()}) is GameMasterResponse
    assert provider_structured_model(StructuredResponse, {}) is StructuredResponse
    assert provider_structured_model(StructuredResponse, {"structured_response_profile": profile()}) is build_sparse_response_model(StructuredResponse, profile())


def test_openai_http_and_sdk_and_gemini_send_same_sparse_union():
    import httpx
    from handlers.llm_providers.base import LLMRequest
    from handlers.llm_providers.common_provider import CommonProvider
    from handlers.llm_providers.gemini_provider import GeminiProvider
    from handlers.llm_providers.openai_compatible import OpenAICompatibleProvider
    from unittest.mock import Mock

    caps = {"structured_output": True, "structured_response_profile": profile()}
    req = LLMRequest(model="test", messages=[], capabilities=caps, structured_model=StructuredResponse,
        api_url="https://example.test", provider_name="common")
    transport = Mock()
    http_provider = CommonProvider(http_transport=transport)
    expected = http_provider._build_payload(req, "test", [])["response_format"]
    assert expected["json_schema"]["strict"] is True
    captured = {}

    class SDK(OpenAICompatibleProvider):
        name = "mock"
        def is_applicable(self, req):
            return True
        def _get_client(self, req):
            client = Mock()
            def create(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"segments":[{"text":"Hi"}],"events":[]}'), finish_reason="stop")], usage=None, model="test")
            client.chat.completions.create.side_effect = create
            return client

    assert SDK(http_transport=transport).generate(req).text
    assert captured["response_format"] == expected
    transport.post_json.return_value = httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]})
    req.provider_name = "gemini"
    GeminiProvider(http_transport=transport).generate(req)
    gemini_schema = transport.post_json.call_args.kwargs["payload"]["generationConfig"]["responseJsonSchema"]
    assert gemini_schema == expected["json_schema"]["schema"]


@pytest.mark.parametrize("support_intents", [False, True])
def test_prompt_controller_renders_sparse_contract_after_template_intent_resolution(support_intents):
    from controllers.prompt_controller import PromptController
    from DSL.dsl_engine import DslInterpreter
    from core.request_policy import RequestPolicy
    script = Path(__file__).resolve().parents[3] / "extra" / "Prompts" / "Structural" / "response_format_json.script"
    class Resolver:
        def resolve_path(self, path):
            return path
        def load_text(self, path, _context):
            return f"support_intents={support_intents}\n[<format.script>]" if path == "main_template.txt" else script.read_text(encoding="utf-8")
        def get_dirname(self, _path):
            return ""
    variables = {}
    character = SimpleNamespace(char_id="Test", base_data_path="unused", main_template_path_relative="main_template.txt",
        variables=variables, app_vars={}, custom_params=[],
        set_variable=lambda key, value: variables.update({key: value}))
    character.dsl_interpreter = DslInterpreter(character, Resolver())
    controller = PromptController()
    controller._setup_character_for_prompt = lambda *args, **kwargs: None
    controller._apply_reply_defaults = lambda *args: None
    controller._resolve_examples_profile = lambda *args: "none"
    caps = {"structured_output": True, "structured_response_profile": profile(), "structured_prompt_features": profile().prompt_features()}
    stable, volatile, _ = controller._build_system_messages(character, "chat", True, RequestPolicy(), caps)
    text = "\n".join(message["content"] for message in stable + volatile)
    assert "sparse_events_v1" in text
    assert "All other segment fields are optional" not in text
    assert '"attitude_change": <number' not in text
    assert ('"type": "intents"' in text) == support_intents
    assert "response_sparse_format" not in variables
    assert "25-70 words total" in text
    caps["structured_output"] = False
    stable, _, _ = controller._build_system_messages(character, "chat", True, RequestPolicy(), caps)
    assert "sparse_events_v1" not in "\n".join(message["content"] for message in stable)


def test_reasoning_order_is_preserved_for_streaming():
    from dataclasses import replace
    caps = replace(profile(), schema_reasoning=True,
        excluded_fields=tuple(name for name in profile().excluded_fields if name != "reasoning"))
    schema = build_sparse_response_model(StructuredResponse, caps).json_schema_dict()
    assert next(iter(schema["properties"])) == "reasoning"
