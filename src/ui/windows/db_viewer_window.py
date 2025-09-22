from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, 
                             QTableView, QHeaderView, QPushButton, QHBoxLayout, QLabel, QLineEdit)
from PyQt6.QtCore import Qt, QAbstractTableModel, QVariant
from PyQt6.QtGui import QColor
from PySide6.QtWidgets import QComboBox

from managers.database_manager import DatabaseManager
from main_logger import logger
from utils import getTranslationVariant as _

class TableModel(QAbstractTableModel):
    def __init__(self, data, header):
        super().__init__()
        self._data = data
        self._header = header

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data[index.row()][index.column()])
        if role == Qt.ItemDataRole.BackgroundRole:
            if index.row() % 2 == 0:
                return QColor(Qt.GlobalColor.darkGray).lighter(110)
            else:
                return QColor(Qt.GlobalColor.darkGray).lighter(100)
        return QVariant()

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._header)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._header[section]
        return QVariant()

class DbViewerWindow(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle(_("Просмотр базы данных", "Database Viewer"))
        self.setGeometry(100, 100, 1000, 600)

        self.main_layout = QVBoxLayout(self)

        self.character_selector_layout = QHBoxLayout()
        self.main_layout.addLayout(self.character_selector_layout)

        self.character_label = QLabel(_("Персонаж:", "Character:"))
        self.character_selector_layout.addWidget(self.character_label)

        self.character_combobox = QComboBox()
        self.character_combobox.setMinimumWidth(200)
        self.character_selector_layout.addWidget(self.character_combobox)
        self.character_combobox.currentTextChanged.connect(self._load_data_for_selected_character)

        self.refresh_button = QPushButton(_("Обновить", "Refresh"))
        self.refresh_button.clicked.connect(self._load_data_for_selected_character)
        self.character_selector_layout.addWidget(self.refresh_button)
        self.character_selector_layout.addStretch()

        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self.history_tab = QWidget()
        self.history_layout = QVBoxLayout(self.history_tab)
        self.history_table = QTableView()
        self.history_layout.addWidget(self.history_table)
        self.tab_widget.addTab(self.history_tab, _("История", "History"))

        self.memory_tab = QWidget()
        self.memory_layout = QVBoxLayout(self.memory_tab)
        self.memory_table = QTableView()
        self.memory_layout.addWidget(self.memory_table)
        self.tab_widget.addTab(self.memory_tab, _("Память", "Memory"))

        self._populate_character_combobox()
        self._load_data_for_selected_character()

    def _populate_character_combobox(self):
        """Заполняет комбобокс именами персонажей из БД."""
        self.character_combobox.clear()
        character_names = self.db_manager.get_all_character_names()
        if character_names:
            self.character_combobox.addItems(sorted(character_names))
        else:
            self.character_combobox.addItem(_("Нет персонажей", "No characters"))
        
        # Устанавливаем текущий персонаж, если он есть в настройках
        # TODO: Получить текущего персонажа из MainController через EventBus
        # current_char = self.event_bus.emit_and_wait(Events.Model.GET_CURRENT_CHARACTER)
        # if current_char and current_char[0] and current_char[0].get('name') in character_names:
        #     self.character_combobox.setCurrentText(current_char[0].get('name'))


    def _load_data_for_selected_character(self):
        """Загружает и отображает данные для выбранного персонажа."""
        character_name = self.character_combobox.currentText()
        if character_name == _("Нет персонажей", "No characters") or not character_name:
            self._clear_tables()
            return

        # Загрузка истории
        history_data_raw = self.db_manager.get_all_history_messages(character_name)
        history_header = [_("ID", "ID"), _("Роль", "Role"), _("Сообщение", "Message"), _("Время", "Timestamp")]
        history_data = []
        for row in history_data_raw:
            history_data.append([row['id'], row['role'], row['content'], row['timestamp']])
        
        history_model = TableModel(history_data, history_header)
        self.history_table.setModel(history_model)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setStretchLastSection(True)

        # Загрузка памяти
        memory_data_raw = self.db_manager.get_all_memory_facts_list(character_name)
        memory_header = [_("ID", "ID"), _("Ключ", "Key"), _("Значение", "Value"), _("Время", "Timestamp")]
        memory_data = []
        for row in memory_data_raw:
            memory_data.append([row['id'], row['key'], row['value'], row['timestamp']])

        memory_model = TableModel(memory_data, memory_header)
        self.memory_table.setModel(memory_model)
        self.memory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.memory_table.horizontalHeader().setStretchLastSection(True)

    def _clear_tables(self):
        """Очищает таблицы."""
        self.history_table.setModel(TableModel([], []))
        self.memory_table.setModel(TableModel([], []))
