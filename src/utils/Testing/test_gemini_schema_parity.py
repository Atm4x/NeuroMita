"""Guards for the Gemini schema converter.

``_to_gemini_schema`` collapses unions: a nullable ``anyOf`` becomes
``nullable`` and any other multi-member ``anyOf`` keeps only its first
non-null member. That fallback is fine for today's schema because the two
free-form fields are patched explicitly, but a new union must not be dropped
silently. This test fails when such a union appears without a dedicated patch.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from schemas.structured_response import StructuredResponse


def _multi_member_unions(node, path=""):
    found = []
    if isinstance(node, dict):
        members = node.get("anyOf")
        if isinstance(members, list):
            non_null = [
                member for member in members
                if member != {"type": "null"} and member.get("type") != "null"
            ]
            if len(non_null) > 1:
                found.append(path)
        for key, value in node.items():
            if key in {"properties", "$defs"} and isinstance(value, dict):
                for name, child in value.items():
                    found.extend(_multi_member_unions(child, f"{path}/{key}/{name}"))
            elif key == "items":
                found.extend(_multi_member_unions(value, f"{path}[]"))
            elif isinstance(value, dict):
                found.extend(_multi_member_unions(value, f"{path}/{key}"))
    return found


class GeminiSchemaParityTests(unittest.TestCase):
    def test_only_known_union_is_collapsed(self):
        hits = _multi_member_unions(StructuredResponse.model_json_schema())
        self.assertEqual(hits, ["/$defs/ToolCall/properties/args"])

    def test_free_form_fields_are_explicitly_patched(self):
        schema = StructuredResponse.gemini_schema_dict()
        self.assertEqual(
            schema["properties"]["tool_call"]["properties"]["args"]["type"],
            "string",
        )
        payload = (
            schema["properties"]["segments"]["items"]
            ["properties"]["intents"]["items"]["properties"]["payload"]
        )
        self.assertEqual(payload["type"], "string")

    def test_optional_working_state_stays_nullable(self):
        schema = StructuredResponse.gemini_schema_dict()
        working_state = schema["properties"]["working_state"]
        self.assertTrue(working_state.get("nullable"))
        self.assertIn("properties", working_state)


if __name__ == "__main__":
    unittest.main()
