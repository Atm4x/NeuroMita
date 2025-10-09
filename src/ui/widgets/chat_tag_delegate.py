from PyQt6.QtWidgets import QStyledItemDelegate, QApplication
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QFontMetrics, QFont
from PyQt6.QtCore import Qt, QSize, QRect

from ui.chat.chat_delegate import ChatMessageDelegate
from utils import process_text_to_voice

class ChatTagDelegate(QStyledItemDelegate):
    """
    Делегат для отображения текста с тегами из чата в QTableView.
    Использует логику ChatMessageDelegate для форматирования.
    """
    def __init__(self, parent=None, gui_instance=None):
        super().__init__(parent)
        self.chat_delegate = ChatMessageDelegate()
        self.gui_instance = gui_instance # Нужен для получения настроек, например, HIDE_CHAT_TAGS

    def paint(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return

        hide_tags = False
        if self.gui_instance and hasattr(self.gui_instance, "_get_setting"):
            hide_tags = self.gui_instance._get_setting("HIDE_CHAT_TAGS", False)

        # Обработка текста с тегами
        processed_parts = self.chat_delegate.split_text_with_tags(text, hide_tags)

        document = QTextDocument()
        document.setDefaultStyleSheet(self._get_stylesheet()) # Применяем стили для тегов
        
        html_content = ""
        for part in processed_parts:
            content = part["content"]
            if part["tag"] == "tag_green":
                html_content += f'<span style="color:{self.chat_delegate.tag_color.name()};">{content}</span>'
            else:
                html_content += content # Обычный текст
        
        document.setHtml(html_content)
        document.setTextWidth(option.rect.width())

        painter.save()
        painter.translate(option.rect.topLeft())
        document.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return super().sizeHint(option, index)

        hide_tags = False
        if self.gui_instance and hasattr(self.gui_instance, "_get_setting"):
            hide_tags = self.gui_instance._get_setting("HIDE_CHAT_TAGS", False)

        processed_parts = self.chat_delegate.split_text_with_tags(text, hide_tags)
        
        document = QTextDocument()
        document.setDefaultStyleSheet(self._get_stylesheet())
        
        html_content = ""
        for part in processed_parts:
            content = part["content"]
            if part["tag"] == "tag_green":
                html_content += f'<span style="color:{self.chat_delegate.tag_color.name()};">{content}</span>'
            else:
                html_content += content
        
        document.setHtml(html_content)
        document.setTextWidth(option.rect.width())
        
        # Возвращаем размер, который нужен для отображения всего содержимого
        return QSize(document.idealWidth(), int(document.size().height()))

    def _get_stylesheet(self):
        # Можно добавить более сложные стили, если потребуется
        return ""