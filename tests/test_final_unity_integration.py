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
