import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QSizePolicy
)
from ui.gui_templates import create_setting_widget, create_section_header
from utils.translation_manager import t
from core.events import get_event_bus, Events


def build_voiceover_settings_ui(self, parent_layout):
    sidebar_w = getattr(self, "SETTINGS_SIDEBAR_WIDTH", 50)
    right_pad = max(8, min(14, int(sidebar_w * 0.22)))

    container = QWidget()
    container_lay = QVBoxLayout(container)
    container_lay.setContentsMargins(0, 0, right_pad, 0)
    container_lay.setSpacing(6)

    create_section_header(container_lay, t("ui.settings.voiceover.title"))

    self.voiceover_section = type('obj', (object,), {'content_frame': parent_layout.parent()})()

    main_config = [
        {'label': t('ui.settings.voiceover.use_speech'),
         'key': 'USE_VOICEOVER', 'type': 'checkbutton',
         'default_checkbutton': False, 'widget_name': 'use_voice_checkbox'},
        {'label': t("ui.settings.voiceover.method"),
         'key': 'VOICEOVER_METHOD', 'type': 'combobox',
         'options': ["TG", "Local"], 'default': 'TG',
         'widget_name': 'method_combobox'},
    ]

    for cfg in main_config:
        widget = create_setting_widget(
            gui=self,
            parent=container,
            label=cfg.get('label'),
            setting_key=cfg.get('key', ''),
            widget_type=cfg.get('type', 'entry'),
            options=cfg.get('options'),
            default=cfg.get('default', ''),
            default_checkbutton=cfg.get('default_checkbutton', False),
            widget_name=cfg.get('widget_name')
        )
        if widget:
            container_lay.addWidget(widget)
            if cfg.get('widget_name') == 'method_combobox':
                self.method_frame = widget

    self.tg_settings_frame = QWidget()
    tg_layout = QVBoxLayout(self.tg_settings_frame)
    tg_layout.setContentsMargins(0, 0, 0, 0)
    tg_layout.setSpacing(4)

    tg_config = [
        {'label': t('ui.settings.voiceover.tg_autoconnect'),
         'key': 'TG_AUTOCONNECT', 'type': 'checkbutton',
         'default_checkbutton': False},

        {'label': t('ui.settings.voiceover.tg_connect'),
         'type': 'button',
         'command': (lambda: get_event_bus().emit(Events.Telegram.START_SILERO, {"source": "ui", "force": True})),
         'widget_name': 'tg_connect_button'},

        {'label': t('ui.settings.voiceover.channel_service'), 'key': 'AUDIO_BOT',
         'type': 'combobox', 'options': ["@silero_voice_bot", "@CrazyMitaAIbot"],
         'default': "@silero_voice_bot"},

        {'label': t('ui.settings.voiceover.max_wait'), 'key': 'SILERO_TIME',
         'type': 'entry', 'default': '12', 'validation': getattr(self, 'validate_number_0_60', None)},

        {'label': t('ui.settings.voiceover.tg_api_settings'), 'type': 'text'},
        {'label': t('ui.settings.voiceover.hidden_after_restart'), 'type': 'text'},

        {'label': t('ui.settings.voiceover.tg_id'), 'key': 'NM_TELEGRAM_API_ID', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},
        {'label': t('ui.settings.voiceover.tg_hash'), 'key': 'NM_TELEGRAM_API_HASH', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},
        {'label': t('ui.settings.voiceover.tg_phone'), 'key': 'NM_TELEGRAM_PHONE', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},
    ]

    for cfg in tg_config:
        widget = create_setting_widget(
            gui=self,
            parent=self.tg_settings_frame,
            label=cfg['label'],
            setting_key=cfg.get('key', ''),
            widget_type=cfg.get('type', 'entry'),
            options=cfg.get('options'),
            default=cfg.get('default', ''),
            validation=cfg.get('validation'),
            hide=cfg.get('hide', False),
            default_checkbutton=cfg.get('default_checkbutton', False),
            command=cfg.get('command'),
            widget_name=cfg.get('widget_name'),
        )
        if widget:
            tg_layout.addWidget(widget)

    container_lay.addWidget(self.tg_settings_frame)

    self.local_settings_frame = QWidget()
    local_layout = QVBoxLayout(self.local_settings_frame)
    local_layout.setContentsMargins(0, 0, 0, 0)
    local_layout.setSpacing(4)

    local_model_row = QWidget()
    local_model_layout = QHBoxLayout(local_model_row)
    local_model_layout.setContentsMargins(0, 2, 0, 2)
    local_model_layout.setSpacing(10)

    label_part = QHBoxLayout()
    label_part.setContentsMargins(0, 0, 0, 0)
    label_part.setSpacing(2)

    local_model_label = QLabel(t("ui.settings.voiceover.local_model"))

    self.local_model_status_label = QLabel("⚠️")
    self.local_model_status_label.setObjectName("WarningIcon")
    self.local_model_status_label.setToolTip(t("ui.settings.voiceover.model_not_initialized"))
    self.local_model_status_label.setFixedWidth(16)
    self.local_model_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    label_part.addWidget(self.local_model_status_label)
    label_part.addWidget(local_model_label)

    label_container = QWidget()
    label_container.setLayout(label_part)
    label_container.setMinimumWidth(140)
    label_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    self.local_voice_combobox = QComboBox()

    local_model_layout.addWidget(label_container)
    local_model_layout.addWidget(self.local_voice_combobox, 1)
    local_layout.addWidget(local_model_row)

    local_config = [
        {'label': t("ui.settings.voiceover.local_language"),
         'key': "VOICE_LANGUAGE", 'type': 'combobox',
         'options': ["ru", "en"], 'default': "ru",
         'widget_name': 'voice_language_var'},

        {'label': t('ui.settings.voiceover.autoload_model'),
         'key': 'LOCAL_VOICE_LOAD_LAST', 'type': 'checkbutton',
         'default_checkbutton': False},

        {'label': t('ui.settings.voiceover.voiceover_in_chat'),
         'key': 'VOICEOVER_LOCAL_CHAT', 'type': 'checkbutton',
         'default_checkbutton': True},

        {'label': t('ui.settings.voiceover.manage_models'),
         'type': 'button',
         'command': (lambda: get_event_bus().emit(Events.GUI.SHOW_WINDOW, {"window_id": "voice_models", "payload": {}}))}
    ]

    if os.environ.get("ENABLE_VOICE_DELETE_CHECKBOX", "0") == "1":
        local_config.insert(2, {
            'label': t('ui.settings.voiceover.delete_audio'),
            'key': 'LOCAL_VOICE_DELETE_AUDIO', 'type': 'checkbutton',
            'default_checkbutton': True
        })

    for cfg in local_config:
        widget = create_setting_widget(
            gui=self,
            parent=self.local_settings_frame,
            label=cfg.get('label'),
            setting_key=cfg.get('key', ''),
            widget_type=cfg.get('type', 'entry'),
            options=cfg.get('options'),
            default=cfg.get('default', ''),
            default_checkbutton=cfg.get('default_checkbutton', False),
            command=cfg.get('command'),
            widget_name=cfg.get('widget_name')
        )
        if widget:
            local_layout.addWidget(widget)

    container_lay.addWidget(self.local_settings_frame)

    parent_layout.addWidget(container)