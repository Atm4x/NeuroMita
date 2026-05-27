from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from managers.settings_manager import SettingsManager
from ui.widgets.settings_overlay_widget import SettingsOverlay, SettingsResizeHandle
from ui.widgets.settings_icon_button import SettingsIconButton
from utils import _


# ---------------------------------------------------------------------------
# Per-section enable/disable
# ---------------------------------------------------------------------------
# The old INTERFACE_MODE (Basic/Advanced/Full) is replaced by independent
# per-section toggles. Each toggleable category gets a setting key in the
# SettingsManager. Defaults reproduce the old "Basic" set: only api and
# characters are enabled out of the box (general is always on, can't be
# toggled off).

SECTION_DEFAULTS: dict[str, bool] = {
    "api":         True,
    "characters":  True,
    "voice":       False,
    "microphone":  False,
    "game":        False,
    "models":      False,
    "screen":      False,
    "debug":       False,
    "news":        False,
    "data":        False,
}

TOGGLEABLE_SECTIONS = tuple(SECTION_DEFAULTS.keys())


SECTION_LABELS = {
    "api":         (_("API",         "API"),         "fa6s.plug"),
    "characters":  (_("Персонажи",   "Characters"),  "fa6s.user"),
    "voice":       (_("Озвучка",     "Voice"),       "fa6s.volume-high"),
    "microphone":  (_("Микрофон",    "Microphone"),  "fa6s.microphone"),
    "game":        (_("Игра",        "Game"),        "fa5s.gamepad"),
    "models":      (_("Модели",      "Models"),      "fa6s.robot"),
    "screen":      (_("Экран",       "Screen"),      "fa6s.display"),
    "debug":       (_("Отладка",     "Debug"),       "fa6s.bug"),
    "news":        (_("Новости",     "News"),        "fa6s.newspaper"),
    "data":        (_("Данные",      "Data"),        "fa5s.database"),
}


def _section_key(cat: str) -> str:
    return f"SECTION_{cat.upper()}_ENABLED"


def is_section_enabled(cat: str) -> bool:
    """Returns whether the category should appear in the sidebar.

    'general' is hard-coded to True (the page hosts the section toggles
    themselves, so it must stay accessible)."""
    if cat == "general":
        return True
    if cat not in SECTION_DEFAULTS:
        return True  # unknown categories stay visible
    default = SECTION_DEFAULTS[cat]
    return bool(SettingsManager.get(_section_key(cat), default))


def set_section_enabled(cat: str, enabled: bool) -> None:
    if cat == "general" or cat not in SECTION_DEFAULTS:
        return
    SettingsManager.set(_section_key(cat), bool(enabled))


def apply_section_visibility(gui) -> None:
    """Show/hide sidebar icons based on the per-section booleans, and
    auto-close the overlay if the user just hid the active category."""
    buttons = getattr(gui, "settings_buttons", None) or {}
    for cat, btn in buttons.items():
        btn.setVisible(is_section_enabled(cat))

    active = getattr(gui, "current_settings_category", None)
    if active and not is_section_enabled(active):
        try:
            gui.show_settings_category(active)  # toggling re-hides the overlay
        except Exception:
            pass

    # Status indicators (capture toggles) live behind the 'screen' section.
    try:
        from ui.widgets.status_indicators_widget import apply_capture_visibility
        apply_capture_visibility(gui)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Backwards-compatible shims
# ---------------------------------------------------------------------------
# Some legacy widgets (guide_widget) still import normalize_mode / call
# apply_interface_mode. Keep no-op stubs so we don't crash, but they no
# longer drive visibility.

def normalize_mode(v):
    m = (v or "").strip().lower()
    if m in ("advanced", "продвинутый"):
        return "advanced"
    if m in ("full", "полный"):
        return "full"
    return "basic"


def apply_interface_mode(gui, mode_value):
    # Kept for any external caller that still passes an interface mode.
    # The new system is driven by per-section toggles, so we just apply
    # the current visibility map and ignore the argument.
    apply_section_visibility(gui)


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
    gui.settings_resize_handle = SettingsResizeHandle(gui.settings_overlay, gui)
    gui.SETTINGS_RESIZE_HANDLE_WIDTH = gui.settings_resize_handle.width()
    gui.settings_resize_handle.hide()

    gui.settings_buttons = {}

    # The sidebar shows one button per category. "general" always lives
    # at the top (and is mandatory); the rest can be toggled on/off via
    # checkboxes on the General page.
    settings_categories = [
        ("fa6s.gear",       _("Общие",      "General"),     "general"),
        ("fa6s.plug",       _("API",         "API"),         "api"),
        ("fa6s.user",       _("Персонажи",   "Characters"),  "characters"),
        ("fa6s.volume-high",_("Озвучка",     "Voice"),       "voice"),
        ("fa6s.microphone", _("Микрофон",    "Microphone"),  "microphone"),
        ("fa5s.gamepad",    _("Игра",        "Game"),        "game"),
        ("fa6s.robot",      _("Модели",      "Models"),      "models"),
        ("fa6s.display",    _("Экран",       "Screen"),      "screen"),
        ("fa6s.bug",        _("Отладка",     "Debug"),       "debug"),
        ("fa6s.newspaper",  _("Новости",     "News"),        "news"),
        ("fa5s.database",   _("Данные",      "Data"),        "data"),
    ]

    for icon_name, tooltip, category in settings_categories:
        btn = SettingsIconButton(icon_name, tooltip)
        btn.clicked.connect(lambda checked, cat=category: gui.show_settings_category(cat))
        panel_layout.addWidget(btn)
        gui.settings_buttons[category] = btn

    panel_layout.addStretch()

    main_layout.addWidget(gui.settings_resize_handle)
    main_layout.addWidget(gui.settings_overlay)
    main_layout.addWidget(settings_panel)
