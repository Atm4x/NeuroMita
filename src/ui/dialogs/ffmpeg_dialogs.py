from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from pathlib import Path
from utils.translation_manager import t

def create_ffmpeg_install_popup(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle(t("dialogs.ffmpeg.title"))
    dialog.setFixedSize(300, 100)
    layout = QVBoxLayout(dialog)
    label = QLabel(t("dialogs.ffmpeg.installing"))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    return dialog

def show_ffmpeg_error_popup(parent):
    error_dialog = QDialog(parent)
    error_dialog.setWindowTitle(t("dialogs.ffmpeg.error_title"))
    error_dialog.setModal(True)

    layout = QVBoxLayout(error_dialog)

    message = t("dialogs.ffmpeg.error_message", path=str(Path('.').resolve()))

    label = QLabel(message)
    layout.addWidget(label)

    ok_button = QPushButton(t("common.ok"))
    ok_button.clicked.connect(error_dialog.accept)
    layout.addWidget(ok_button, alignment=Qt.AlignmentFlag.AlignCenter)

    error_dialog.exec()