"""Skill retention, the load_skill tool and the rendered prompt blocks."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from managers.character_resource_manager import get_character_resource_manager
from managers.skill_session_manager import SkillSessionManager
from managers.tools.builtin.load_skill import LoadSkillTool
from services.skill_catalog import SkillCatalog


def _prompt_set(root: Path, skills: list[dict], files: dict[str, str]) -> None:
    skills_dir = root / "Skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (skills_dir / name).write_text(content, encoding="utf-8")
    (skills_dir / "catalog.json").write_text(
        json.dumps({"skills": skills}, ensure_ascii=False), encoding="utf-8"
    )


class SkillSessionTests(unittest.TestCase):
    def _session(self):
        return SkillSessionManager().bind("Mita", "Mita")

    def test_only_the_two_newest_skills_are_retained(self):
        session = self._session()
        for skill_id in ("music", "wardrobe", "tv"):
            session.remember(skill_id, tokens=10)
        self.assertEqual(session.loaded(), ["wardrobe", "tv"])

    def test_reloading_moves_a_skill_to_the_end(self):
        session = self._session()
        session.remember("music", tokens=10)
        session.remember("wardrobe", tokens=10)
        session.remember("music", tokens=10)
        self.assertEqual(session.loaded(), ["wardrobe", "music"])

    def test_token_budget_evicts_the_oldest_skill(self):
        session = self._session()
        session.remember("heavy", tokens=1800)
        session.remember("light", tokens=400)
        self.assertEqual(session.loaded(), ["light"])

    def test_clear_forgets_everything(self):
        session = self._session()
        session.remember("music", tokens=10)
        session.clear()
        self.assertEqual(session.loaded(), [])


class LoadSkillToolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _prompt_set(
            self.root,
            [
                {"id": "music", "title": "Music", "file": "music.md"},
                {"id": "wardrobe", "title": "Wardrobe", "file": "wardrobe.md"},
            ],
            {"music.md": "Pick a calm track.", "wardrobe.md": "Offer two outfits."},
        )
        self.char_id = "SkillTestChar"
        self.resources = get_character_resource_manager()
        self.resources.register_character(self.char_id, self.char_id, str(self.root))
        self.tool = LoadSkillTool()
        self.tool.set_char_id(self.char_id)
        self.tool.set_prompt_set_path(str(self.root))

    def tearDown(self):
        self.resources.loaded_skills_for(self.char_id).clear()
        self._tmp.cleanup()

    def test_loading_returns_the_body_and_remembers_the_skill(self):
        result = self.tool.run(id="music")
        self.assertIn("Pick a calm track.", result)
        self.assertIn("skill: Music", result)
        self.assertEqual(self.resources.loaded_skills_for(self.char_id).loaded(), ["music"])

    def test_unknown_skill_lists_what_exists(self):
        result = self.tool.run(id="dance")
        self.assertIn("Unknown skill", result)
        self.assertIn("music", result)
        self.assertEqual(self.resources.loaded_skills_for(self.char_id).loaded(), [])

    def test_parameters_enumerate_catalog_ids(self):
        params = self.tool.parameters
        self.assertEqual(params["properties"]["id"]["enum"], ["music", "wardrobe"])
        self.assertEqual(params["required"], ["id"])

    def test_missing_catalog_is_reported(self):
        self.tool.set_prompt_set_path(str(self.root / "nowhere"))
        self.assertIn("no skill catalog", self.tool.run(id="music"))


class LoadedSkillsPromptTests(unittest.TestCase):
    def test_loaded_block_contains_only_retained_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prompt_set(
                root,
                [
                    {"id": "music", "title": "Music", "file": "music.md"},
                    {"id": "wardrobe", "title": "Wardrobe", "file": "wardrobe.md"},
                ],
                {"music.md": "Pick a calm track.", "wardrobe.md": "Offer two outfits."},
            )
            catalog = SkillCatalog.load(root)
            block = catalog.render_loaded_block(["wardrobe"])
            self.assertIn("[LOADED SKILLS]", block)
            self.assertIn("Offer two outfits.", block)
            self.assertNotIn("Pick a calm track.", block)
            self.assertEqual(catalog.render_loaded_block(["missing"]), "")

    def test_eager_block_contains_every_catalog_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prompt_set(
                root,
                [
                    {"id": "music", "title": "Music", "file": "music.md"},
                    {"id": "wardrobe", "title": "Wardrobe", "file": "wardrobe.md"},
                ],
                {"music.md": "Pick a calm track.", "wardrobe.md": "Offer two outfits."},
            )
            catalog = SkillCatalog.load(root)
            block = catalog.render_loaded_block(sorted(catalog.entries), max_chars=4000)
            self.assertIn("Pick a calm track.", block)
            self.assertIn("Offer two outfits.", block)


class PromptIntegrationTests(unittest.TestCase):
    class _Character:
        char_id = "SkillPrompt"
        id = "SkillPrompt"

        def __init__(self, path, loaded):
            self.base_data_path = str(path)
            self.skills = self
            self._loaded = list(loaded)

        def loaded(self):
            return list(self._loaded)

        def get_variable(self, _name, default=None):
            return default

    def _texts(self, policy=None):
        from controllers.prompt_controller import PromptController
        from core.request_policy import RequestPolicy
        from services.contracts import PromptBuildRequest

        controller = PromptController()
        controller._build_system_messages = lambda *_a, **_k: ([], [], [])
        controller._get_setting = lambda _key, default=None, *_a, **_k: default
        controller._build_system_state_message = lambda *_a, **_k: {
            "role": "system", "content": "[System State] skill prompt test"
        }
        result = controller.build(PromptBuildRequest(
            character=self.character,
            event_type="chat",
            policy=policy or RequestPolicy(use_history_in_prompt=False),
            user_input="hi",
            capabilities={
                "structured_output": True,
                "skills": True,
                "skill_mode": self.mode,
            },
        ))
        return [str(m.get("content") or "") for m in result.messages]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        _prompt_set(
            root,
            [{"id": "music", "title": "Music", "file": "music.md"}],
            {"music.md": "Pick a calm track."},
        )
        self.root = root
        self.mode = "on_demand"

    def tearDown(self):
        self._tmp.cleanup()

    def test_catalog_block_precedes_history_and_loaded_block_is_separate(self):
        self.character = self._Character(self.root, ["music"])
        texts = self._texts()
        joined = "\n".join(texts)
        self.assertIn("[SKILLS]", joined)
        self.assertIn("- music: Music", joined)
        self.assertIn("[LOADED SKILLS]", joined)
        self.assertIn("Pick a calm track.", joined)
        self.assertLess(joined.index("[SKILLS]"), joined.index("[LOADED SKILLS]"))

    def test_eager_mode_embeds_bodies_without_catalog(self):
        self.mode = "eager"
        self.character = self._Character(self.root, [])
        texts = self._texts()
        joined = "\n".join(texts)
        self.assertIn("[LOADED SKILLS]", joined)
        self.assertIn("Pick a calm track.", joined)
        self.assertNotIn("[SKILLS]", joined.replace("[LOADED SKILLS]", ""))


if __name__ == "__main__":
    unittest.main()
