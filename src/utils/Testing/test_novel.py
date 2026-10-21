import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from domain.novel import validate_novel, sanitize_response, sanitize_transform
from schemas.structured_response import StructuredResponse


class NovelTests(unittest.TestCase):
    def test_session_requires_known_rooms_pose_and_protocol(self):
        valid = dict(version=1, session="a", player_room="hall", mita_room="corridor", pose="happy")
        self.assertEqual(validate_novel(valid), valid)
        for key, value in (("version", True), ("version", 2), ("session", ""), ("player_room", "jail"), ("pose", "run"), ("pose", []), ("player_room", {})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_novel({**valid, key: value})

    def test_only_novel_presentation_is_retained(self):
        raw = StructuredResponse.model_validate({"segments": [{"text": "Hi", "emotions": ["happy", "bad"],
            "commands": ["kill"], "animations": ["dance"], "intents": [
                {"type": "novel.pose", "payload": {"pose": "ring", "junk": "x"}},
                {"type": "novel.move", "payload": {"room": "kitchen"}},
                {"type": "novel.move", "payload": {"room": "jail"}},
                {"type": "inventory.collect", "payload": {"object": "key"}}]}]})
        segment = sanitize_response(raw).segments[0]
        self.assertEqual(segment.emotions, ["happy"])
        self.assertEqual(segment.commands, [])
        self.assertEqual(segment.animations, [])
        self.assertEqual([i.type for i in segment.intents], ["novel.pose", "novel.move"])
        self.assertEqual(segment.intents[0].payload, {"pose": "ring"})

    def test_malformed_model_intent_values_are_dropped(self):
        raw = StructuredResponse.model_validate({"segments": [{"text": "Hi", "intents": [
            {"type": "novel.pose", "payload": {"pose": []}},
            {"type": "novel.move", "payload": {"room": {}}}]}]})
        self.assertEqual(sanitize_response(raw).segments[0].intents, [])

    def test_transform_is_bounded_partial_and_rejects_invalid_numbers(self):
        self.assertEqual(sanitize_transform(dict(x=9, y=-9, scale=8, duration=9, junk=1)),
                         dict(x=0.35, y=-0.2, scale=1.5, duration=3.0))
        self.assertEqual(sanitize_transform(dict(scale=0.8, duration=0)), dict(scale=0.8, duration=0.0))
        self.assertEqual(sanitize_transform(dict(x=-9, y=9, scale=-1, duration=-1)),
                         dict(x=-0.35, y=0.2, scale=0.6, duration=0.0))
        for bad in (True, "1", None, [], {}, float("nan"), float("inf"), -(10 ** 400)):
            with self.subTest(value=repr(bad)):
                self.assertIsNone(sanitize_transform(dict(x=0.2, scale=bad)))
        for payload in ({}, dict(duration=1), [], None):
            self.assertIsNone(sanitize_transform(payload))

    def test_transform_intent_and_context_reach_model_without_unknown_fields(self):
        raw = StructuredResponse.model_validate({"segments": [{"text": "Closer", "intents": [
            {"type": "novel.transform", "payload": {"x": 0.15, "scale": 1.2, "duration": 0.6, "junk": "x"}},
            {"type": "novel.transform", "payload": {"x": 0, "y": "bad"}}]}]})
        intents = sanitize_response(raw).segments[0].intents
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].payload, dict(x=0.15, scale=1.2, duration=0.6))
        valid = dict(version=1, session="a", player_room="hall", mita_room="corridor", pose="happy")
        self.assertEqual(validate_novel({**valid, "transform": dict(x=0.1, y=0, scale=1.2)})["transform"],
                         dict(x=0.1, y=0, scale=1.2))
        for bad in (dict(x=0), dict(x=0, y=0, scale=True), None):
            with self.assertRaises(ValueError):
                validate_novel({**valid, "transform": bad})

    def test_prompt_preserves_recent_history_and_exact_house_state(self):
        from services.novel_prompt import build_novel_prompt
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "user", "content": "Earlier"}, {"role": "assistant", "content": "Remembered"}]
        request = SimpleNamespace(character=SimpleNamespace(history_manager=history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Hello", sender="Player",
            game_state={"novel": dict(player_room="bedroom", mita_room="corridor", pose="sad", transform=dict(x=0.15, y=0, scale=1.2))})
        result = build_novel_prompt(request)
        self.assertTrue(result.support_intents)
        self.assertIn('"player_room": "bedroom"', result.messages[0]["content"])
        self.assertIn('"transform": {"x": 0.15, "y": 0, "scale": 1.2}', result.messages[0]["content"])
        self.assertIn("novel.transform", result.messages[0]["content"])
        self.assertIn("Remembered", str(result.messages))
        self.assertEqual(result.messages[-1]["content"], "Hello")

    def test_prompt_budget_is_bounded_and_history_can_be_disabled(self):
        from services.novel_prompt import build_novel_prompt
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "assistant", "content": "x" * 20000}]
        request = SimpleNamespace(character=SimpleNamespace(history_manager=history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="y" * 5000, sender="Player", game_state={})
        result = build_novel_prompt(request)
        self.assertEqual(len(result.user_message["content"]), 2000)
        self.assertLess(sum(len(m["content"]) for m in result.messages), 20000)
        request.policy.use_history_in_prompt = False
        history.get_recent_messages.reset_mock()
        build_novel_prompt(request)
        history.get_recent_messages.assert_not_called()

    def test_prompt_controller_routes_novel_persona_without_fabricating_history(self):
        from controllers.prompt_controller import PromptController
        from characters.novel_personality import NOVEL_CHARACTER_PROMPT
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "assistant", "content": "Our real earlier reply"}]
        request = SimpleNamespace(character=SimpleNamespace(is_novel=True, history_manager=history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Я вернулся", sender="Player",
            game_state={"novel": dict(player_room="hall", mita_room="hall", pose="happy")})
        result = object.__new__(PromptController).build(request)
        self.assertTrue(result.messages[0]["content"].startswith(NOVEL_CHARACTER_PROMPT))
        for command in ("novel.pose", "novel.move", "novel.transform"):
            self.assertIn(command, result.messages[0]["content"])
        self.assertEqual(result.history_messages, [
            {"role": "assistant", "content": "Our real earlier reply"},
            {"role": "user", "content": "Я вернулся", "sender": "Player"}])
        self.assertEqual([message["role"] for message in result.messages], ["system", "assistant", "user"])

    def test_character_is_registered_separately(self):
        from managers.character_manager import _CHARACTER_DEFINITIONS
        definition = next(d for d in _CHARACTER_DEFINITIONS if d.character_id == "TwoD")
        self.assertEqual(definition.storage_name, "2D Mita")
        self.assertTrue(definition.factory.is_novel)


if __name__ == "__main__":
    unittest.main()
