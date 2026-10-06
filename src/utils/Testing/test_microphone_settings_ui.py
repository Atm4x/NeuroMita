import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
import pytest

from domain.audio_input import ASRInputDevice, MicrophoneSelection
from domain.audio_input import AudioInputCatalog, EndpointIdentityStatus
from controllers.gui.microphone_settings_controller import MicrophoneSettingsController
from ui.settings.microphone_settings.ui import build_microphone_settings_ui
from services.microphone_monitor import MonitorState

_APP = None


@pytest.fixture
def panel():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    root = QWidget()
    root.settings = {"NM_MICROPHONE_ID": 24, "NM_MICROPHONE_NAME": "Desk microphone"}
    build_microphone_settings_ui(root, QVBoxLayout(root))
    controller = MicrophoneSettingsController.__new__(MicrophoneSettingsController)
    controller.view = root
    controller._closed = False
    controller._ui = lambda fn: fn()
    controller._save_setting = Mock()
    controller.event_bus = Mock()
    controller._speech_service_or_retry = lambda *args: (
        SimpleNamespace(microphone_list_async=lambda cb: callbacks.append(cb)),
        False,
    )
    callbacks = []
    yield root, controller, callbacks
    root.mic_monitor_controller.monitor.close()
    root.close()
    root.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _APP.processEvents()


def test_refresh_uses_device_objects_and_full_names_without_changing_runtime(panel):
    root, controller, callbacks = panel
    long_name = "A very long USB microphone name with (parentheses) and more than thirty characters"
    controller.refresh_microphones()
    callbacks.pop()(
        [
            ASRInputDevice(12, long_name, "WASAPI"),
            ASRInputDevice(38, "Desk microphone", "WASAPI"),
        ]
    )
    assert root.mic_combobox.itemText(0) == long_name
    assert root.mic_combobox.currentData().index == 38
    controller.event_bus.emit.assert_not_called()
    controller._save_setting.assert_not_called()
    controller._on_mic_changed(0)
    assert controller.event_bus.emit.call_args.args[1] == MicrophoneSelection(
        index=12, name=long_name
    )


def test_pause_while_mita_speaks_defaults_to_off(panel):
    root, _, _ = panel
    assert not root.mic_mute_while_speaking_checkbox.isChecked()


def test_complete_display_name_is_used_but_selection_keeps_raw_name_and_id(panel):
    root, controller, callbacks = panel
    full_name = "Microphone (FIFINE K670 Microphone)"
    raw_name = full_name[:31]
    device = ASRInputDevice(1, raw_name, "MME", display_name=full_name)
    root.settings.update(NM_MICROPHONE_ID=1, NM_MICROPHONE_NAME=raw_name)
    controller.refresh_microphones()
    callbacks.pop()([device])
    assert root.mic_combobox.itemText(0) == full_name
    assert root.mic_combobox.currentText() == full_name
    assert full_name in root.mic_combobox.itemData(0, Qt.ItemDataRole.ToolTipRole)
    controller._on_mic_changed(0)
    assert full_name in root.mic_combobox.toolTip()
    assert controller.event_bus.emit.call_args.args[1] == MicrophoneSelection(
        index=1, name=raw_name
    )


def test_legacy_selection_gets_endpoint_id_migration_without_runtime_change(panel):
    root, controller, callbacks = panel
    controller.refresh_microphones()
    callbacks.pop()([ASRInputDevice(38, "Desk microphone", "WASAPI", uid="endpoint-A")])
    controller._save_setting.assert_not_called()
    assert root.mic_combobox.currentData().uid == "endpoint-A"
    controller.event_bus.emit.assert_not_called()


def test_saved_endpoint_survives_name_and_index_change_in_ui(panel):
    root, controller, callbacks = panel
    root.settings["NM_MICROPHONE_UID"] = "endpoint-A"
    controller.refresh_microphones()
    callbacks.pop()(
        [
            ASRInputDevice(24, "Desk microphone", "WASAPI", uid="endpoint-B"),
            ASRInputDevice(39, "Renamed microphone", "WASAPI", uid="endpoint-A"),
        ]
    )
    assert root.mic_combobox.currentData().index == 39
    assert root.mic_combobox.currentText() == "Renamed microphone"
    controller._on_mic_changed(1)
    assert controller.event_bus.emit.call_args.args[1] == MicrophoneSelection(
        uid="endpoint-A", index=39, name="Renamed microphone"
    )


def test_missing_endpoint_is_not_replaced_by_matching_legacy_name(panel):
    root, controller, callbacks = panel
    root.settings["NM_MICROPHONE_UID"] = "missing-endpoint"
    controller.refresh_microphones()
    callbacks.pop()(
        [ASRInputDevice(24, "Desk microphone", "WASAPI", uid="other-endpoint")]
    )
    assert root.mic_combobox.currentData() is None
    controller._save_setting.assert_not_called()


def test_existing_endpoint_binding_is_not_downgraded_by_legacy_catalog(panel):
    root, controller, callbacks = panel
    root.settings["NM_MICROPHONE_UID"] = "endpoint-A"
    root.mic_combobox.addItem(
        "Desk microphone", ASRInputDevice(24, "Desk microphone", "WASAPI")
    )
    controller.refresh_microphones()
    callbacks.pop()([ASRInputDevice(24, "Desk microphone", "WASAPI")])
    assert root.mic_combobox.currentData() is None
    controller._save_setting.assert_not_called()


def test_failed_identity_query_is_shown_as_unverified_binding_not_missing_mic(panel):
    root, controller, callbacks = panel
    root.settings["NM_MICROPHONE_UID"] = "endpoint-A"
    controller.refresh_microphones()
    device = ASRInputDevice(24, "Desk microphone", "WASAPI")
    callbacks.pop()(
        AudioInputCatalog((device,), identity_status=EndpointIdentityStatus.UNAVAILABLE)
    )
    assert "Не удалось проверить" in root.mic_combobox.currentText()
    assert root.mic_combobox.currentData() is None
    assert root.settings["NM_MICROPHONE_UID"] == "endpoint-A"
    controller._save_setting.assert_not_called()
    assert "по имени и индексу" in root.mic_combobox.itemData(
        1, Qt.ItemDataRole.ToolTipRole
    )


def test_missing_saved_microphone_is_not_replaced_by_first_device(panel):
    root, controller, callbacks = panel
    controller.refresh_microphones()
    callbacks.pop()([ASRInputDevice(24, "Other microphone", "WASAPI")])
    assert root.mic_combobox.currentData() is None
    assert "Desk microphone" in root.mic_combobox.currentText()
    assert not root.mic_test_button.isEnabled()
    controller.event_bus.emit.assert_not_called()


def test_stale_refresh_response_cannot_replace_new_selection(panel):
    root, controller, callbacks = panel
    controller.refresh_microphones()
    controller.refresh_microphones()
    callbacks[1]([ASRInputDevice(30, "Desk microphone", "WASAPI")])
    callbacks[0]([ASRInputDevice(24, "Desk microphone", "WASAPI")])
    assert root.mic_combobox.currentData().index == 30


def test_wheel_does_not_change_microphone(panel):
    root, controller, callbacks = panel
    combo = root.mic_combobox
    combo.addItem("First", ASRInputDevice(0, "First", "WASAPI"))
    combo.addItem("Second", ASRInputDevice(1, "Second", "WASAPI"))
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(combo, event)
    assert combo.currentIndex() == 0
    assert not event.isAccepted()


def test_model_catalog_opens_asr_category(panel):
    from core.events import Events

    root, controller, callbacks = panel
    controller._open_asr_catalog()
    controller.event_bus.emit.assert_called_once_with(
        Events.GUI.SHOW_WINDOW, {"window_id": "ai_hub", "payload": {"category": "asr"}}
    )
    assert root.asr_restart_button.parentWidget() is not root.asr_status_badge


def test_status_badge_uses_semantic_colors_and_loading_indicator(panel):
    from styles.theme import get_theme

    root, controller, callbacks = panel
    theme = get_theme()
    root.asr_init_status.set_status("Ready", "ok")
    assert root.asr_status_badge.dot.color.name() == theme["success"]
    root.asr_init_status.set_status("Loading", "progress")
    assert root.asr_status_badge.dot.color.name() == theme["accent"]
    assert root.asr_status_badge.dot._timer.isActive()
    root.asr_init_status.set_status("Error", "warn")
    assert root.asr_status_badge.dot.color.name() == theme["danger"]
    assert not root.asr_status_badge.dot._timer.isActive()


def test_hiding_settings_stops_monitor_and_button_names_the_actual_device(panel):
    root, controller, callbacks = panel
    device = ASRInputDevice(24, "Desk microphone", "WASAPI")
    root.mic_combobox.addItem(device.name, device)
    monitor_controller = root.mic_monitor_controller
    monitor = Mock()
    monitor.snapshot.return_value = MonitorState("stopped")
    monitor.start.return_value = True
    monitor_controller.monitor = monitor
    root.show()
    QApplication.processEvents()
    monitor.snapshot.return_value = MonitorState("listening", device, 0.5)
    root.mic_test_button.setChecked(True)
    monitor.start.assert_called_once_with(device)
    assert "Desk microphone" in root.mic_test_device_label.text()
    monitor.snapshot.return_value = MonitorState("stopped")
    root.hide()
    assert monitor.stop.called
    assert not root.mic_test_button.isChecked()


def test_backend_selector_only_offers_current_endpoint_and_updates_monitor(panel):
    root, controller, callbacks = panel
    root.settings.update(NM_MICROPHONE_UID="desk", NM_MICROPHONE_BACKEND="MME")
    mme = ASRInputDevice(1, "Desk microphone", "MME", uid="desk")
    wasapi = ASRInputDevice(38, "Desk microphone", "WASAPI", uid="desk")
    other = ASRInputDevice(2, "Other", "DirectSound", uid="other")
    controller.refresh_microphones()
    callbacks.pop()(
        AudioInputCatalog(
            devices=(wasapi, other),
            representations=(mme, wasapi, other),
            compatible_representations=(mme, wasapi, other),
        )
    )
    backend = root.mic_backend_combobox
    assert [backend.itemData(i) for i in range(backend.count())] == [
        "",
        "MME",
        "WASAPI",
    ]
    assert backend.currentData() == "MME"
    assert root.mic_combobox.currentData().index == 1
    controller.event_bus.emit.assert_not_called()
    backend.setCurrentIndex(0)
    controller._on_backend_changed(0)
    assert root.mic_combobox.currentData().index == 38
    assert controller.event_bus.emit.call_args.args[1].backend == ""


def test_unavailable_backend_preserved_and_disables_microphone_test(panel):
    root, controller, callbacks = panel
    root.settings.update(NM_MICROPHONE_UID="desk", NM_MICROPHONE_BACKEND="MME")
    wasapi = ASRInputDevice(38, "Desk microphone", "WASAPI", uid="desk")
    controller.refresh_microphones()
    callbacks.pop()(
        AudioInputCatalog(devices=(wasapi,), compatible_representations=(wasapi,))
    )
    assert root.mic_backend_combobox.currentData() == "MME"
    assert not root.mic_monitor_controller.button.isEnabled()
    controller.event_bus.emit.assert_not_called()


@pytest.mark.parametrize("missing", ["mic_combobox", "mic_refresh_button"])
def test_microphone_setting_arrives_before_widgets_are_ready(panel, missing):
    root, controller, callbacks = panel
    widget = getattr(root, missing)
    setattr(root, missing, None)
    assert controller._widgets_signature() is None
    controller._reflect_external_setting(
        SimpleNamespace(key="NM_MICROPHONE_UID", value="desk")
    )
    controller.refresh_microphones()
    assert not callbacks
    setattr(root, missing, widget)
    assert controller._widgets_signature() is not None
    controller.refresh_microphones(prefer_saved=True)
    assert len(callbacks) == 1
    callbacks.pop()([ASRInputDevice(38, "Desk microphone", "WASAPI")])
    assert root.mic_combobox.currentData().index == 38


def test_microphone_catalog_callback_ignores_replaced_widgets(panel):
    root, controller, callbacks = panel
    controller.refresh_microphones()
    combo = root.mic_combobox
    root.mic_combobox = None
    callbacks.pop()([ASRInputDevice(38, "Desk microphone", "WASAPI")])
    assert combo.count() == 0
    root.mic_combobox = combo
