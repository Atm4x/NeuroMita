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
    from characters.novel import TwoDMita
    character = SimpleNamespace(char_id="TwoD", runtime_profile=TwoDMita.runtime_profile, history_manager=history,
        base_data_path=str(PROMPTS / "TwoD" / "Default"), main_template_path_relative="main_template.txt")
    character.variables, character.app_vars, character.custom_params = {}, {}, []
    character.get_variable = lambda key, default=None: character.variables.get(key, default)
    character.set_variable = lambda key, value: character.variables.__setitem__(key, value)
    character.update_app_vars = lambda values: character.app_vars.update(values)
    character.dsl_interpreter = DslInterpreter(character, LocalPathResolver(str(PROMPTS), character.base_data_path))
    return character


def build_prompt(request, *, connected=True):
    from dataclasses import fields
    from controllers.prompt_controller import PromptController
    from core.request_policy import RequestPolicy
    from services.contracts import AppVarsService, HistoryService, PreparedHistory, PromptBuildRequest, RuntimeCapabilities
    normalized = {field.name: getattr(request, field.name) for field in fields(PromptBuildRequest) if hasattr(request, field.name)}
    normalized.setdefault("event_type", "chat")
    if not isinstance(request.policy, RequestPolicy):
        normalized["policy"] = RequestPolicy.from_dict(vars(request.policy))
    history = MagicMock(spec=HistoryService)
    history.prepare_for_prompt.side_effect = lambda **kwargs: PreparedHistory(
        messages=request.character.history_manager.get_recent_messages(limit=kwargs["memory_limit"]),
        summary="", last_message_at=None)
    app_vars = SimpleNamespace(snapshot=lambda: {})
    controller = object.__new__(PromptController)
    controller._get_setting = lambda _key, default=None: default
    with patch("controllers.prompt_controller.use", side_effect=lambda service: app_vars if service is AppVarsService else history), \
         patch("controllers.prompt_controller.runtime_capabilities", return_value=RuntimeCapabilities(connected=connected)), \
         patch.object(controller, "_build_character_environment_message", return_value=None):
        return controller.build(PromptBuildRequest(**normalized))


def prompt_text(result):
    return "\n".join(m["content"] for m in result.messages if isinstance(m["content"], str))


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
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "user", "content": "Earlier"}, {"role": "assistant", "content": "Remembered"}]
        request = SimpleNamespace(character=prompt_character(history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Hello", sender="Player",
            game_state={"novel": dict(player_room="bedroom", mita_room="corridor", pose="sad", transform=dict(x=0.15, y=0, scale=1.2))})
        result = build_prompt(request)
        self.assertTrue(result.support_intents)
        self.assertIn('"player_room": "bedroom"', prompt_text(result))
        self.assertIn('"transform": {"x": 0.15, "y": 0, "scale": 1.2}', prompt_text(result))
        self.assertIn("novel.transform", prompt_text(result))
        self.assertIn("Remembered", str(result.messages))
        self.assertEqual(result.messages[-1]["content"], [{"type": "text", "text": "Hello"}])

    def test_prompt_uses_shared_history_window_and_history_can_be_disabled(self):
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "assistant", "content": str(i)} for i in range(65)]
        request = SimpleNamespace(character=prompt_character(history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Hello", sender="Player", game_state={})
        result = build_prompt(request)
        self.assertEqual(len(result.history_messages), 41)
        self.assertEqual(result.history_messages[0]["content"], "25")
        request.policy.use_history_in_prompt = False
        history.get_recent_messages.reset_mock()
        result = build_prompt(request)
        history.get_recent_messages.assert_not_called()
        self.assertEqual(len(result.history_messages), 1)

    def test_prompt_controller_routes_novel_persona_without_fabricating_history(self):
        from controllers.prompt_controller import PromptController
        history = MagicMock()
        history.get_recent_messages.return_value = [{"role": "assistant", "content": "Our real earlier reply"}]
        request = SimpleNamespace(character=prompt_character(history),
            policy=SimpleNamespace(use_history_in_prompt=True), user_input="Я вернулся", sender="Player",
            game_state={"novel": dict(player_room="hall", mita_room="hall", pose="happy")})
        result = build_prompt(request)
        self.assertIn((PROMPTS / "TwoD/Default/Main/main.txt").read_text(encoding="utf-8").strip(), prompt_text(result))
        for command in ("novel.pose", "novel.move", "novel.transform", "novel.tint", "novel.shake", "novel.effect"):
            self.assertIn(command, prompt_text(result))
        self.assertEqual(result.history_messages[0], {"role": "assistant", "content": "Our real earlier reply"})
        self.assertEqual(result.user_message["content"], [{"type": "text", "text": "Я вернулся"}])
        self.assertIn("[System State]", prompt_text(result))
        self.assertIn("[Current State]", prompt_text(result))
        self.assertNotIn("[Behavior State]", prompt_text(result))

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
            self.assertIn("User edited persona FIRST", prompt_text(build_prompt(request)))
            (target / "Main/main.txt").write_text("User edited persona SECOND", encoding="utf-8")
            result = prompt_text(build_prompt(request))
            self.assertIn("User edited persona SECOND", result)
            self.assertNotIn("User edited persona FIRST", result)

    def test_shared_builder_keeps_request_context_and_excludes_stale_3d_world(self):
        request = SimpleNamespace(character=prompt_character(MagicMock()),
            policy=SimpleNamespace(use_history_in_prompt=False), user_input="Hi", sender="Player",
            system_input="Live event", hidden_user_context="Current sender detail",
            extra_system_infos=["Current request detail"],
            game_state={"world_state": "STALE_3D", "novel": dict(player_room="hall", pose="ring", session="transport-only")})
        result = build_prompt(request)
        text = prompt_text(result)
        for value in ("Live event", "Current sender detail", "Current request detail", '"player_room": "hall"'):
            self.assertIn(value, text)
        self.assertNotIn("STALE_3D", text)
        self.assertNotIn("transport-only", text)
        self.assertNotIn("[Scene State]", str(result.history_messages))

    def test_runtime_profiles_preserve_standard_and_cartridge_defaults(self):
        from domain.character_runtime_profile import runtime_profile_for
        from characters.novel import TwoDMita
        from characters.cartridge import CartridgeCharacter
        default = runtime_profile_for(SimpleNamespace())
        self.assertTrue(default.rag_enabled and default.tools_enabled and default.background_memory_enabled)
        novel = runtime_profile_for(object.__new__(TwoDMita))
        self.assertFalse(novel.rag_enabled or novel.tools_enabled or novel.background_memory_enabled)
        self.assertTrue(novel.requires_structured_output)
        cartridge = runtime_profile_for(object.__new__(CartridgeCharacter))
        self.assertFalse(cartridge.rag_enabled or cartridge.core_memory_enabled or cartridge.tools_enabled or cartridge.background_memory_enabled)
        self.assertIsNone(cartridge.scene_context_key)

    def test_profile_controls_shared_model_rag_tools_and_structured_output(self):
        import threading
        from dataclasses import replace
        from controllers.model_controller import ModelController
        from services.contracts import ChatGenerationRequest
        from characters.novel import TwoDMita
        class Captured(BaseException):
            pass
        for rag in (False, True):
            with self.subTest(rag=rag):
                character = prompt_character(MagicMock())
                character.display_name = "2D Mita"
                character.runtime_profile = replace(TwoDMita.runtime_profile, rag_enabled=rag)
                controller = object.__new__(ModelController)
                controller.settings = SimpleNamespace(get=lambda key, default=None: True if key == "RAG_ENABLED" else default)
                controller.model = SimpleNamespace(cfg=SimpleNamespace(memory_limit=40))
                controller.preset_resolver = SimpleNamespace(resolve=lambda _: SimpleNamespace(capabilities={}, dialect_id="openai_chat"))
                controller._temporary_system_infos_lock = threading.RLock()
                controller._temporary_system_infos = {}
                controller._resolve_preset_id = lambda *_: 1
                controller._resolve_preset_bool = lambda *_, **kwargs: kwargs.get("default", False)
                controller._capture_generation_input = lambda **_: None
                controller.process_rag = MagicMock(return_value="Relevant memory")
                captured = []
                def stop_at_prompt(request):
                    captured.append(request)
                    raise Captured()
                builder = SimpleNamespace(build=stop_at_prompt)
                with patch("controllers.model_controller.use", return_value=builder), self.assertRaises(Captured):
                    controller._generate_chat_serialized(ChatGenerationRequest(
                        character_id="TwoD", event_type="chat", user_input="Hello",
                        game_state={"novel": {"player_room": "hall"}}), character)
                self.assertEqual(controller.process_rag.called, rag)
                self.assertEqual(captured[0].rag_context, "Relevant memory" if rag else "")
                self.assertTrue(captured[0].capabilities["structured_output"])
                self.assertFalse(captured[0].capabilities["structured_response_profile"].tools_enabled)

    def test_background_memory_uses_profile_instead_of_character_kind(self):
        from dataclasses import replace
        from controllers.history_controller import HistoryController
        from characters.novel import TwoDMita
        controller = object.__new__(HistoryController)
        controller._start_background_compression = MagicMock()
        controller._maybe_run_memory_maintenance = MagicMock()
        character = SimpleNamespace(char_id="TwoD", runtime_profile=TwoDMita.runtime_profile)
        event = SimpleNamespace(data={"character_id": "TwoD", "character_ref": character})
        controller._on_message_completed(event)
        controller._start_background_compression.assert_not_called()
        character.runtime_profile = replace(character.runtime_profile, background_memory_enabled=True)
        controller._on_message_completed(event)
        controller._start_background_compression.assert_called_once_with(character)
        controller._maybe_run_memory_maintenance.assert_called_once_with(character)

    def test_disconnected_prompt_does_not_reuse_saved_scene_state(self):
        request = SimpleNamespace(character=prompt_character(MagicMock()),
            policy=SimpleNamespace(use_history_in_prompt=False), user_input="Hi", sender="Player",
            game_state={"novel": {"player_room": "bedroom"}})
        text = prompt_text(build_prompt(request, connected=False))
        self.assertNotIn("[Scene State]", text)
        self.assertIn("[System State]", text)

    def test_shared_history_save_retains_novel_limit_without_truncating_other_characters(self):
        from characters.character import Character
        from characters.novel import TwoDMita
        messages = [{"role": "assistant", "content": str(i)} for i in range(70)]
        for profile, expected in ((TwoDMita.runtime_profile, 40), (None, 70)):
            character = SimpleNamespace(runtime_profile=profile, variables={},
                flush_variables=MagicMock(), history_manager=MagicMock())
            Character.save_character_state_to_history(character, messages)
            saved = character.history_manager.save_history.call_args.args[0]["messages"]
            self.assertEqual(saved, messages[-expected:])

    def test_character_is_registered_separately(self):
        from managers.character_manager import _CHARACTER_DEFINITIONS
        definition = next(d for d in _CHARACTER_DEFINITIONS if d.character_id == "TwoD")
        self.assertEqual(definition.storage_name, "2D Mita")
        self.assertEqual(definition.factory.runtime_profile.scene_context_key, "novel")


if __name__ == "__main__":
    unittest.main()
