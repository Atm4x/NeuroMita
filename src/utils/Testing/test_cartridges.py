from __future__ import annotations

import copy
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.cartridge_catalog import parse_catalog, validate_session


def catalog():
    return {"version": 1, "cartridges": [{
        "id": "space", "legacyCharacter": "Cart_portal", "title": "Space",
        "itemNames": ["CartridgeSpace"], "record": "A record", "prompt": "A space personality",
        "historyMessages": 4, "contextCharacters": 8000,
        "effects": [{"id": "speed", "title": "Speed", "type": "player.speed",
                     "target": "player", "magnitude": 1.2, "slotCost": 1}],
    }]}


class CartridgeCatalogTests(unittest.TestCase):
    def test_legacy_and_dynamic_identities(self):
        payload = catalog()
        other = copy.deepcopy(payload["cartridges"][0])
        other.update(id="dance", legacyCharacter=None, itemNames=["Dance"], effects=[])
        payload["cartridges"].append(other)
        self.assertEqual([d.character_id for d in parse_catalog(payload)], ["Cart_portal", "Cartridge_dance"])

    def test_rejects_identity_collisions_and_unknown_effects(self):
        for edit in (
            lambda p: p["cartridges"].append(copy.deepcopy(p["cartridges"][0])),
            lambda p: p.update(version=2),
            lambda p: p["cartridges"][0].update(id="../Crazy"),
            lambda p: p["cartridges"][0].update(legacyCharacter="Crazy"),
            lambda p: p["cartridges"][0]["effects"][0].update(type="run.code"),
            lambda p: p["cartridges"][0]["effects"][0].update(magnitude=float("nan")),
            lambda p: p["cartridges"][0]["effects"][0].update(slotCost=0),
            lambda p: p["cartridges"][0].update(historyMessages=True),
        ):
            payload = catalog()
            edit(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_catalog(payload)

    def test_session_requires_permission_inserted_identity_and_version(self):
        valid = {"version": 1, "catalog": catalog(), "id": "space", "session": "session-a", "ai_enabled": True}
        self.assertEqual(validate_session(valid, "Cart_portal")[0].id, "space")
        for key, value in (("version", 3), ("ai_enabled", False), ("session", ""), ("id", "missing")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_session({**valid, key: value}, "Cart_portal")
        with self.assertRaises(ValueError):
            validate_session(valid, "Cart_divan")


class CartridgePromptTests(unittest.TestCase):
    def request(self):
        from core.request_policy import RequestPolicy
        from services.contracts import PromptBuildRequest
        definition = parse_catalog(catalog())[0]
        history = MagicMock()
        history.get_recent_messages.return_value = [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
        ]
        character = SimpleNamespace(cartridge_definition=definition, history_manager=history)
        return PromptBuildRequest(character=character, event_type="chat", policy=RequestPolicy(), user_input="Hello")

    def test_uses_short_history_without_mita_memory_or_intents(self):
        from services.cartridge_prompt import build_cartridge_prompt
        request = self.request()
        result = build_cartridge_prompt(request)
        self.assertFalse(result.support_intents)
        request.character.history_manager.get_recent_messages.assert_called_once_with(limit=4)
        self.assertIn("Earlier answer", str(result.messages))
        self.assertEqual(result.user_message["content"], "Hello")
        self.assertEqual(result.messages[0]["content"].splitlines()[0], "A space personality")

    def test_context_budget_discards_large_old_messages(self):
        from services.cartridge_prompt import build_cartridge_prompt
        request = self.request()
        request.character.history_manager.get_recent_messages.return_value = [
            {"role": "user", "content": "x" * 15000},
            {"role": "assistant", "content": "Recent reply"},
        ]
        result = build_cartridge_prompt(request)
        self.assertEqual(len(result.history_messages), 2)
        self.assertLess(sum(len(str(m["content"])) for m in result.messages), 8000)

    def test_no_history_policy_never_reads_history(self):
        from services.cartridge_prompt import build_cartridge_prompt
        request = self.request()
        request.policy.use_history_in_prompt = False
        build_cartridge_prompt(request)
        request.character.history_manager.get_recent_messages.assert_not_called()

    def test_total_character_budget_includes_user_and_group_context(self):
        from dataclasses import replace
        from services.cartridge_prompt import build_cartridge_prompt
        request = self.request()
        request.character.cartridge_definition = replace(request.character.cartridge_definition, context_characters=1200)
        request.user_input = "u" * 2000
        request.system_input = "s" * 2000
        request.participants = ["participant" * 50] * 16
        result = build_cartridge_prompt(request)
        self.assertLessEqual(sum(len(m["content"]) for m in result.messages), 1200)

    def test_registration_preserves_main_selection_and_updates_definition(self):
        from managers.character_manager import CharacterManager
        manager = object.__new__(CharacterManager)
        manager._lock = threading.RLock()
        manager._definitions = {}
        manager.characters = {}
        manager.resources = MagicMock()
        manager.current_character = sentinel = object()
        manager.register_cartridges(parse_catalog(catalog()))
        self.assertIs(manager.current_character, sentinel)
        self.assertEqual(manager.get_display_name("Cart_portal"), "Space")
        factory = manager._definitions["Cart_portal"].factory
        with patch("characters.cartridge.Character.__init__") as init:
            factory()
        self.assertEqual(init.call_args.kwargs["storage_name"], "Cart_portal")
        self.assertTrue(init.call_args.kwargs["is_cartridge"])

    def test_saved_history_is_bounded_per_cartridge(self):
        from characters.cartridge import CartridgeCharacter
        with patch("characters.cartridge.Character.__init__"):
            character = CartridgeCharacter(parse_catalog(catalog())[0])
        with patch("characters.cartridge.Character.save_character_state_to_history") as save:
            character.save_character_state_to_history([{"content": str(i)} for i in range(20)])
        self.assertEqual([m["content"] for m in save.call_args.args[0]], ["16", "17", "18", "19"])

    def test_structured_reply_retains_text_and_address_but_cannot_apply_effects(self):
        from characters.cartridge import CartridgeCharacter
        from schemas.structured_response import StructuredResponse
        with patch("characters.cartridge.Character.__init__"):
            character = CartridgeCharacter(parse_catalog(catalog())[0])
        reply = StructuredResponse.model_validate({"stress_change": -5, "memory_add": ["forbidden"],
            "segments": [{"text": "Hello", "target": "Crazy", "commands": ["light:off"],
                          "intents": [{"type": "dialogue.continue", "payload": {}}]}]})
        result = character.process_structured_response(reply)
        self.assertEqual(result.segments[0].text, "Hello")
        self.assertEqual(result.segments[0].target, "Crazy")
        self.assertEqual(result.segments[0].intents, [])
        self.assertEqual(result.segments[0].commands, [])
        self.assertIsNone(result.memory_add)
        self.assertEqual(result.stress_change, 0)


if __name__ == "__main__":
    unittest.main()
