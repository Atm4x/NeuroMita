from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from controllers.gui.app_shell_controller import AppShellController
from controllers.model_controller import ModelController
from core.image_assets import (
    BMP,
    GIF,
    JPEG,
    PNG,
    WEBP,
    detect_image_mime,
    image_bytes_to_data_url,
    split_data_url,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 8
GIF_BYTES = b"GIF89a" + b"\x00" * 8
BMP_BYTES = b"BM" + b"\x00" * 8
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8


class ImageMimeTests(unittest.TestCase):
    """PNG из буфера обмена не должен уезжать провайдеру как image/jpeg."""

    def test_mime_is_detected_by_signature(self):
        for payload, expected in (
            (PNG_BYTES, PNG),
            (JPEG_BYTES, JPEG),
            (GIF_BYTES, GIF),
            (BMP_BYTES, BMP),
            (WEBP_BYTES, WEBP),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(expected, detect_image_mime(payload))

    def test_data_url_carries_the_real_mime(self):
        self.assertTrue(image_bytes_to_data_url(PNG_BYTES).startswith("data:image/png;base64,"))
        self.assertTrue(image_bytes_to_data_url(JPEG_BYTES).startswith("data:image/jpeg;base64,"))

    def test_unknown_signature_falls_back_to_jpeg_and_is_not_empty(self):
        url = image_bytes_to_data_url(b"not an image")
        mime, payload = split_data_url(url)
        self.assertEqual(JPEG, mime)
        self.assertEqual(b"not an image", base64.b64decode(payload))

    def test_split_data_url_rejects_plain_links(self):
        self.assertIsNone(split_data_url("https://example.test/a,b.png"))
        self.assertIsNone(split_data_url(""))
        self.assertIsNone(split_data_url("data:image/png;base64"))

    def test_split_data_url_returns_mime_and_payload(self):
        self.assertEqual(
            ("image/webp", "AAAA"),
            split_data_url("data:image/webp;base64,AAAA"),
        )


class ImageFallbackDecisionTests(unittest.TestCase):
    """Изображения исчезают только вместе с пригодным описанием."""

    def test_placeholder_descriptions_are_not_usable(self):
        self.assertFalse(ModelController._description_is_usable("[Image 1: description unavailable]"))
        self.assertFalse(ModelController._description_is_usable("[Scene description unavailable]"))
        self.assertFalse(ModelController._description_is_usable("   "))
        self.assertTrue(ModelController._description_is_usable("На столе стоит чашка."))

    def test_described_images_are_replaced_by_text(self):
        self.assertEqual(
            "described",
            ModelController._image_fallback_decision(described=True, native_vision=False),
        )

    def test_failed_description_keeps_images_for_a_native_vision_model(self):
        self.assertEqual(
            "keep_images",
            ModelController._image_fallback_decision(described=False, native_vision=True),
        )

    def test_failed_description_withholds_images_for_a_text_model(self):
        self.assertEqual(
            "withhold_images",
            ModelController._image_fallback_decision(described=False, native_vision=False),
        )


class AttachedImagesLabelTests(unittest.TestCase):
    def test_single_image_label_is_singular(self):
        self.assertEqual("<Прикреплённое изображение>", AppShellController._attached_images_label(1))

    def test_several_images_label_reports_quantity(self):
        for count in (2, 3, 5):
            with self.subTest(count=count):
                self.assertEqual(
                    f"<Прикреплено изображений: {count}>",
                    AppShellController._attached_images_label(count),
                )


if __name__ == "__main__":
    unittest.main()
