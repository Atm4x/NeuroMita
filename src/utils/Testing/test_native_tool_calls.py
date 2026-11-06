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
from services.native_tool_calls import (
    bridge_native_tool_response,
    native_tool_followup_messages,
    persisted_native_tool_messages,
    resolve_tool_mode,
)
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


class NativeSkillHistoryTests(unittest.TestCase):
    def test_newly_loaded_skill_is_available_and_labeled_in_current_turn(self):
        call = {"id": "call_skill", "name": "load_skill", "arguments": {"ids": ["tv"]}}
        body = "[skill: TV]\nAuthored instructions.\n\nUse the remote."
        assistant, reply = native_tool_followup_messages(call, body)
        self.assertEqual(assistant["tool_calls"][0]["id"], "call_skill")
        self.assertEqual(reply["role"], "tool")
        self.assertEqual(reply["tool_call_id"], "call_skill")
        self.assertIn(body, reply["content"])
        self.assertTrue(reply["content"].startswith("[LOADED SKILLS]\n"))
        self.assertTrue(reply["content"].endswith("\n[/LOADED SKILLS]"))

    def test_old_skill_instructions_are_not_replayed(self):
        call = {"id": "call_skill", "name": "load_skill", "arguments": {"ids": ["tv"]}}
        body = "[skill: TV]\nAn instruction that must not persist."
        original = native_tool_followup_messages(call, body)
        history = persisted_native_tool_messages({"native_tool_history": original})
        self.assertEqual(history[0], original[0])
        self.assertEqual(history[1]["tool_call_id"], "call_skill")
        self.assertIn("load_skill again", history[1]["content"])
        self.assertNotIn("must not persist", history[1]["content"])
        # The current tool response was not edited by history projection.
        self.assertIn("must not persist", original[1]["content"])

    def test_non_skill_native_results_are_preserved(self):
        call = {"id": "call_search", "name": "web_search", "arguments": {"query": "hi"}}
        original = native_tool_followup_messages(call, "Web search result")
        history = persisted_native_tool_messages({"native_tool_history": original})
        self.assertEqual(history, original)

    def test_error_results_are_not_wrapped_as_skill_instructions(self):
        call = {"id": "call_skill", "name": "load_skill", "arguments": {"ids": ["missing"]}}
        result = native_tool_followup_messages(call, "[load_skill] Unknown skill.")
        self.assertEqual(result[1]["content"], "[load_skill] Unknown skill.")


class ToolModeTests(unittest.TestCase):
    def test_gemini_always_uses_the_schema_path(self):
        capabilities = {"structured_response_profile": NativeToolBridgeTests()._profile("schema"),
                         "tools_native": True}
        decision = resolve_tool_mode(_Settings(TOOLS_MODE='native'), capabilities, 'gemini')
        self.assertEqual(decision['effective'], 'schema')


if __name__ == '__main__':
    unittest.main()
