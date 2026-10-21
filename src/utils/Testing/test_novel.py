import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from domain.novel import validate_novel, sanitize_response, sanitize_transform, sanitize_tint, sanitize_visual
from schemas.structured_response import StructuredResponse


PROMPTS = Path(__file__).resolve().parents[3] / "extra" / "Prompts"


def prompt_character(history):
    from DSL.dsl_engine import DslInterpreter
    from DSL.path_resolver import LocalPathResolver
    character = SimpleNamespace(char_id="TwoD", is_novel=True, history_manager=history,
        base_data_path=str(PROMPTS / "TwoD" / "Default"), main_template_path_relative="main_template.txt")
    character.dsl_interpreter = DslInterpreter(character, LocalPathResolver(str(PROMPTS), character.base_data_path))
    return character


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
        request = SimpleNamespace(character=prompt_character(history),
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
        request = SimpleNamespace(character=prompt_character(history),
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
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "assistant", "content": "Our real earlier reply"}]
        request = SimpleNamespace(character=prompt_character(history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Я вернулся", sender="Player",
            game_state={"novel": dict(player_room="hall", mita_room="hall", pose="happy")})
        result = object.__new__(PromptController).build(request)
        self.assertIn((PROMPTS / "TwoD/Default/Main/main.txt").read_text(encoding="utf-8").strip(), result.messages[0]["content"])
        for command in ("novel.pose", "novel.move", "novel.transform", "novel.tint", "novel.shake", "novel.effect"):
            self.assertIn(command, result.messages[0]["content"])
        self.assertEqual(result.history_messages, [
            {"role": "assistant", "content": "Our real earlier reply"},
            {"role": "user", "content": "Я вернулся", "sender": "Player"}])
        self.assertEqual([message["role"] for message in result.messages], ["system", "assistant", "user"])

    def test_visual_commands_are_bounded_and_malformed_values_are_rejected(self):
        self.assertEqual(sanitize_tint(dict(color="#aa22ff", opacity=0, duration=99)),
                         dict(color="#AA22FF", opacity=0.15, duration=3))
        self.assertEqual(sanitize_visual("novel.shake", dict(strength=9, duration=9)), dict(strength=0.03, duration=2))
        self.assertEqual(sanitize_visual("novel.effect", dict(effect="pulse")), dict(effect="pulse", strength=0.5, duration=0.5))
        for bad in ("red", "#123", [], None):
            self.assertIsNone(sanitize_tint(dict(color=bad)))
        for bad in (True, "1", None, [], float("nan"), float("inf")):
            self.assertIsNone(sanitize_tint(dict(color="#FFFFFF", opacity=bad)))
            self.assertIsNone(sanitize_visual("novel.shake", dict(strength=bad)))
        self.assertIsNone(sanitize_visual("novel.effect", dict(effect="shake")))
        self.assertIsNone(sanitize_visual("novel.effect", dict(effect=[])))
        raw = StructuredResponse.model_validate({"segments": [{"text": "Hi", "intents": [
            {"type": "novel.tint", "payload": {"color": "#ffaacc", "junk": 3}},
            {"type": "novel.shake", "payload": {}},
            {"type": "novel.effect", "payload": {"effect": "tilt"}},
            {"type": "novel.effect", "payload": {"effect": "destroy"}}]}]})
        intents = sanitize_response(raw).segments[0].intents
        self.assertEqual([i.type for i in intents], ["novel.tint", "novel.shake", "novel.effect"])
        self.assertEqual(intents[0].payload, dict(color="#FFAACC"))
        valid = dict(version=1, session="a", player_room="hall", mita_room="hall", pose="happy",
                     appearance=dict(color="#FFFFFF", opacity=1))
        self.assertEqual(validate_novel(valid), valid)

    def test_normal_prompt_set_is_discoverable_selected_and_reloaded_from_disk(self):
        import shutil
        import tempfile
        from characters.novel import TwoDMita
        from managers.prompt_catalogue_manager import list_prompt_sets
        from services.novel_prompt import build_novel_prompt
        self.assertIn("Default", list_prompt_sets(str(PROMPTS), "TwoD"))
        with tempfile.TemporaryDirectory() as directory:
            prompt_root = Path(directory)
            target = prompt_root / "TwoD/Custom"
            shutil.copytree(PROMPTS / "TwoD/Default", target)
            settings = MagicMock()
            settings.get.return_value = "Custom"
            instance = object.__new__(TwoDMita)
            instance.char_id, instance.prompts_root = "TwoD", str(prompt_root)
            with patch("characters.character.use", return_value=settings):
                self.assertEqual(instance._resolve_prompt_set_name(), "Custom")
            character = prompt_character(MagicMock())
            from DSL.dsl_engine import DslInterpreter
            from DSL.path_resolver import LocalPathResolver
            character.base_data_path = str(target)
            character.dsl_interpreter = DslInterpreter(character, LocalPathResolver(str(prompt_root), str(target)))
            request = SimpleNamespace(character=character, policy=SimpleNamespace(use_history_in_prompt=False),
                user_input="Hi", sender="Player", game_state={})
            (target / "Main/main.txt").write_text("User edited persona FIRST", encoding="utf-8")
            self.assertIn("User edited persona FIRST", build_novel_prompt(request).messages[0]["content"])
            (target / "Main/main.txt").write_text("User edited persona SECOND", encoding="utf-8")
            result = build_novel_prompt(request).messages[0]["content"]
            self.assertIn("User edited persona SECOND", result)
            self.assertNotIn("User edited persona FIRST", result)

    def test_character_is_registered_separately(self):
        from managers.character_manager import _CHARACTER_DEFINITIONS
        definition = next(d for d in _CHARACTER_DEFINITIONS if d.character_id == "TwoD")
        self.assertEqual(definition.storage_name, "2D Mita")
        self.assertTrue(definition.factory.is_novel)


if __name__ == "__main__":
    unittest.main()
