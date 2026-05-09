from __future__ import annotations

from styles.theme import get_theme
from utils import render_qss

DIALOG_QSS_TEMPLATE = """
    QDialog#ActionDialog {
        background-color: {panel_bg};
        color: {text};
        border: 1px solid {outline};
    }

    QDialog#ActionDialog QLabel {
        background-color: transparent;
        color: {text};
    }

    QDialog#ActionDialog QLabel#TitleLabel {
        font-size: 11pt;
        font-weight: bold;
    }

    QDialog#ActionDialog QLabel#WarningLabel {
        font-weight: bold;
        color: {warn_text};
    }

    QDialog#ActionDialog QTextEdit#LogArea {
        background-color: {app_bg};
        color: {muted};
        font-family: "Consolas", "Courier New", monospace;
        font-size: 9pt;
        border: 1px solid {border_soft};
    }

    QDialog#ActionDialog QProgressBar {
        border: 1px solid {border_soft};
        border-radius: 2px;
        text-align: center;
        background-color: {chip_hover};
        color: {text};
        height: 12px;
    }

    QDialog#ActionDialog QProgressBar::chunk {
        background-color: {accent};
        border-radius: 2px;
    }

    QDialog#ActionDialog QPushButton {
        background-color: {chip_hover};
        color: {text};
        border: 1px solid {border_soft};
        padding: 5px 14px;
        border-radius: 3px;
    }
    QDialog#ActionDialog QPushButton:hover {
        background-color: {chip_pressed};
        border-color: {accent_border};
    }
    QDialog#ActionDialog QPushButton:pressed {
        background-color: {chip_bg};
    }
    QDialog#ActionDialog QPushButton:disabled {
        background-color: {btn_disabled_bg};
        color: {btn_disabled_fg};
        border-color: {outline};
    }

    QDialog#ActionDialog QPushButton#RetryButton {
        background-color: {accent};
        font-weight: bold;
    }
    QDialog#ActionDialog QPushButton#RetryButton:hover {
        background-color: {accent_hover};
    }

    QDialog#ActionDialog QPushButton#ContinueButton {
        background-color: {accent};
        font-weight: bold;
    }
    QDialog#ActionDialog QPushButton#ContinueButton:hover {
        background-color: {accent_hover};
    }
"""


def get_dialog_stylesheet(theme_name: str | None = None) -> str:
    theme = get_theme(name=theme_name)
    return render_qss(DIALOG_QSS_TEMPLATE, theme)
