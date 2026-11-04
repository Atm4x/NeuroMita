import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from characters.cartridge import CartridgeCharacter
from characters.novel import TwoDMita
from controllers.history_controller import HistoryController
from domain.character_runtime_profile import DEFAULT_RUNTIME_PROFILE
from game_connections.handlers import build_action_registry
from game_connections.handlers.registry import RequestContext


def test_combined_registry_retains_desktop_timeline_and_game_handshake():
    registry = build_action_registry()
    for action in ("desktop_state", "timeline", "create_task", "get_task_status"):
        assert registry.get(action) is not None
    server = SimpleNamespace(
        PROTOCOL_VERSION=1,
        declare_client_role=MagicMock(return_value="desktop"),
        owns_player_input=MagicMock(return_value=False),
        send_json=AsyncMock(),
    )
    ctx = RequestContext(server, "overlay", object(), None)
    asyncio.run(registry.get("hello").handle({"client_role": "desktop"}, ctx))
    reply = server.send_json.call_args.args[1]
    assert reply["client_role"] == "desktop"
    assert reply["cartridge_protocol_version"] == reply["novel_protocol_version"] == 1
    assert reply["owns_player_input"] is False


@pytest.mark.parametrize("profile,background", [
    (DEFAULT_RUNTIME_PROFILE, True),
    (CartridgeCharacter.runtime_profile, False),
    (TwoDMita.runtime_profile, False),
])
def test_timeline_compression_respects_virtual_character_capabilities(profile, background):
    controller = object.__new__(HistoryController)
    controller._start_timeline_compression = MagicMock()
    controller._start_background_compression = MagicMock()
    controller._maybe_run_memory_maintenance = MagicMock()
    character = SimpleNamespace(char_id="integration_actor", runtime_profile=profile)
    context = object()
    registry = MagicMock()
    registry.get_optional.return_value = context
    event = SimpleNamespace(data={"character_id": character.char_id, "character_ref": character})
    with patch("controllers.history_controller.services", return_value=registry):
        controller._on_message_completed(event)
    if background:
        controller._start_timeline_compression.assert_called_once_with(character, context)
        controller._maybe_run_memory_maintenance.assert_called_once_with(character)
    else:
        controller._start_timeline_compression.assert_not_called()
        controller._maybe_run_memory_maintenance.assert_not_called()
    controller._start_background_compression.assert_not_called()


def test_desktop_kind_turn_does_not_change_game_target_or_timeline():
    from game_connections.handlers.actions import create_task as action
    from core.events import Events

    server = SimpleNamespace(_should_block_event=MagicMock(return_value=False))
    event_bus = MagicMock()
    ctx = RequestContext(server, "overlay", object(), event_bus, client_role="desktop")
    registry = MagicMock()
    registry.get.return_value = None
    with (
        patch.object(action, "use", return_value=registry),
        patch.object(action, "services") as services,
        patch.object(action, "collect_context_images", return_value=[]),
        patch.object(action, "_dispatch_task", new_callable=AsyncMock) as dispatch,
    ):
        asyncio.run(action.CreateTaskAction().handle({
            "type": "answer",
            "character": "Kind",
            "req_id": "turn-1",
            "data": {"message": "Привет"},
        }, ctx))

    services.assert_not_called()
    registry.set_unity_target_character_id.assert_not_called()
    assert [call.args[0] for call in event_bus.emit.call_args_list] == [
        Events.Server.ECHO_CHAT_MESSAGE_REQUESTED,
    ]
    dispatch.assert_awaited_once()
    turn = dispatch.await_args.kwargs
    assert turn["character_id"] == "Kind"
    assert turn["req_id"] == "turn-1"
    assert turn["player_message_source"] == "application"


def test_desktop_rejects_other_characters():
    server = SimpleNamespace(_send_aborted_update=AsyncMock())
    ctx = RequestContext(server, "overlay", object(), None, client_role="desktop")
    asyncio.run(build_action_registry().get("create_task").handle({
        "character": "Cappie", "req_id": "wrong-character",
    }, ctx))
    server._send_aborted_update.assert_awaited_once_with(
        "overlay", "answer", "Cappie", reason="Desktop supports only Kind dialogue", req_id="wrong-character",
    )


@pytest.mark.parametrize("character_id,active,state,expected", [
    ("Kind", True, {"activity": "idle"}, True),
    ("Kind", False, {"activity": "idle"}, False),
    ("Kind", True, {}, False),
    ("Crazy", True, {"activity": "idle"}, False),
])
def test_desktop_prompt_scope(character_id, active, state, expected):
    from controllers.prompt_controller import PromptController
    from services.contracts import DesktopWatchService, SettingsService
    settings = SimpleNamespace(get=lambda _key, _default=False: active)
    watch = SimpleNamespace(desktop_state=lambda: dict(state), is_watching=lambda: False)
    registry = SimpleNamespace(get_optional=lambda key: {
        SettingsService: settings, DesktopWatchService: watch,
    }.get(key))
    with patch("controllers.prompt_controller.services", return_value=registry):
        block = PromptController._desktop_context_for_character(character_id)
    assert bool(block) is expected
    if expected:
        assert "not the apartment" in block
        assert "Screen watching: off" in block


def test_desktop_prompt_takes_priority_over_connected_apartment():
    from controllers.prompt_controller import PromptController
    from core.request_policy import RequestPolicy
    from services.contracts import PromptBuildRequest, RuntimeCapabilities
    character = SimpleNamespace(char_id="Kind", get_variable=lambda _name, default=None: default)
    controller = PromptController()
    controller._build_system_messages = lambda *_a, **_k: ([], [], [])
    controller._build_system_state_message = lambda *_a, **_k: {"role": "system", "content": "[connected]"}
    controller._build_character_environment_message = lambda *_a, **_k: {"role": "system", "content": "Apartment environment"}
    controller._build_shared_minigame_context = MagicMock()
    state = {"world_state": "Kitchen", "runtime_rules": "Open the cupboard"}
    with (
        patch.object(controller, "_desktop_context_for_character", return_value="[Desktop mode] Current location is Windows desktop"),
        patch("controllers.prompt_controller.runtime_capabilities", return_value=RuntimeCapabilities(connected=True)),
    ):
        result = controller.build(PromptBuildRequest(
            character=character, event_type="chat", policy=RequestPolicy(use_history_in_prompt=False),
            user_input="Where are you?", game_state=state,
        ))
    contents = [str(m["content"]) for m in result.messages]
    assert any("[Desktop mode]" in content for content in contents)
    assert all("Kitchen" not in content and "Open the cupboard" not in content and "Apartment environment" not in content for content in contents)
    controller._build_shared_minigame_context.assert_not_called()
    assert state == {"world_state": "Kitchen", "runtime_rules": "Open the cupboard"}


@pytest.mark.parametrize("role,expected", [("desktop", True), ("game", False), ("", False)])
def test_desktop_voice_is_delivered_to_overlay_instead_of_python_player(role, expected):
    from controllers.audio_controller import AudioController
    from services.contracts import TaskService
    task = SimpleNamespace(data={"client_role": role})
    tasks = SimpleNamespace(get_task=lambda uid: task if uid == "voice-task" else None)
    registry = SimpleNamespace(get_optional=lambda key: tasks if key is TaskService else None)
    with patch("controllers.audio_controller.services", return_value=registry):
        assert AudioController._desktop_task("voice-task") is expected
        assert AudioController._desktop_task("missing-task") is False
