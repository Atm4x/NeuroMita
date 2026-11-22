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

    def test_multi_image_message_is_left_untouched(self):
        controller = self._make_controller()
        messages = [
            {
                "role": "user",
                "content": [_image_part(), _image_part("data:image/jpeg;base64,BBBB")],
                "image_descriptions": {"normal": "One combined description."},
            },
            {"role": "user", "content": [_image_part("data:image/jpeg;base64,CCCC")]},
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        self.assertEqual(_part_types(result[0]["content"]).count("image_url"), 2)

    def test_best_description_variant_is_used(self):
        controller = self._make_controller({"HISTORY_IMAGE_DESCRIPTION_KEEP_RECENT": 0})
        messages = [
            {
                "role": "user",
                "content": [_image_part()],
                "image_descriptions": {
                    "brief": "Brief variant.",
                    "normal": "Normal variant.",
                    "manual": "Manual variant.",
                },
            },
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        self.assertIn("Manual variant.", result[0]["content"][0]["text"])
        self.assertNotIn("Normal variant.", result[0]["content"][0]["text"])

    def test_player_image_wins_over_newer_assistant_image(self):
        controller = self._make_controller()
        messages = [
            {
                "role": "user",
                "content": [_image_part()],
                "image_descriptions": {"normal": "Player screenshot."},
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Look."}, _image_part("data:image/jpeg;base64,BBBB")],
                "image_descriptions": {"normal": "Mita camera frame."},
            },
        ]

        result = controller._replace_older_images_with_descriptions(messages)

        self.assertIn("image_url", _part_types(result[0]["content"]))
        self.assertNotIn("image_url", _part_types(result[1]["content"]))
        self.assertIn("Mita camera frame.", result[1]["content"][1]["text"])

    def test_quality_reduction_still_applies_to_retained_image_with_description(self):
        controller = self._make_controller()
        messages = [
            {
                "role": "user",
                "content": [_image_part()],
                "image_descriptions": {"normal": "Retained frame."},
            },
        ]
        processed_quality: list[int] = []
        controller._process_image_quality = lambda data, quality: (
            processed_quality.append(quality),
            data,
        )[1]

        result = controller._apply_history_image_quality_reduction(
            messages,
            {
                "start_index": 0,
                "use_percentage": False,
                "min_quality": 30,
                "decrease_rate": 5,
                "screen_capture_quality": 75,
            },
        )

        self.assertEqual(processed_quality, [75])
        self.assertIn("image_url", _part_types(result[0]["content"]))


if __name__ == "__main__":
    unittest.main()
