from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from core.events import Events
from utils.translation_manager import t
import asyncio

def show_tg_code_dialog(parent, code_future, event_bus):
    dialog = QDialog(parent)
    dialog.setWindowTitle(t("dialogs.telegram.code.title"))
    dialog.setFixedSize(300, 150)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

    layout = QVBoxLayout(dialog)
    label = QLabel(t("dialogs.telegram.code.label"))
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(label)

    code_entry = QLineEdit()
    code_entry.setMaxLength(10)
    code_entry.setFocus()
    layout.addWidget(code_entry)

    def submit_code():
        code = code_entry.text().strip()
        if code:
            if code_future and not code_future.done():
                loop = event_bus.emit_and_wait(Events.Core.GET_EVENT_LOOP, timeout=1.0)
                if loop and loop[0] and loop[0].is_running():
                    loop[0].call_soon_threadsafe(code_future.set_result, code)
            dialog.accept()
        else:
            QMessageBox.critical(dialog, t("common.error"), t("dialogs.telegram.code.error"))

    def on_reject():
        if code_future and not code_future.done():
            loop = event_bus.emit_and_wait(Events.Core.GET_EVENT_LOOP, timeout=1.0)
            if loop and loop[0] and loop[0].is_running():
                loop[0].call_soon_threadsafe(code_future.set_exception, asyncio.CancelledError(t("dialogs.telegram.code.cancelled")))

    btn = QPushButton(t("dialogs.telegram.code.confirm_btn"))
    btn.clicked.connect(submit_code)
    layout.addWidget(btn)
    code_entry.returnPressed.connect(submit_code)

    dialog.rejected.connect(on_reject)
    dialog.exec()

def show_tg_password_dialog(parent, password_future, event_bus):
    dialog = QDialog(parent)
    dialog.setWindowTitle(t("dialogs.telegram.password.title"))
    dialog.setFixedSize(300, 150)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

    layout = QVBoxLayout(dialog)
    label = QLabel(t("dialogs.telegram.password.label"))
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(label)

    password_entry = QLineEdit()
    password_entry.setEchoMode(QLineEdit.EchoMode.Password)
    password_entry.setFocus()
    layout.addWidget(password_entry)

    def submit_password():
        pwd = password_entry.text().strip()
        if pwd:
            if password_future and not password_future.done():
                loop = event_bus.emit_and_wait(Events.Core.GET_EVENT_LOOP, timeout=1.0)
                if loop and loop[0] and loop[0].is_running():
                    loop[0].call_soon_threadsafe(password_future.set_result, pwd)
            dialog.accept()
        else:
            QMessageBox.critical(dialog, t("common.error"), t("dialogs.telegram.password.error"))

    def on_reject():
        if password_future and not password_future.done():
            loop = event_bus.emit_and_wait(Events.Core.GET_EVENT_LOOP, timeout=1.0)
            if loop and loop[0] and loop[0].is_running():
                loop[0].call_soon_threadsafe(password_future.set_exception, asyncio.CancelledError(t("dialogs.telegram.password.cancelled")))

    btn = QPushButton(t("dialogs.telegram.password.confirm_btn"))
    btn.clicked.connect(submit_password)
    layout.addWidget(btn)
    password_entry.returnPressed.connect(submit_password)

    dialog.rejected.connect(on_reject)
    dialog.exec()