from PyQt6.QtWidgets import QStyledItemDelegate, QApplication, QStyleOptionViewItem
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QFontMetrics, QFont, QPainter
from PyQt6.QtCore import Qt, QSize, QRect, QModelIndex

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

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return

        hide_tags = False
        if self.gui_instance and hasattr(self.gui_instance, "_get_setting"):
            hide_tags = self.gui_instance._get_setting("HIDE_CHAT_TAGS", False)

        processed_parts = self.chat_delegate.split_text_with_tags(text, hide_tags)

        document = QTextDocument()
        document.setDefaultFont(option.font) # Используем шрифт из option
        
        html_content = ""
        for part in processed_parts:
            content = part["content"]
            # Экранируем HTML-спецсимволы, чтобы они не интерпретировались как теги,
            # кроме тех, которые мы хотим стилизовать.
            # Для простоты, пока просто стилизуем наши теги.
            escaped_content = content.replace("&", "&").replace("<", "<").replace(">", ">")
            
            if part["tag"] == "tag_green":
                html_content += f'<span style="color:{self.chat_delegate.tag_color.name()};">{escaped_content}</span>'
            else:
                html_content += escaped_content
        
        document.setHtml(html_content)
        document.setTextWidth(option.rect.width())

        painter.save()
        painter.setClipRect(option.rect) # Обрезаем отрисовку по границам ячейки
        painter.translate(option.rect.topLeft())
        document.drawContents(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return super().sizeHint(option, index)

        hide_tags = False
        if self.gui_instance and hasattr(self.gui_instance, "_get_setting"):
            hide_tags = self.gui_instance._get_setting("HIDE_CHAT_TAGS", False)

        processed_parts = self.chat_delegate.split_text_with_tags(text, hide_tags)
        
        document = QTextDocument()
        document.setDefaultFont(option.font)
        
        html_content = ""
        for part in processed_parts:
            content = part["content"]
            escaped_content = content.replace("&", "&").replace("<", "<").replace(">", ">")
            if part["tag"] == "tag_green":
                html_content += f'<span style="color:{self.chat_delegate.tag_color.name()};">{escaped_content}</span>'
            else:
                html_content += escaped_content
        
        document.setHtml(html_content)
        # Устанавливаем ширину текста равной ширине ячейки, чтобы QTextDocument мог вычислить правильную высоту
        document.setTextWidth(option.rect.width())
        
        # Возвращаем QSize с идеальной шириной и вычисленной высотой
        # Это позволит строке таблицы автоматически подстроиться под высоту содержимого
        return QSize(int(document.idealWidth()), int(document.size().height()))