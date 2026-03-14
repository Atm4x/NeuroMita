from PyQt6.QtWidgets import QDialog, QVBoxLayout
from utils.translation_manager import t
from main_logger import logger

def handle_voice_model_dialog(gui, data):
    try:
        callback = data.get('callback')

        dialog_exists = False
        if getattr(gui, "_voice_model_dialog", None):
            try:
                gui._voice_model_dialog.isVisible()
                if gui._voice_model_dialog.layout() and gui._voice_model_dialog.layout().count() > 0:
                    dialog_exists = True
            except:
                gui._voice_model_dialog = None
        
        if dialog_exists:
            if callback:
                callback(gui._voice_model_dialog)
            gui._voice_model_dialog.show()
            gui._voice_model_dialog.raise_()
            gui._voice_model_dialog.activateWindow()
            return
        
        if getattr(gui, "_voice_model_dialog", None):
            try:
                gui._voice_model_dialog.close()
                gui._voice_model_dialog.deleteLater()
            except:
                pass
            gui._voice_model_dialog = None
        
        dialog = QDialog(gui)
        dialog.setWindowTitle(_("Управление локальными моделями", "Manage Local Models"))
        dialog.setModal(False)
        dialog.resize(875, 800)
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        
        gui._voice_model_dialog = dialog
        
        def on_dialog_closed():
            if gui._voice_model_dialog:
                gui._voice_model_dialog.hide()
        
        dialog.finished.connect(on_dialog_closed)
        
        if callback:
            callback(dialog)
        
        dialog.show()
        
    except Exception as e:
        logger.error(f"Ошибка при создании диалога: {e}", exc_info=True)
        error_callback = data.get('error_callback')
        if error_callback:
            error_callback(str(e))