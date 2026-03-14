from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt
from utils.translation_manager import t

def create_model_loading_dialog(parent, model_name, cancel_callback):
    dialog = QDialog(parent)
    dialog.setWindowTitle(t("dialogs.model_loading.title") + f" {model_name}")
    dialog.setFixedSize(400, 300)
    dialog.setModal(True)
    
    layout = QVBoxLayout(dialog)
    
    title_label = QLabel(t("ui.dialogs.model_loading.title") + f" {model_name}")
    title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    
    wait_label = QLabel(t("common.please_wait"))
    wait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(wait_label)
    
    loading_progress = QProgressBar()
    loading_progress.setRange(0, 0)
    layout.addWidget(loading_progress)
    
    loading_status_label = QLabel(t("common.initializing"))
    loading_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(loading_status_label)
    
    cancel_button = QPushButton(t("common.cancel"))
    cancel_button.clicked.connect(cancel_callback)
    layout.addWidget(cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)
    
    return dialog, loading_progress, loading_status_label