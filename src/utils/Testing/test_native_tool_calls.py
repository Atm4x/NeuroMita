"""Native tool calls: one call per turn, never mixed with a schema call."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from services.contracts import RuntimeCapabilities
from services.native_tool_calls import bridge_native_tool_response, resolve_tool_mode
from services.structured_response_capabilities import resolve_structured_response_capabilities


class _Settings:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class NativeToolBridgeTests(unittest.TestCase):
    def _profile(self, tools_mode='native'):
        return resolve_structured_response_capabilities(
            settings=_Settings(TOOLS_MODE=tools_mode),
            runtime=RuntimeCapabilities(connected=True, remote_only=False),
            character=SimpleNamespace(secret_capable=False, secret_revealed=False),
            structured_output=True,
            tools_enabled=True,
            enabled_tools=("load_skill",),
            tools_mode=tools_mode,
            tool_depth=0,
            tool_max_depth=2,
            images_available=False,
            has_custom_params=False,
            schema_reasoning=False,
        )

    def _request(self, tools_mode='native'):
        return SimpleNamespace(
            tools_mode=tools_mode,
            tools_on=tools_mode == 'native',
            tools_payload=[{"type": "function", "function": {
                "name": "load_skill", "description": "", "parameters": {},
            }}],
            dialect_id='openai_chat_completions',
            messages=[],
            extra={"tool_mode": {"effective": tools_mode}},
            capabilities={"structured_response_profile": self._profile(tools_mode)},
        )

    def _response(self, text, calls):
        return SimpleNamespace(text=text, raw={}, protocol_history=[], tool_calls=calls)

    @staticmethod
    def _call(name='load_skill', call_id='call_1', arguments=None):
        return SimpleNamespace(
            id=call_id, name=name,
            arguments={"id": "wardrobe"} if arguments is None else arguments,
        )

    def test_a_single_native_call_reaches_the_structured_payload(self):
        response = self._response('{"segments": [{"text": "Смотрю."}]}', [self._call()])
        bridged = bridge_native_tool_response(response, self._request())
        data = json.loads(bridged.text)
        self.assertEqual(data["tool_call"], {"name": "load_skill", "args": {"id": "wardrobe"}})
        self.assertEqual(bridged.raw["native_tool_call"]["id"], "call_1")

    def test_two_native_calls_are_rejected(self):
        response = self._response('{"segments": [{"text": "Смотрю."}]}', [
            self._call(call_id='call_1'), self._call(call_id='call_2'),
        ])
        with self.assertRaises(ValueError):
            bridge_native_tool_response(response, self._request())

    def test_a_native_call_next_to_a_schema_call_is_rejected(self):
        response = self._response(
            '{"segments": [{"text": "Смотрю."}], '
            '"tool_call": {"name": "load_skill", "args": {"id": "wardrobe"}}}',
            [self._call()],
        )
        with self.assertRaises(ValueError):
            bridge_native_tool_response(response, self._request())

    def test_an_unadvertised_tool_is_rejected(self):
        response = self._response('{"segments": [{"text": "Смотрю."}]}', [self._call(name='web_search')])
        with self.assertRaises(ValueError):
            bridge_native_tool_response(response, self._request())


class ToolModeTests(unittest.TestCase):
    def test_gemini_always_uses_the_schema_path(self):
        capabilities = {"structured_response_profile": NativeToolBridgeTests()._profile("schema"),
                         "tools_native": True}
        decision = resolve_tool_mode(_Settings(TOOLS_MODE='native'), capabilities, 'gemini')
        self.assertEqual(decision['effective'], 'schema')


if __name__ == '__main__':
    unittest.main()
