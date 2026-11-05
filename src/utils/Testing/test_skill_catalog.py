"""Skill catalog loading, validation and prompt rendering."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from services.skill_catalog import SkillCatalog


def _write_catalog(root: Path, skills: list[dict], files: dict[str, str]) -> None:
    skills_dir = root / "Skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = skills_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (skills_dir / "catalog.json").write_text(
        json.dumps({"version": 1, "skills": skills}, ensure_ascii=False),
        encoding="utf-8",
    )


class SkillCatalogTests(unittest.TestCase):
    def test_missing_catalog_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = SkillCatalog.load(tmp)
            self.assertFalse(catalog)
            self.assertEqual(catalog.entries, {})
            self.assertEqual(catalog.render_catalog_block(), "")

    def test_valid_entries_are_loaded_with_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(
                root,
                [
                    {"id": "music", "title": "Music", "file": "music.md", "capabilities": ["music"]},
                    {"id": "wardrobe", "title": "Wardrobe", "file": "deep/wardrobe.txt"},
                ],
                {"music.md": "Pick a track that fits the mood.", "deep/wardrobe.txt": "Offer two outfits."},
            )
            catalog = SkillCatalog.load(root)
            self.assertTrue(catalog)
            self.assertEqual(sorted(catalog.entries), ["music", "wardrobe"])
            music = catalog.get("music")
            self.assertEqual(music.title, "Music")
            self.assertEqual(music.content, "Pick a track that fits the mood.")
            self.assertEqual(len(music.content_hash), 64)
            self.assertGreater(music.token_estimate, 0)

    def test_entry_escaping_the_catalog_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "secret.md").write_text("secret", encoding="utf-8")
            _write_catalog(root, [{"id": "leak", "file": "../secret.md"}], {})
            catalog = SkillCatalog.load(root)
            self.assertFalse(catalog)
            self.assertTrue(any("escapes" in issue for issue in catalog.issues))

    def test_disallowed_suffix_and_missing_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(
                root,
                [
                    {"id": "binary", "file": "tool.exe"},
                    {"id": "gone", "file": "missing.md"},
                ],
                {"tool.exe": "MZ"},
            )
            catalog = SkillCatalog.load(root)
            self.assertFalse(catalog)
            self.assertEqual(len(catalog.issues), 2)

    def test_duplicate_and_empty_entries_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(
                root,
                [
                    {"id": "music", "file": "music.md"},
                    {"id": "music", "file": "music2.md"},
                    {"id": "blank", "file": "blank.md"},
                ],
                {"music.md": "First", "music2.md": "Second", "blank.md": "   "},
            )
            catalog = SkillCatalog.load(root)
            self.assertEqual(list(catalog.entries), ["music"])
            self.assertEqual(catalog.get("music").content, "First")
            self.assertTrue(any("duplicate" in issue for issue in catalog.issues))

    def test_catalog_block_is_compact_and_filtered_by_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(
                root,
                [
                    {"id": "music", "title": "Music", "file": "music.md", "capabilities": ["music"]},
                    {"id": "wardrobe", "title": "Wardrobe", "file": "wardrobe.md"},
                ],
                {"music.md": "m", "wardrobe.md": "w"},
            )
            catalog = SkillCatalog.load(root)
            block = catalog.render_catalog_block()
            self.assertIn("[SKILLS]", block)
            self.assertIn("- music: Music", block)
            self.assertIn("- wardrobe: Wardrobe", block)
            self.assertIn("[/SKILLS]", block)

            filtered = catalog.render_catalog_block(capabilities=["music"])
            self.assertIn("music", filtered)
            self.assertNotIn("wardrobe", filtered)

            tiny = catalog.render_catalog_block(max_chars=200)
            self.assertLessEqual(len(tiny), 260)

    def test_body_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(
                root,
                [{"id": "long", "file": "long.md"}],
                {"long.md": "x" * 50},
            )
            entry = SkillCatalog.load(root).get("long")
            self.assertEqual(len(entry.render_body(max_chars=40)), 40)


class RuntimePayloadCatalogTests(unittest.TestCase):
    PAYLOAD = {
        "skills": [
            {"id": "music", "title": "Music", "body": "Pick a calm track."},
            {"id": "wardrobe", "title": "Wardrobe", "body": "Offer two outfits.", "capabilities": ["wardrobe"]},
        ]
    }

    def test_payload_builds_entries_without_files(self):
        catalog = SkillCatalog.from_payload(self.PAYLOAD)
        self.assertEqual(sorted(catalog.entries), ["music", "wardrobe"])
        self.assertEqual(catalog.get("music").content, "Pick a calm track.")
        self.assertEqual(len(catalog.get("music").content_hash), 64)

    def test_payload_accepts_a_json_string(self):
        import json
        catalog = SkillCatalog.from_payload(json.dumps(self.PAYLOAD))
        self.assertTrue(catalog)

    def test_payload_rejects_missing_body_and_bad_ids(self):
        catalog = SkillCatalog.from_payload({"skills": [
            {"id": "empty", "title": "Empty"},
            {"id": "Bad Id", "body": "x"},
            {"id": "ok", "body": "y"},
        ]})
        self.assertEqual(list(catalog.entries), ["ok"])
        self.assertEqual(len(catalog.issues), 2)

    def test_empty_payload_is_falsy_but_not_an_error(self):
        catalog = SkillCatalog.from_payload([])
        self.assertFalse(catalog)


if __name__ == "__main__":
    unittest.main()
