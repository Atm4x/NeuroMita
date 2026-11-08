"""A versioned Unity contract defers mechanic text to skills."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from controllers.prompt_controller import PromptController
from services.skill_catalog import SkillCatalog


def _catalog(*skills: tuple[str, str]) -> SkillCatalog:
    return SkillCatalog.from_payload({
        "skills": [{"id": skill_id, "title": skill_id, "body": body} for skill_id, body in skills],
    })


class SceneMechanicsContractTests(unittest.TestCase):
    MECHANICS = [
        {"mechanic": "tv", "skill": "tv", "state": "available"},
        {"mechanic": "easel", "skill": "easel", "state": "available"},
    ]

    def _messages(self, game_state, *, capabilities, catalog=None):
        return PromptController._build_unity_scene_mechanics_messages(
            game_state, capabilities=capabilities, skill_catalog=catalog,
        )

    def test_an_old_payload_renders_nothing_extra(self):
        messages = self._messages(
            {"intent_rules": "old contract"},
            capabilities={"skills": True, "skill_mode": "on_demand"},
            catalog=_catalog(("tv", "TV body")),
        )

        self.assertEqual(messages, [])

    def test_on_demand_mode_asks_for_a_skill_load(self):
        messages = self._messages(
            {"prompt_contract_version": 2, "scene_mechanics": self.MECHANICS},
            capabilities={"skills": True, "skill_mode": "on_demand"},
            catalog=_catalog(("tv", "TV body"), ("easel", "Easel body")),
        )

        text = messages[0]["content"]
        self.assertIn("[Unity Scene Mechanics]", text)
        self.assertIn("tv (skill tv)", text)
        self.assertIn("load_skill", text)
        self.assertIn("Do not invent argument names.", text)
        self.assertNotIn("TV body", text)

    def test_eager_mode_points_at_the_inlined_bodies(self):
        messages = self._messages(
            {"prompt_contract_version": 2, "scene_mechanics": self.MECHANICS},
            capabilities={"skills": True, "skill_mode": "eager"},
            catalog=_catalog(("tv", "TV body")),
        )

        text = messages[0]["content"]
        self.assertIn("already included above", text)
        self.assertNotIn("load_skill", text)
        self.assertNotIn("TV body", text)

    def test_without_tools_the_bodies_are_inlined(self):
        messages = self._messages(
            {"prompt_contract_version": 2, "scene_mechanics": self.MECHANICS[:1]},
            capabilities={"skills": False},
            catalog=_catalog(("tv", "TV body")),
        )

        text = messages[0]["content"]
        self.assertIn("cannot load skills on demand", text)
        self.assertIn("TV body", text)

    def test_a_partial_catalog_inlines_what_arrived_and_names_the_rest(self):
        messages = self._messages(
            {"prompt_contract_version": 2, "scene_mechanics": self.MECHANICS},
            capabilities={"skills": False},
            catalog=_catalog(("tv", "TV body")),
        )

        text = messages[0]["content"]
        self.assertIn("No instructions arrived for: easel", text)
        self.assertIn("TV body", text)

    def test_undelivered_mechanic_is_named(self):
        messages = self._messages(
            {"prompt_contract_version": 2, "scene_mechanics": [
                {"mechanic": "tv", "skill": "tv", "state": "available"},
                {"mechanic": "easel", "skill": "easel", "state": "missing"},
            ]},
            capabilities={"skills": True, "skill_mode": "on_demand"},
            catalog=_catalog(("tv", "TV body")),
        )

        text = messages[0]["content"]
        self.assertIn("Reported but not delivered: easel", text)

    def test_plain_strings_and_unknown_states_are_normalised(self):
        entries = PromptController._scene_mechanic_entries(
            {"scene_mechanics": ["tv", {"id": "easel", "state": "weird"}, "TV"]}
        )

        self.assertEqual([entry["mechanic"] for entry in entries], ["tv", "easel"])
        self.assertEqual(entries[1]["state"], "available")
        self.assertEqual(entries[1]["skill"], "easel")

    def test_payload_projection_keeps_the_contract_fields(self):
        from game_connections.handlers.actions.create_task import build_game_state_payload

        payload = build_game_state_payload({
            "prompt_contract_version": "2",
            "scene_mechanics": self.MECHANICS,
        }, "Crazy")

        self.assertEqual(payload["prompt_contract_version"], 2)
        self.assertEqual(payload["scene_mechanics"], self.MECHANICS)

    def test_payload_without_the_marker_stays_at_version_zero(self):
        from game_connections.handlers.actions.create_task import build_game_state_payload

        payload = build_game_state_payload({}, "Crazy")

        self.assertEqual(payload["prompt_contract_version"], 0)
        self.assertEqual(payload["scene_mechanics"], [])


if __name__ == "__main__":
    unittest.main()
