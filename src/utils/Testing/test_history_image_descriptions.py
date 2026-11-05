"""Older inline images in the prompt window become their stored descriptions."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from controllers.history_controller import HistoryController


def _image_part(url: str = "data:image/jpeg;base64,AAAA") -> dict:
    return {"type": "image_url", "image_url": {"url": url}}


def _part_types(content: list) -> list[str]:
    return [str(part.get("type") or "") for part in content if isinstance(part, dict)]


class HistoryImageDescriptionTests(unittest.TestCase):
    def _make_controller(self, settings: dict | None = None) -> HistoryController:
        controller = HistoryController.__new__(HistoryController)
        cfg = dict(settings or {})
        controller._get_setting = lambda key, default=None: cfg.get(key, default)
        return controller

    def test_older_image_is_replaced_with_stored_description(self):
        controller = self._make_controller()
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Look at this."}, _image_part()],
                "image_descriptions": {"auto": "A kitchen with an open fridge."},
            },
            {"role": "assistant", "content": "I see it."},
            {"role": "user", "content": [_image_part("data:image/jpeg;base64,BBBB")]},
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        content = result[0]["content"]
        self.assertEqual(_part_types(content), ["text", "text"])
        self.assertIn(
            "[Earlier image — description: A kitchen with an open fridge.]",
            content[1]["text"],
        )
        self.assertEqual(result[1], messages[1])

    def test_most_recent_image_stays_inline(self):
        controller = self._make_controller()
        messages = [
            {
                "role": "user",
                "content": [_image_part()],
                "image_descriptions": {"auto": "First frame."},
            },
            {
                "role": "user",
                "content": [_image_part("data:image/jpeg;base64,BBBB")],
                "image_descriptions": {"auto": "Second frame."},
            },
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        self.assertNotIn("image_url", _part_types(result[0]["content"]))
        self.assertIn("image_url", _part_types(result[1]["content"]))

    def test_image_without_description_is_left_untouched(self):
        controller = self._make_controller()
        message = {"role": "user", "content": [_image_part()]}

        result = controller._replace_older_images_with_descriptions([message])

        self.assertEqual(result, [message])

    def test_keep_recent_setting_can_disable_inline_images(self):
        controller = self._make_controller({"HISTORY_IMAGE_DESCRIPTION_KEEP_RECENT": 0})
        messages = [
            {
                "role": "user",
                "content": [_image_part()],
                "image_descriptions": {"auto": "Only frame."},
            },
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        self.assertNotIn("image_url", _part_types(result[0]["content"]))


if __name__ == "__main__":
    unittest.main()
