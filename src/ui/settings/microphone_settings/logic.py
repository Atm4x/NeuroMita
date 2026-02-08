import re
from PyQt6.QtCore import Qt, QTimer, QSignalBlocker
from utils import getTranslationVariant as _
from main_logger import logger
from core.events import get_event_bus, Events
from styles.main_styles import get_theme


def wire_microphone_settings_logic(self):
    theme = get_theme()

    def _pill_style(kind: str):
        if kind == "ok":
            fg = theme["success"]
            bg = "rgba(61,166,110,0.12)"
            br = "rgba(61,166,110,0.45)"
        elif kind == "warn":
            fg = theme["danger"]
            bg = "rgba(214,69,69,0.12)"
            br = "rgba(214,69,69,0.45)"
        elif kind == "progress":
            fg = theme["accent"]
            bg = "rgba(138,43,226,0.12)"
            br = theme["accent_border"]
        else:
            fg = theme["text"]
            bg = theme["chip_bg"]
            br = theme["border_soft"]
        return fg, bg, br

    def set_pill(data: dict):
        try:
            lbl = data.get("label")
            if lbl is None:
                return
            text = str(data.get("text", "") or "")
            kind = str(data.get("kind", "info") or "info")

            fg, bg, br = _pill_style(kind)
            lbl.setText(text)
            lbl.setStyleSheet(
                f"QLabel {{ padding: 2px 6px; border-radius: 8px; "
                f"font-weight: 600; font-size: 11px; "
                f"color: {fg}; background: {bg}; border: 1px solid {br}; }}"
            )
        except Exception as e:
            logger.debug(f"asr_set_pill handler failed: {e}")

    def reset_init_status():
        if hasattr(self, "asr_init_status") and self.asr_init_status is not None:
            try:
                if hasattr(self, "asr_set_pill"):
                    self.asr_set_pill.emit({"label": self.asr_init_status, "text": "—", "kind": "info"})
                    return
            except Exception:
                pass
            try:
                set_pill({"label": self.asr_init_status, "text": "—", "kind": "info"})
            except Exception:
                pass

    if hasattr(self, "asr_set_pill"):
        try:
            if hasattr(self, "_on_asr_set_pill"):
                self.asr_set_pill.disconnect(self._on_asr_set_pill)
        except Exception:
            pass

        self._on_asr_set_pill = set_pill
        try:
            self.asr_set_pill.connect(self._on_asr_set_pill)
        except Exception:
            pass

    reset_init_status()

    eb = get_event_bus()
    # ---------------------------
    # ASR runtime params (VAD/Audio)
    # ---------------------------
    required_widgets = [
        "asr_sample_rate_spinbox",
        "asr_chunk_size_spinbox",
        "asr_vad_threshold_spinbox",
        "asr_silence_timeout_spinbox",
        "asr_pre_buffer_spinbox",
    ]
    if not all(hasattr(self, n) for n in required_widgets):
        return

    SETTINGS_KEYS = {
        "VOSK_SAMPLE_RATE": "ASR_VOSK_SAMPLE_RATE",
        "CHUNK_SIZE": "ASR_CHUNK_SIZE",
        "VAD_THRESHOLD": "ASR_VAD_THRESHOLD",
        "VAD_SILENCE_TIMEOUT_SEC": "ASR_VAD_SILENCE_TIMEOUT_SEC",
        "VAD_PRE_BUFFER_DURATION_SEC": "ASR_VAD_PRE_BUFFER_DURATION_SEC",
    }

    def _get_ui_params() -> dict:
        return {
            "VOSK_SAMPLE_RATE": int(self.asr_sample_rate_spinbox.value()),
            "CHUNK_SIZE": int(self.asr_chunk_size_spinbox.value()),
            "VAD_THRESHOLD": float(self.asr_vad_threshold_spinbox.value()),
            "VAD_SILENCE_TIMEOUT_SEC": float(self.asr_silence_timeout_spinbox.value()),
            "VAD_PRE_BUFFER_DURATION_SEC": float(self.asr_pre_buffer_spinbox.value()),
        }

    def _set_ui_params(params: dict) -> None:
        params = params or {}

        def _apply():
            try:
                with QSignalBlocker(self.asr_sample_rate_spinbox):
                    self.asr_sample_rate_spinbox.setValue(int(params.get("VOSK_SAMPLE_RATE", 16000)))
                with QSignalBlocker(self.asr_chunk_size_spinbox):
                    self.asr_chunk_size_spinbox.setValue(int(params.get("CHUNK_SIZE", 512)))
                with QSignalBlocker(self.asr_vad_threshold_spinbox):
                    self.asr_vad_threshold_spinbox.setValue(float(params.get("VAD_THRESHOLD", 0.5)))
                with QSignalBlocker(self.asr_silence_timeout_spinbox):
                    self.asr_silence_timeout_spinbox.setValue(float(params.get("VAD_SILENCE_TIMEOUT_SEC", 0.15)))
                with QSignalBlocker(self.asr_pre_buffer_spinbox):
                    self.asr_pre_buffer_spinbox.setValue(float(params.get("VAD_PRE_BUFFER_DURATION_SEC", 0.3)))
            except Exception as e:
                logger.debug(f"_set_ui_params failed: {e}")

        # event может прийти не из UI потока
        QTimer.singleShot(0, _apply)

    def _get_current_device_id() -> int:
        # 1) пробуем из combobox (там строка вида "... (3)")
        try:
            idx = self.mic_combobox.currentIndex() if hasattr(self, "mic_combobox") else -1
            if idx is not None and idx >= 0 and hasattr(self, "mic_combobox"):
                full = self.mic_combobox.itemData(idx, Qt.ItemDataRole.UserRole)
                if isinstance(full, str):
                    m = re.search(r"\((\d+)\)\s*$", full)
                    if m:
                        return int(m.group(1))
        except Exception:
            pass

        # 2) fallback: settings
        try:
            return int(self.settings.get("NM_MICROPHONE_ID", 0) or 0)
        except Exception:
            return 0

    # debounce timer
    if not hasattr(self, "_asr_params_debounce_timer") or self._asr_params_debounce_timer is None:
        self._asr_params_debounce_timer = QTimer()
        self._asr_params_debounce_timer.setSingleShot(True)
        self._asr_params_debounce_timer.setInterval(250)

    def _persist_params(params: dict):
        for rk, sk in SETTINGS_KEYS.items():
            try:
                eb.emit(Events.Settings.SAVE_SETTING, {"key": sk, "value": params.get(rk)})
            except Exception:
                pass

    def _restart_recognition_if_active():
        try:
            mic_active = bool(self.mic_active_checkbox.isChecked()) if hasattr(self, "mic_active_checkbox") else bool(
                self.settings.get("MIC_ACTIVE", False)
            )
        except Exception:
            mic_active = False

        if not mic_active:
            return

        device_id = _get_current_device_id()
        eb.emit(Events.Speech.RESTART_SPEECH_RECOGNITION, {"device_id": device_id})

    def _apply_from_ui_debounced():
        params = _get_ui_params()
        if params == getattr(self, "_asr_last_sent_params", None):
            return
        self._asr_last_sent_params = dict(params)

        eb.emit(Events.Speech.SET_ASR_RUNTIME_PARAMS, {"params": params, "source": "ui"})
        _persist_params(params)
        _restart_recognition_if_active()

    try:
        self._asr_params_debounce_timer.timeout.disconnect()
    except Exception:
        pass
    self._asr_params_debounce_timer.timeout.connect(_apply_from_ui_debounced)

    def _schedule_apply():
        try:
            self._asr_params_debounce_timer.start()
        except Exception:
            pass

    # connect UI -> debounce
    for w in (
        self.asr_sample_rate_spinbox,
        self.asr_chunk_size_spinbox,
        self.asr_vad_threshold_spinbox,
        self.asr_silence_timeout_spinbox,
        self.asr_pre_buffer_spinbox,
    ):
        try:
            # чтобы не накапливать коннекты при повторном wire
            if hasattr(w, "_asr_value_changed_handler"):
                try:
                    w.valueChanged.disconnect(w._asr_value_changed_handler)
                except Exception:
                    pass

            def _h(_v=None, _schedule=_schedule_apply):
                _schedule()

            w._asr_value_changed_handler = _h
            w.valueChanged.connect(w._asr_value_changed_handler)
        except Exception:
            pass

    # subscribe backend -> UI
    if not bool(getattr(self, "_asr_params_events_subscribed", False)):
        self._asr_params_events_subscribed = True

        def _on_asr_params_changed(event):
            data = event.data if isinstance(event.data, dict) else {}
            params = data.get("params") if isinstance(data.get("params"), dict) else data
            if isinstance(params, dict):
                _set_ui_params(params)

        eb.subscribe(Events.Speech.ASR_PARAMS_CHANGED, _on_asr_params_changed, weak=False)

    # request current runtime values when UI opens/wired
    QTimer.singleShot(0, lambda: eb.emit(Events.Speech.ASR_PARAMS_REQUEST, {"source": "ui"}))


def on_mic_selected(gui, full_device_name=None):
    if not hasattr(gui, "mic_combobox"):
        return
    bus = get_event_bus()

    if full_device_name is None:
        idx = gui.mic_combobox.currentIndex()
        if idx >= 0:
            full_device_name = gui.mic_combobox.itemData(idx, Qt.ItemDataRole.UserRole)

    selection = full_device_name or ""
    if selection and "(" in selection:
        try:
            microphone_name = selection.rsplit(" (", 1)[0]
            m = re.search(r"\((\d+)\)\s*$", selection)
            if m:
                device_id = int(m.group(1))
                bus.emit(Events.Speech.SET_MICROPHONE, {"name": microphone_name, "device_id": device_id})
                if gui.settings.get("MIC_ACTIVE", False):
                    bus.emit(Events.Speech.RESTART_SPEECH_RECOGNITION, {"device_id": device_id})
        except Exception as e:
            logger.error(f"Ошибка выбора микрофона: {e}")


def load_mic_settings(gui):
    try:
        bus = get_event_bus()
        device_id = gui.settings.get("NM_MICROPHONE_ID", 0)
        device_name = gui.settings.get("NM_MICROPHONE_NAME", "")
        bus.emit(Events.Speech.SET_MICROPHONE, {"name": device_name, "device_id": device_id})

        if gui.settings.get("MIC_ACTIVE", False) and hasattr(gui, "mic_active_checkbox"):
            gui.mic_active_checkbox.setChecked(True)

    except Exception as e:
        logger.error(f"Ошибка загрузки настроек микрофона: {e}")