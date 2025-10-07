from typing import Dict

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QTableView, QVBoxLayout, QWidget, QHeaderView, QMessageBox
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtCore import Qt

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
        self.history_view.setAlternatingRowColors(True)
        self.history_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        history_layout.addWidget(self.history_view)

        # Модель для таблицы history
        self.history_model = QSqlTableModel(self.history_view, self.db) # Передаем соединение
        self.history_model.setTable("history")
        self.history_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.history_view.setModel(self.history_model) # Устанавливаем модель здесь
        self.history_model.select()

    def _setup_memory_tab(self):
        self.memory_tab = QWidget()
        self.tabs.addTab(self.memory_tab, "Память")
        memory_layout = QVBoxLayout(self.memory_tab)

        self.memory_view = QTableView()
        self.memory_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.memory_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.memory_view.setAlternatingRowColors(True)
        self.memory_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        memory_layout.addWidget(self.memory_view)

        # Модель для таблицы memory
        self.memory_model = QSqlTableModel(self.memory_view, self.db) # Передаем соединение
        self.memory_model.setTable("memory")
        self.memory_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.memory_view.setModel(self.memory_model) # Устанавливаем модель здесь
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