from typing import Dict

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QTableView, QVBoxLayout, QWidget, QHeaderView, QMessageBox, QDialog, QTextEdit, QPushButton, QHBoxLayout, QStyledItemDelegate
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtCore import Qt, QDateTime, QVariant

from core.events import Events
from managers.database_manager import DatabaseManager
from main_logger import logger
import uuid


class DatabaseViewer(QMainWindow):
    """Окно просмотра базы данных (только чтение)."""

    def __init__(self, character_name: str = None, parent=None):
        super().__init__(parent)
        self.character_name = character_name or "All"  # По умолчанию все персонажи, или указанный
        self.db_manager = DatabaseManager()
        self.setWindowTitle(f"Просмотр БД: {'Все персонажи' if self.character_name == 'All' else self.character_name}")
        self.setGeometry(100, 100, 800, 600)

        # Настройка QSqlDatabase с уникальным именем
        self.connection_name = f"db_viewer_connection_{uuid.uuid4().hex}"
        self.db = QSqlDatabase.addDatabase("QSQLITE", self.connection_name)
        self.db.setDatabaseName(self.db_manager.db_path)
        if not self.db.open():
            error_message = f"Не удалось открыть БД для просмотра: {self.db.lastError().text()}"
            logger.error(error_message)
            QMessageBox.critical(self, "Ошибка БД", error_message)
            return

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Применение темного стиля к QTabWidget и QTableView
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background: #3c3c3c;
                color: #888888; /* Уточнен цвет текста вкладок на более темный */
                padding: 8px 15px;
                border: 1px solid #444;
                border-bottom-color: #2b2b2b; /* same as pane color */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
                border-bottom-color: #2b2b2b;
            }
            QTabBar::tab:hover {
                background: #505050;
            }
            QTableView {
                background-color: #2b2b2b;
                color: #f0f0f0;
                gridline-color: #444;
                selection-background-color: #555;
                selection-color: #f0f0f0;
                border: 1px solid #444;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #f0f0f0;
                padding: 4px;
                border: 1px solid #444;
                border-bottom: 1px solid #2b2b2b;
            }
            QTableView QTableCornerButton::section {
                background-color: #3c3c3c;
                border: 1px solid #444;
            }
            QTableView::verticalHeader {
                background-color: #3c3c3c;
            }
            QTableView::verticalHeader::section {
                background-color: #3c3c3c;
                color: #cccccc; /* Уточнен цвет текста вертикальных заголовков на более темный */
                padding: 4px;
                border: 1px solid #444;
            }
            QTableView::item {
                color: #f0f0f0; /* Цвет текста для элементов таблицы */
            }
            QTableView::indicator {
                background-color: #3c3c3c;
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #555;
                color: #cccccc; /* Уточнен цвет текста кнопок на более темный */
                border: 1px solid #666;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
            QDialog {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QTextEdit {
                background-color: #3c3c3c;
                color: #f0f0f0;
                border: 1px solid #444;
            }
            QScrollBar:vertical {
                border: 1px solid #444;
                background: #3c3c3c;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical {
                border: 1px solid #444;
                background: #3c3c3c;
                height: 10px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                border: 1px solid #444;
                background: #3c3c3c;
                height: 10px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: 1px solid #444;
                width: 3px;
                height: 3px;
                background: #f0f0f0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        self._setup_history_tab()
        self._setup_memory_tab()

        self.load_data()

    def _setup_history_tab(self):
        self.history_tab = QWidget()
        self.tabs.addTab(self.history_tab, "История")
        history_layout = QVBoxLayout(self.history_tab)

        self.history_view = QTableView()
        self.history_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.history_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_view.setAlternatingRowColors(False)
        self.history_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        history_layout.addWidget(self.history_view)
        self.history_view.doubleClicked.connect(self._show_content_dialog)

        # Модель для таблицы history
        self.history_model = QSqlTableModel(self.history_view, self.db)  # Передаем соединение
        self.history_model.setTable("history")
        self.history_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.history_view.setModel(self.history_model)  # Устанавливаем модель здесь
        self.history_model.select()

    def _setup_memory_tab(self):
        self.memory_tab = QWidget()
        self.tabs.addTab(self.memory_tab, "Память")
        memory_layout = QVBoxLayout(self.memory_tab)

        self.memory_view = QTableView()
        self.memory_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.memory_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.memory_view.setAlternatingRowColors(False)
        self.memory_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        memory_layout.addWidget(self.memory_view)
        self.memory_view.doubleClicked.connect(self._show_content_dialog)

        # Модель для таблицы memory
        self.memory_model = QSqlTableModel(self.memory_view, self.db)  # Передаем соединение
        self.memory_model.setTable("memory")
        self.memory_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.memory_view.setModel(self.memory_model)  # Устанавливаем модель здесь
        self.memory_model.select()

    def load_data(self):
        """Загружает данные для выбранного персонажа или всех."""
        if self.character_name != "All":
            # Фильтр по character_name
            self.history_model.setFilter(f"character_name = '{self.character_name}'")
            self.memory_model.setFilter(f"character_name = '{self.character_name}'")
        self.history_model.select()
        self.memory_model.select()

        # Настройка колонок (вызываем после select(), чтобы получить метаданные колонок)
        self._setup_columns(self.history_view, self.history_model,
                            {"id": "ID", "role": "Роль", "content": "Содержимое", "timestamp": "Время"})
        self._setup_columns(self.memory_view, self.memory_model,
                            {"id": "ID", "key": "Ключ", "value": "Значение", "timestamp": "Время"})

        # Делегат для форматирования времени
        self.history_view.setItemDelegateForColumn(self.history_model.fieldIndex("timestamp"), DateTimeDelegate(self))
        self.memory_view.setItemDelegateForColumn(self.memory_model.fieldIndex("timestamp"), DateTimeDelegate(self))

    def _setup_columns(self, view: QTableView, model: QSqlTableModel, column_map: Dict[str, str]):
        """Настраивает видимые колонки, их заголовки и ширину."""
        # Скрываем все колонки по умолчанию
        for i in range(model.columnCount()):
            view.hideColumn(i)

        # Устанавливаем заголовки и показываем нужные колонки
        for col_name, header_text in column_map.items():
            col_index = model.fieldIndex(col_name)
            if col_index >= 0:
                model.setHeaderData(col_index, Qt.Orientation.Horizontal, header_text)
                view.showColumn(col_index)
        
        view.resizeColumnsToContents()
        # Убедимся, что колонка 'content' или 'value' растягивается
        if 'content' in column_map:
            content_index = model.fieldIndex('content')
            if content_index >= 0:
                view.horizontalHeader().setSectionResizeMode(content_index, QHeaderView.ResizeMode.Stretch)
        elif 'value' in column_map:
            value_index = model.fieldIndex('value')
            if value_index >= 0:
                view.horizontalHeader().setSectionResizeMode(value_index, QHeaderView.ResizeMode.Stretch)
        
        # Сортировка по timestamp, если колонка существует
        timestamp_index = model.fieldIndex('timestamp')
        if timestamp_index >= 0:
            view.sortByColumn(timestamp_index, Qt.SortOrder.DescendingOrder)

    def closeEvent(self, event):
        """Закрытие окна."""
        if self.db and self.db.isOpen():
            self.db.close()
            # Удаляем соединение из пула QSqlDatabase
            QSqlDatabase.removeDatabase(self.connection_name)
        logger.info(f"Окно просмотра БД закрыто для {self.character_name}. Соединение {self.connection_name} удалено.")
        event.accept()

    def _show_content_dialog(self, index):
        """Показывает содержимое выбранной ячейки в отдельном диалоговом окне."""
        model = index.model()
        column_name = model.headerData(index.column(), Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        cell_content = model.data(index, Qt.ItemDataRole.DisplayRole)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Содержимое: {column_name}")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText(str(cell_content))
        layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.exec()


class DateTimeDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        # Извлекаем значение из QVariant, если оно есть
        if isinstance(value, QVariant):
            value = value.value()

        # Проверяем, является ли значение QDateTime
        if isinstance(value, QDateTime):
            return value.toString("yyyy-MM-dd HH:mm:ss")
        
        # Если значение является строкой, пытаемся преобразовать ее в QDateTime
        if isinstance(value, str):
            try:
                # Попытка преобразовать строку в QDateTime, учитывая ISO 8601 формат
                dt = QDateTime.fromString(value, Qt.DateFormat.ISODate)
                if dt.isValid():
                    return dt.toString("yyyy-MM-dd HH:mm:ss")
            except Exception:
                pass # Если преобразование не удалось, продолжаем как обычный текст
        
        # Для всех остальных случаев используем стандартное отображение
        return super().displayText(value, locale)

    def setModelData(self, editor, model, index):
        # Этот метод нужен, если бы мы хотели редактировать данные,
        # но для read-only просмотра он может быть пустым или вызывать базовую реализацию.
        # В данном случае, мы не разрешаем редактирование, поэтому можно оставить так.
        super().setModelData(editor, model, index)

    def createEditor(self, parent, option, index):
        # Для read-only просмотра нет необходимости создавать редактор
        return super().createEditor(parent, option, index)

    def updateEditorGeometry(self, editor, option, index):
        # Для read-only просмотра нет необходимости обновлять геометрию редактора
        super().updateEditorGeometry(editor, option, index)


def open_database_viewer(gui, character_name: str = None):
    """Открывает окно просмотра БД для указанного персонажа."""
    if character_name is None:
        # Получаем текущего персонажа
        from core.events import get_event_bus
        event_bus = get_event_bus()
        current_char_data = event_bus.emit_and_wait(Events.Model.GET_CURRENT_CHARACTER, timeout=1.0)
        character_name = current_char_data[0].get('char_id') if current_char_data and current_char_data[0] else None

    if not character_name:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(gui, "Внимание", "Персонаж не выбран.")
        return

    viewer = DatabaseViewer(character_name, gui)
    viewer.show()