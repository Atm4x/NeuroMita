from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from DSL.dsl_engine import DslInterpreter
from DSL.path_resolver import LocalPathResolver
from services.mita_stages import (
    DEFAULT_STAGE,
    STAGE_DEFINITIONS,
    STAGE_IDS,
    STAGE_PROMPT_SET,
    MitaStageService,
)


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "extra" / "Prompts"
STAGE_SET = PROMPTS / "Crazy" / STAGE_PROMPT_SET


class FakeCharacter:
    char_id = "Crazy"

    def __init__(self, prompt_set_name: str = STAGE_PROMPT_SET, variables=None):
        self.prompt_set_name = prompt_set_name
        self.variables = dict(variables or {})
        self.custom_params = []

    def get_variable(self, name, default=None):
        return self.variables.get(name, default)

    def set_variable(self, name, value):
        self.variables[name] = value


@pytest.fixture()
def service(monkeypatch):
    instance = MitaStageService()
    monkeypatch.setattr(instance, "_publish", lambda *args, **kwargs: None)
    return instance


@pytest.fixture()
def character():
    return FakeCharacter()


def structured(secret: bool = False):
    return SimpleNamespace(secret_exposed=secret)


def test_all_twelve_stage_prompt_files_exist():
    assert len(STAGE_DEFINITIONS) == 12
    assert len(set(STAGE_IDS)) == 12
    for stage in STAGE_DEFINITIONS:
        assert (STAGE_SET / stage.prompt_file).is_file(), stage.prompt_file
    config = json.loads((STAGE_SET / "config.json").read_text(encoding="utf-8"))
    proposals = [p for p in config["custom_params"] if p.get("name") == "bm_stage_proposal"]
    assert len(proposals) == 1
    assert proposals[0]["required"] is False


def test_initialization_is_deterministic_and_idempotent(service, character):
    assert service.ensure_initialized(character) is True
    assert character.variables["bm_stage_id"] == DEFAULT_STAGE
    assert character.variables["bm_stage_auto"] is True
    assert character.variables["bm_stage_qa_enabled"] is True
    assert character.variables["bm_stage_show_in_unity"] is True
    assert character.variables["bm_stage_min_turns"] == 3
    snapshot = dict(character.variables)
    assert service.ensure_initialized(character) is False
    assert character.variables == snapshot


def test_manual_switch_reaches_every_stage(service, character):
    for stage_id in STAGE_IDS:
        ok, label = service.manual_set(character, stage_id)
        assert ok, stage_id
        assert label
        assert character.variables["bm_stage_id"] == stage_id
        assert character.variables["bm_stage_auto"] is False


def test_manual_switch_is_refused_when_qa_is_disabled(service, character):
    service.ensure_initialized(character)
    character.variables["bm_stage_qa_enabled"] = False
    ok, message = service.manual_set(character, "war")
    assert ok is False
    assert "disabled" in message.lower()
    assert character.variables["bm_stage_id"] == DEFAULT_STAGE


def test_ordinary_transition_waits_for_dwell_time(service, character):
    character.variables["bm_stage_proposal"] = "entertainment|the player is fun"
    assert service.observe_response(character, structured()) is None
    assert character.variables["bm_stage_id"] == DEFAULT_STAGE
    assert "dwell" in character.variables["bm_stage_last_reason"].lower()

    character.variables["bm_stage_stage_turns"] = 3
    character.variables["bm_stage_proposal"] = "entertainment|the player is fun"
    payload = service.observe_response(character, structured())
    assert payload is not None
    assert character.variables["bm_stage_id"] == "entertainment"
    assert character.variables["bm_stage_auto"] is True


def test_check_to_game_requires_exposed_secret(service, character):
    character.variables.update({
        "bm_stage_id": "check", "bm_stage_stage_turns": 3, "bm_stage_min_turns": 0,
    })
    character.variables["bm_stage_proposal"] = "game|we stop pretending"
    assert service.observe_response(character, structured()) is None
    assert character.variables["bm_stage_id"] == "check"

    character.variables["secretExposed"] = True
    character.variables["bm_stage_proposal"] = "game|we stop pretending"
    assert service.observe_response(character, structured()) is not None
    assert character.variables["bm_stage_id"] == "game"


def test_check_to_entertainment2_when_secret_stays_hidden(service, character):
    character.variables.update({
        "bm_stage_id": "check", "bm_stage_min_turns": 0, "bm_stage_stage_turns": 1,
    })
    character.variables["bm_stage_proposal"] = "entertainment2|the player stayed"
    assert service.observe_response(character, structured()) is not None
    assert character.variables["bm_stage_id"] == "entertainment2"


def test_love_to_boredom_is_reproducible(service, character):
    character.variables.update({
        "bm_stage_id": "love", "bm_stage_min_turns": 0, "bm_stage_stage_turns": 1,
    })
    character.variables["bm_stage_proposal"] = "boredom|the old games stopped working"
    assert service.observe_response(character, structured()) is not None
    assert character.variables["bm_stage_id"] == "boredom"


def test_early_secret_exposure_can_jump_to_war(service, character):
    character.variables["bm_stage_id"] = "introduction"
    character.variables["secretExposed"] = True
    character.variables["bm_stage_proposal"] = "war|the truth is out"
    payload = service.observe_response(character, structured(secret=True))
    assert payload is not None
    assert character.variables["bm_stage_id"] == "war"
    assert character.variables["bm_stage_preview"] is False
    assert character.variables["bm_stage_secret_source"] == "mita_explicit"


def test_boredom_cannot_enter_post_reveal_stages_before_secret(service, character):
    character.variables.update({"bm_stage_id": "boredom", "bm_stage_min_turns": 0})
    character.variables["bm_stage_proposal"] = "submission|nothing else to do"
    assert service.observe_response(character, structured()) is None
    assert character.variables["bm_stage_id"] == "boredom"

    character.variables["secretExposed"] = True
    character.variables["bm_stage_proposal"] = "submission|nothing else to do"
    assert service.observe_response(character, structured()) is not None
    assert character.variables["bm_stage_id"] == "submission"


def test_proposal_is_a_request_and_invalid_target_is_ignored(service, character):
    character.variables.update({"bm_stage_min_turns": 0, "bm_stage_stage_turns": 1})
    character.variables["bm_stage_proposal"] = "rebellion|because"
    assert service.observe_response(character, structured()) is None
    assert character.variables["bm_stage_id"] == DEFAULT_STAGE
    assert "does not lead" in character.variables["bm_stage_last_reason"]
    assert character.variables["bm_stage_proposal"] == ""


def test_manual_preview_does_not_claim_secret_or_change_it(service, character):
    character.variables["secretExposed"] = False
    ok, _ = service.manual_set(character, "war")
    assert ok is True
    assert character.variables["bm_stage_preview"] is True
    assert character.variables["secretExposed"] is False


def test_allowed_prompt_is_gated_until_min_turns(service, character):
    service.prepare_prompt_context(character)
    assert character.variables["bm_stage_allowed_prompt"].startswith("none yet")
    character.variables["bm_stage_stage_turns"] = 3
    service.prepare_prompt_context(character)
    allowed = character.variables["bm_stage_allowed_prompt"]
    assert "entertainment" in allowed
    assert "displeasure" in allowed
    assert "check" not in allowed


def test_ui_payload_is_explicit_hide_for_legacy_and_option_off(service):
    legacy = FakeCharacter("Default")
    assert service.ui_payload(legacy) == {"type": "stage_ui", "stage_ui": {"visible": False}}

    experimental = FakeCharacter()
    service.ensure_initialized(experimental)
    assert service.ui_payload(experimental)["stage_ui"]["visible"] is True
    experimental.variables["bm_stage_show_in_unity"] = False
    assert service.ui_payload(experimental)["stage_ui"] == {"visible": False}


def test_stage_command_switches_and_reports_state(service, character):
    text = service.handle_command(character, "")
    assert "introduction" in text
    text = service.handle_command(character, "set check")
    assert "Проверка" in text
    assert character.variables["bm_stage_id"] == "check"
    assert character.variables["bm_stage_auto"] is False
    text = service.handle_command(character, "auto on")
    assert "auto" in text
    assert character.variables["bm_stage_auto"] is True
    text = service.handle_command(character, "show off")
    assert "hidden" in text
    assert character.variables["bm_stage_show_in_unity"] is False
    text = service.handle_command(character, "reset")
    assert "Знакомство" in text
    assert character.variables["bm_stage_id"] == DEFAULT_STAGE
    assert character.variables["bm_stage_auto"] is True
    assert "/stage set" in service.handle_command(character, "help")
    assert "introduction" in service.handle_command(character, "list")


def test_stage_ui_publication_is_deduplicated_and_forced(monkeypatch):
    from core.events import Events

    class Bus:
        def __init__(self):
            self.events = []

        def emit(self, name, data=None):
            self.events.append((name, data))

    bus = Bus()
    monkeypatch.setattr("services.mita_stages.get_event_bus", lambda: bus)
    instance = MitaStageService()
    char = FakeCharacter()
    instance.ensure_initialized(char)
    payload = instance.ui_payload(char)
    instance._publish(char, payload)
    instance._publish(char, payload)
    instance._publish(char, payload, force=True)
    assert [event[0] for event in bus.events] == [
        Events.Server.SEND_STAGE_UI,
        Events.Server.SEND_STAGE_UI,
    ]
    assert bus.events[0][1]["character_id"] == "Crazy"
    assert bus.events[0][1]["payload"]["stage_ui"]["visible"] is True


def test_stage_selector_loads_only_one_block_and_keeps_shared_contract():
    character = FakeCharacter()
    character.variables.update({
        "bm_stage_id": "war",
        "bm_stage_allowed_prompt": "rebellion (Мятеж)",
        "bm_stage_auto": True,
        "bm_stage_preview": False,
        "bm_stage_stage_turns": 3,
        "bm_stage_min_turns": 3,
        "secretExposed": True,
        "attitude": 60.0,
        "boredom": 20.0,
        "stress": 8.0,
        "Love": 1,
    })
    interpreter = DslInterpreter(
        character, LocalPathResolver(str(PROMPTS), str(STAGE_SET)),
    )
    blocks, _messages = interpreter.process_main_template("main_template.txt")
    infos = interpreter.get_context_infos()
    static_text = "\n".join(blocks)
    volatile_text = "\n".join(infos)
    assert "STAGE: war" in volatile_text
    assert "STAGE: introduction" not in volatile_text
    assert "Current Stage" in volatile_text
    assert "secret: the Player knows your secret" in volatile_text
    assert "Дополнительные принципы экспериментальных стадий" in static_text
    assert static_text.count("Дополнительные принципы экспериментальных стадий") == 1


@pytest.mark.parametrize("stage", STAGE_DEFINITIONS)
def test_every_stage_selector_branch_renders_its_own_block(stage):
    character = FakeCharacter()
    character.variables.update({
        "bm_stage_id": stage.id,
        "bm_stage_allowed_prompt": "none",
        "bm_stage_auto": True,
        "bm_stage_preview": False,
        "bm_stage_stage_turns": 3,
        "bm_stage_min_turns": 3,
        "secretExposed": stage.id in {"game", "cohabitation", "submission", "war", "rebellion"},
        "attitude": 60.0,
        "boredom": 20.0,
        "stress": 8.0,
        "Love": 1,
    })
    interpreter = DslInterpreter(
        character, LocalPathResolver(str(PROMPTS), str(STAGE_SET)),
    )
    interpreter.process_main_template("main_template.txt")
    volatile_text = "\n".join(interpreter.get_context_infos())
    assert f"# STAGE: {stage.id}" in volatile_text
    assert volatile_text.count("# STAGE:") == 1


def test_default_prompt_set_is_not_modified_by_stage_service():
    default_config = json.loads((PROMPTS / "Crazy" / "Default" / "config.json").read_text(encoding="utf-8"))
    assert "bm_stage_id" not in default_config
    default_template = (PROMPTS / "Crazy" / "Default" / "main_template.txt").read_text(encoding="utf-8")
    assert "Stages/behavior_contract.txt" not in default_template
