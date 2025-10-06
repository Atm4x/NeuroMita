from PyQt6.QtWidgets import QMainWindow, QTabWidget, QTableView, QVBoxLayout, QWidget, QHeaderView
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtCore import Qt
from managers.database_manager import DatabaseManager
from main_logger import logger


class DatabaseViewer(QMainWindow):
    """Окно просмотра базы данных (только чтение)."""

    def __init__(self, character_name: str = None, parent=None):
        super().__init__(parent)
        self.character_name = character_name or "All"  # По умолчанию все персонажи, или указанный
        self.db_manager = DatabaseManager()
        self.setWindowTitle(f"Просмотр БД: {'Все персонажи' if self.character_name == 'All' else self.character_name}")
        self.setGeometry(100, 100, 800, 600)

        # Настройка QSqlDatabase
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(self.db_manager.db_path)
        if not self.db.open():
            logger.error(f"Не удалось открыть БД для просмотра: {self.db.lastError().text()}")
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
        self.history_model = QSqlTableModel(self.history_view, self.db)
        self.history_model.setTable("history")
        self.history_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
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
        self.memory_model = QSqlTableModel(self.memory_view, self.db)
        self.memory_model.setTable("memory")
        self.memory_model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.memory_model.select()

    def load_data(self):
        """Загружает данные для выбранного персонажа или всех."""
        if self.character_name != "All":
            # Фильтр по character_name
            self.history_model.setFilter(f"character_name = '{self.character_name}'")
            self.memory_model.setFilter(f"character_name = '{self.character_name}'")
        self.history_model.select()
        self.memory_model.select()

        # Настройка колонок
        self._setup_columns(self.history_view, self.history_model, ["id", "role", "content", "timestamp"])
        self._setup_columns(self.memory_view, self.memory_model, ["id", "key", "value", "timestamp"])

    def _setup_columns(self, view: QTableView, model: QSqlTableModel, visible_columns: list):
        """Настраивает видимые колонки и их ширину."""
        model.setHeaderData(0, Qt.Orientation.Horizontal, "ID")
        model.setHeaderData(1, Qt.Orientation.Horizontal, "Роль/Ключ")
        model.setHeaderData(2, Qt.Orientation.Horizontal, "Содержимое/Значение")
        model.setHeaderData(3, Qt.Orientation.Horizontal, "Время")

        # Скрываем faiss_vector и другие
        for i in range(model.columnCount()):
            if i not in [0, 1, 2, 3]:  # Показываем только ID, role/key, content/value, timestamp
                view.hideColumn(i)

        view.setModel(model)
        view.resizeColumnsToContents()
        view.sortByColumn(3, Qt.SortOrder.DescendingOrder)  # Сортировка по времени DESC

    def closeEvent(self, event):
        """Закрытие окна."""
        if self.db and self.db.isOpen():
            self.db.close()
        logger.info(f"Окно просмотра БД закрыто для {self.character_name}")
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