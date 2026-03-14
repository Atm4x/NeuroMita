from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from ui.widgets.settings_overlay_widget import SettingsOverlay
from ui.widgets.settings_icon_button import SettingsIconButton
from utils.translation_manager import t


def setup_settings_panel(gui, main_layout):
    settings_panel = QWidget()
    settings_panel.setFixedWidth(50)
    gui.SETTINGS_SIDEBAR_WIDTH = 50
    settings_panel.setObjectName("SettingsSidebar")

    panel_layout = QVBoxLayout(settings_panel)
    panel_layout.setContentsMargins(5, 10, 5, 10)
    panel_layout.setSpacing(5)

    gui.settings_overlay = SettingsOverlay(gui)
    gui.settings_overlay.setMaximumWidth(0)
    gui.settings_overlay.hide()

    gui.settings_buttons = {}

    settings_categories = [
        ("fa6s.gear", t("ui.widgets.settings_panel.general"), "general"),
        ("fa6s.plug", t("ui.widgets.settings_panel.api"), "api"),
        ("fa6s.robot", t("ui.widgets.settings_panel.models"), "models"),
        ("fa6s.volume-high", t("ui.widgets.settings_panel.voice"), "voice"),
        ("fa6s.microphone", t("ui.widgets.settings_panel.microphone"), "microphone"),
        ("fa6s.user", t("ui.widgets.settings_panel.characters"), "characters"),
        ("fa6s.display", t("ui.widgets.settings_panel.screen"), "screen"),
        ("fa5s.gamepad", t("ui.widgets.settings_panel.game"), "game"),
        ("fa6s.bug", t("ui.widgets.settings_panel.debug"), "debug"),
        ("fa6s.newspaper", t("ui.widgets.settings_panel.news"), "news"),
    ]

    for icon_name, tooltip, category in settings_categories:
        btn = SettingsIconButton(icon_name, tooltip)
        btn.clicked.connect(lambda checked, cat=category: gui.show_settings_category(cat))
        panel_layout.addWidget(btn)
        gui.settings_buttons[category] = btn

    panel_layout.addStretch()

    main_layout.addWidget(gui.settings_overlay)
    main_layout.addWidget(settings_panel)