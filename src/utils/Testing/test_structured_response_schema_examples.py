"""Examples in the structured-response schema match the declared field types."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from schemas.structured_response import StructuredResponse


class StructuredResponseSchemaExampleTests(unittest.TestCase):
    _LIST_FIELDS = (
        "memory_add",
        "memory_update",
        "memory_delete",
        "memory_merge",
        "reminder_add",
        "reminder_delete",
        "entities",
        "relations",
    )

    def test_list_fields_show_array_examples(self):
        properties = StructuredResponse.model_json_schema()["properties"]
        for name in self._LIST_FIELDS:
            with self.subTest(field=name):
                description = str(properties[name].get("description") or "")
                match = re.search(r"Example:\s*(\[[^\]]*\])", description)
                self.assertIsNotNone(match, f"{name}: example is missing")
                example = match.group(1).strip()
                self.assertTrue(
                    example.startswith("["),
                    f"{name}: list field must show a JSON array, got {example!r}",
                )
                self.assertTrue(example.endswith("]"),
                                f"{name}: unexpected example {example!r}")


if __name__ == "__main__":
    unittest.main()
