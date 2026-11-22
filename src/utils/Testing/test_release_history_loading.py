from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QWidget

from controllers.chat_controller import ChatController
from controllers.gui.api_settings.editor_mixin import EditorMixin
from controllers.gui.settings_controller import SettingsController
from handlers.asr_models.google_recognizer import GoogleRecognizer
from managers.unity_retry_store import UnityRetryStore
from ui.chat.presentation_coordinator import ChatPresentationCoordinator, ChatRenderCommand
from ui.windows.app_window_base import AppWindowBase
from core.events import Events


@pytest.mark.parametrize("prepend", [False, True])
@pytest.mark.parametrize("show_thinking", [False, True])
def test_history_reasoning_is_adjacent_to_its_answer(prepend, show_thinking):
    rows = []
    def insert(_context, *, role, content, insert_at_start=False, **_kwargs):
        if insert_at_start:
            rows.insert(0, role)
        else:
            rows.append(role)
    window = SimpleNamespace(
        _chat_presentation=SimpleNamespace(is_message_deleted=lambda **_kwargs: False),
        _chat_render_context=object(), _get_setting=lambda *_args: show_thinking,
    )
    with patch("ui.windows.app_window_base.message_renderer.insert_message", side_effect=insert):
        AppWindowBase._render_history_entry(window, {
            "role": "assistant", "content": "answer", "thinking": "thought", "message_id": "out:1",
        }, character_id="A", insert_at_start=prepend)
    assert rows == (["think", "assistant"] if show_thinking else ["assistant"])


def test_first_lazy_chat_mount_requests_history_without_prior_pending_load():
    window = SimpleNamespace(chat_window=object(), _pending_history_payload=None,
        _chat_history_load_pending=False, load_chat_history=Mock(), update_token_count=Mock())
    with patch("ui.windows.app_window_base.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
        assert AppWindowBase._on_chat_ui_ready(window)
    window.load_chat_history.assert_called_once()



@pytest.mark.parametrize("owners,expected", [(["Crazy", "Kind"], 1), (["Kind"], 0)])
def test_committed_multi_character_history_refreshes_selected_character(owners, expected):
    window = SimpleNamespace(_chat_presentation=Mock(),
        _shell_actions=SimpleNamespace(current_character_id=lambda: "Crazy"), load_chat_history=Mock())
    AppWindowBase._on_history_messages_committed(window,
        {"message_ids": ["in:turn", "out:turn"], "character_ids": owners})
    assert window.load_chat_history.call_count == expected



def test_retry_merge_preserves_history_order_across_month_and_uses_rendered_time_format():
    payload = {"messages": [
        {"message_id": "in:old", "role": "user", "time": "30.09.2026 10:00:00"},
        {"message_id": "out:new", "role": "assistant", "time": "01.10.2026 10:00:00"}]}
    result = AppWindowBase._merge_unity_retry_records(payload, [])
    assert [m["message_id"] for m in result["messages"]] == ["in:old", "out:new"]



def test_backend_attachment_retries_history_load_after_early_sandbox_mount():
    from controllers.gui.app_shell_controller import AppShellController
    signal = Mock()
    shell = AppShellController(SimpleNamespace(load_chat_history_signal=signal),
        SimpleNamespace(app=Mock()))
    with patch("controllers.gui.app_shell_controller.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
        shell.attach_backend(object())
    signal.emit.assert_called_once()
