from types import SimpleNamespace
import asyncio

import pytest

from game_connections.handlers.actions import desktop_state
from services.contracts import DesktopWatchService, SettingsService, SpeechService


@pytest.mark.parametrize("enabled,ready,mode,game,permitted,expected", [
    (False, False, "vad", False, True, "disabled"),
    (True, False, "vad", False, True, "starting"),
    (True, True, "radio", False, True, "manual"),
    (True, True, "vad", True, True, "game"),
    (True, True, "vad", False, False, "paused"),
    (True, True, "vad", False, True, "ready"),
])
def test_desktop_ack_reports_microphone_state(monkeypatch, enabled, ready, mode, game, permitted, expected):
    capture = SimpleNamespace(enabled=enabled, ready=ready, mode=mode, permitted=permitted)
    settings = SimpleNamespace(get=lambda key, default=None: enabled if key == "MIC_ACTIVE" else True)
    speech = SimpleNamespace(capture_state=lambda: capture)
    providers = {SettingsService: settings, SpeechService: speech, DesktopWatchService: None}
    monkeypatch.setattr(desktop_state, "services", lambda: SimpleNamespace(get_optional=providers.get))
    messages = []

    async def send(writer, message):
        messages.append(message)

    server = SimpleNamespace(set_desktop_voice_request=lambda *args: None,
                             set_desktop_watch_request=lambda *args: False,
                             primary_client_id=lambda: "game" if game else "", send_json=send)
    ctx = SimpleNamespace(server=server, client_id="desktop", writer=object())
    asyncio.run(desktop_state.DesktopStateAction().handle({"voice_input": True}, ctx))
    assert messages[0]["microphone"]["status"] == expected
    if enabled:
        assert messages[0]["microphone"]["mode"] == mode


def test_game_link_keeps_desktop_connection_separate():
    from services.game_link_service import ServerGameLinkService
    link = ServerGameLinkService()
    link.attach_desktop_probe(lambda: True)
    assert link.is_desktop_connected()
    assert not link.is_connected()
    assert not link.desktop_voice_target()
    link.attach_desktop_probe(lambda: False)
    assert not link.is_desktop_connected()


def test_sandbox_link_row_updates_connection_label():
    from PyQt6.QtWidgets import QApplication
    from ui.pages.sandbox_page import _GameLinkStatusRow
    app = QApplication.instance() or QApplication([])
    row = _GameLinkStatusRow("Связь", lambda *_: None, lambda: None, "Настройки")
    for connected, label in [(True, "Подключён десктоп"), (True, "Игра + десктоп"), (False, "Нет связи")]:
        row.setText(label)
        row.setChecked(connected)
        assert row._chip.text() == label
        assert row._chip.toolTip() == label
    row.close()
