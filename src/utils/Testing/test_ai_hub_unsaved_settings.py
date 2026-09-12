from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.mvvm import immutable_payload
from ui.windows.ai_hub.settings_panel import SettingsPanel
from ui.windows.ai_hub.settings_presentation import (
    AIHubSettingsChanged,
    AIHubSettingsState,
    DiscardAIHubSettingsChanges,
    SelectAIHubSettingsComponent,
)


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class _ViewModelStub(QObject):
    state_changed = pyqtSignal(object)
    effect_emitted = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.state = AIHubSettingsState(
            components=(("tts:a", "A"), ("tts:b", "B")),
            selected_component_id="tts:a",
            schema=immutable_payload(
                [
                    {
                        "key": "device",
                        "label": "Device",
                        "type": "combobox",
                        "options": {
                            "values": ["cuda:0", "cuda:1"],
                            "default": "cuda:0",
                            "display_labels": {
                                "cuda:0": "cuda:0 (GPU A)",
                                "cuda:1": "cuda:1 (GPU B)",
                            },
                        },
                    }
                ]
            ),
            values=immutable_payload({"device": "cuda:0"}),
            components_revision=1,
            form_revision=1,
        )
        self.dispatched: list[object] = []

    def dispatch(self, intent) -> None:
        self.dispatched.append(intent)
        if isinstance(intent, AIHubSettingsChanged):
            self.state = replace(self.state, dirty=True)
            self.state_changed.emit(self.state)
        elif isinstance(intent, DiscardAIHubSettingsChanges):
            self.state = replace(self.state, dirty=False)
            self.state_changed.emit(self.state)
        elif isinstance(intent, SelectAIHubSettingsComponent):
            # Selection itself is enough for these navigation tests; production
            # VM asynchronously loads that component's schema afterwards.
            self.state = replace(
                self.state,
                selected_component_id=intent.component_id,
                dirty=False,
            )
            self.state_changed.emit(self.state)

    def close(self) -> None:
        pass


def _set_dirty_device(panel: SettingsPanel) -> None:
    combo = panel._form._widgets["device"]
    combo.setCurrentIndex(1)
    _app().processEvents()
    assert panel.has_unsaved_changes()
    # Raw model value must stay cuda:N even though the UI displays the GPU name.
    assert panel._form.values()["device"] == "cuda:1"


def test_unsaved_component_switch_cancel_restores_previous_selection(monkeypatch) -> None:
    _app()
    vm = _ViewModelStub()
    panel = SettingsPanel(vm)
    _set_dirty_device(panel)

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_a, **_kw: QMessageBox.StandardButton.Cancel,
    )
    panel._list.setCurrentRow(1)
    _app().processEvents()

    assert vm.state.selected_component_id == "tts:a"
    assert str(panel._list.currentItem().data(Qt.ItemDataRole.UserRole) or "") == "tts:a"
    assert not any(isinstance(item, SelectAIHubSettingsComponent) for item in vm.dispatched)


def test_unsaved_component_switch_discard_allows_navigation(monkeypatch) -> None:
    _app()
    vm = _ViewModelStub()
    panel = SettingsPanel(vm)
    _set_dirty_device(panel)

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_a, **_kw: QMessageBox.StandardButton.Discard,
    )
    panel._list.setCurrentRow(1)
    _app().processEvents()

    assert vm.state.selected_component_id == "tts:b"
    assert any(isinstance(item, SelectAIHubSettingsComponent) for item in vm.dispatched)
