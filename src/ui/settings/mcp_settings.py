"""Generic MCP server editor for the launcher settings page.

The editor intentionally persists only MCP's portable configuration format.
It does not know about Discord, Codex, or any other server implementation.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from controllers.gui.async_runner import run_async
from core.services import services
from managers.mcp import MCPConfigStore, MCPServerConfig, MCPTransportKind
from services.contracts import MCPService
from ui.gui_templates import create_section_header
from ui.settings.settings_access import get_setting, set_setting
from utils import getTranslationVariant as _


def _json_mapping(editor: QPlainTextEdit, label: str) -> dict[str, str]:
    text = editor.toPlainText().strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(_("{}: некорректный JSON.", "{}: invalid JSON.").format(label)) from exc
    if not isinstance(value, Mapping):
        raise ValueError(_("{} должен быть объектом JSON.", "{} must be a JSON object.").format(label))
    return {str(key): str(item) for key, item in value.items()}


def _set_json_mapping(editor: QPlainTextEdit, value: Mapping[str, Any]) -> None:
    editor.setPlainText(json.dumps(dict(value or {}), ensure_ascii=False, indent=2))


def _lines(editor: QPlainTextEdit, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    result = tuple(line.strip() for line in editor.toPlainText().splitlines() if line.strip())
    return result or default


class MCPServerDialog(QDialog):
    """Create or edit one transport-neutral MCP server declaration."""

    def __init__(
        self,
        store: MCPConfigStore,
        *,
        config: MCPServerConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._original_id = config.server_id if config is not None else ""
        self.setWindowTitle(_("Настройка MCP-сервера", "MCP server settings"))
        self.setMinimumWidth(700)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        notice = QLabel(
            _(
                "MCP-сервер запускается только локально или подключается по указанному URL. "
                "Для токенов используйте ${env:ИМЯ_ПЕРЕМЕННОЙ}, а не храните их в файле настроек.",
                "An MCP server runs locally or connects through the specified URL. "
                "Use ${env:VARIABLE_NAME} for tokens instead of storing them in the settings file.",
            )
        )
        notice.setObjectName("SeparatorLabel")
        notice.setWordWrap(True)
        root.addWidget(notice)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(8)

        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.enabled_check = QCheckBox(_("Включён", "Enabled"))
        self.transport_combo = QComboBox()
        self.transport_combo.addItem("stdio", MCPTransportKind.STDIO.value)
        self.transport_combo.addItem("Streamable HTTP", MCPTransportKind.STREAMABLE_HTTP.value)
        self.command_edit = QLineEdit()
        self.args_edit = QPlainTextEdit()
        self.args_edit.setPlaceholderText(_("Один аргумент в строке", "One argument per line"))
        self.args_edit.setFixedHeight(72)
        self.cwd_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.env_edit = QPlainTextEdit()
        self.env_edit.setPlaceholderText('{\n  "TOKEN": "${env:MY_TOKEN}"\n}')
        self.env_edit.setFixedHeight(92)
        self.headers_edit = QPlainTextEdit()
        self.headers_edit.setPlaceholderText('{\n  "Authorization": "Bearer ${env:MY_TOKEN}"\n}')
        self.headers_edit.setFixedHeight(92)
        self.profile_edit = QLineEdit()
        self.projects_edit = QPlainTextEdit()
        self.projects_edit.setPlaceholderText('{\n  "project-id": "C:\\\\Development\\\\Project"\n}')
        self.projects_edit.setFixedHeight(72)
        self.auto_connect_check = QCheckBox(_("Подключаться при запуске", "Connect on startup"))
        self.expose_tools_check = QCheckBox(_("Показывать инструменты Мите", "Expose tools to Mita"))
        self.allowed_tools_edit = QPlainTextEdit("*")
        self.allowed_tools_edit.setPlaceholderText(_("Один шаблон в строке; * = все", "One pattern per line; * = all"))
        self.allowed_tools_edit.setFixedHeight(62)
        self.denied_tools_edit = QPlainTextEdit()
        self.denied_tools_edit.setPlaceholderText(_("Один шаблон в строке", "One pattern per line"))
        self.denied_tools_edit.setFixedHeight(62)
        self.connect_timeout_spin = QSpinBox()
        self.connect_timeout_spin.setRange(1, 600)
        self.connect_timeout_spin.setSuffix(_(" с", " s"))
        self.call_timeout_spin = QSpinBox()
        self.call_timeout_spin.setRange(1, 3600)
        self.call_timeout_spin.setSuffix(_(" с", " s"))

        form.addRow(_("ID", "ID"), self.id_edit)
        form.addRow(_("Название", "Name"), self.name_edit)
        form.addRow("", self.enabled_check)
        form.addRow(_("Транспорт", "Transport"), self.transport_combo)
        form.addRow(_("Команда", "Command"), self.command_edit)
        form.addRow(_("Аргументы", "Arguments"), self.args_edit)
        form.addRow(_("Рабочая папка", "Working directory"), self.cwd_edit)
        form.addRow(_("URL", "URL"), self.url_edit)
        form.addRow(_("Переменные среды (JSON)", "Environment (JSON)"), self.env_edit)
        form.addRow(_("Заголовки HTTP (JSON)", "HTTP headers (JSON)"), self.headers_edit)
        form.addRow(_("Профиль", "Profile"), self.profile_edit)
        form.addRow(_("Проекты (JSON)", "Projects (JSON)"), self.projects_edit)
        form.addRow("", self.auto_connect_check)
        form.addRow("", self.expose_tools_check)
        form.addRow(_("Разрешённые инструменты", "Allowed tools"), self.allowed_tools_edit)
        form.addRow(_("Запрещённые инструменты", "Denied tools"), self.denied_tools_edit)
        form.addRow(_("Тайм-аут подключения", "Connect timeout"), self.connect_timeout_spin)
        form.addRow(_("Тайм-аут вызова", "Call timeout"), self.call_timeout_spin)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.transport_combo.currentIndexChanged.connect(self._sync_transport_fields)
        self._load(config)
        self._sync_transport_fields()

    def _load(self, config: MCPServerConfig | None) -> None:
        if config is None:
            self.enabled_check.setChecked(True)
            self.auto_connect_check.setChecked(True)
            self.connect_timeout_spin.setValue(15)
            self.call_timeout_spin.setValue(120)
            return
        self.id_edit.setText(config.server_id)
        self.name_edit.setText(config.name)
        self.enabled_check.setChecked(config.enabled)
        index = self.transport_combo.findData(MCPTransportKind(config.transport).value)
        self.transport_combo.setCurrentIndex(max(0, index))
        self.command_edit.setText(config.command or "")
        self.args_edit.setPlainText("\n".join(config.args))
        self.cwd_edit.setText(config.cwd or "")
        self.url_edit.setText(config.url or "")
        _set_json_mapping(self.env_edit, config.env)
        _set_json_mapping(self.headers_edit, config.headers)
        self.profile_edit.setText(config.profile or "")
        _set_json_mapping(self.projects_edit, config.projects)
        self.auto_connect_check.setChecked(config.auto_connect)
        self.expose_tools_check.setChecked(config.expose_tools)
        self.allowed_tools_edit.setPlainText("\n".join(config.allowed_tools))
        self.denied_tools_edit.setPlainText("\n".join(config.denied_tools))
        self.connect_timeout_spin.setValue(round(config.connect_timeout_seconds))
        self.call_timeout_spin.setValue(round(config.call_timeout_seconds))

    def _sync_transport_fields(self) -> None:
        is_stdio = self.transport_combo.currentData() == MCPTransportKind.STDIO.value
        for widget in (self.command_edit, self.args_edit, self.cwd_edit, self.env_edit):
            widget.setEnabled(is_stdio)
        for widget in (self.url_edit, self.headers_edit):
            widget.setEnabled(not is_stdio)

    def config(self) -> MCPServerConfig:
        transport = MCPTransportKind(str(self.transport_combo.currentData() or "stdio"))
        is_stdio = transport is MCPTransportKind.STDIO
        return MCPServerConfig(
            server_id=self.id_edit.text().strip(),
            name=self.name_edit.text().strip(),
            enabled=self.enabled_check.isChecked(),
            transport=transport,
            command=self.command_edit.text().strip() or None,
            args=_lines(self.args_edit),
            cwd=self.cwd_edit.text().strip() or None,
            env=_json_mapping(self.env_edit, _("Переменные среды", "Environment")) if is_stdio else {},
            url=self.url_edit.text().strip() or None,
            headers=_json_mapping(self.headers_edit, _("Заголовки HTTP", "HTTP headers")) if not is_stdio else {},
            profile=self.profile_edit.text().strip() or None,
            projects=_json_mapping(self.projects_edit, _("Проекты", "Projects")),
            auto_connect=self.auto_connect_check.isChecked(),
            connect_timeout_seconds=float(self.connect_timeout_spin.value()),
            call_timeout_seconds=float(self.call_timeout_spin.value()),
            expose_tools=self.expose_tools_check.isChecked(),
            allowed_tools=_lines(self.allowed_tools_edit, default=("*",)),
            denied_tools=_lines(self.denied_tools_edit),
        )

    def _save(self) -> None:
        try:
            config = self.config()
            config.validate()
            configs = self._store.load()
            if self._original_id and config.server_id != self._original_id:
                configs = [item for item in configs if item.server_id != self._original_id]
            if any(item.server_id == config.server_id for item in configs):
                configs = [item for item in configs if item.server_id != config.server_id]
            configs.append(config)
            self._store.save(configs)
        except Exception as exc:
            QMessageBox.warning(
                self,
                _("Не удалось сохранить MCP-сервер", "Could not save MCP server"),
                str(exc),
            )
            return
        self.accept()


class MCPSettingsPanel(QFrame):
    def __init__(self, gui: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gui = gui
        self._store = MCPConfigStore()
        self._configs: dict[str, MCPServerConfig] = {}
        self.setObjectName("SettingsCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        intro = QLabel(
            _(
                "Добавляйте любые совместимые MCP-серверы. Для stdio укажите команду, "
                "для удалённого сервера — Streamable HTTP URL. Фильтры инструментов "
                "применяются до передачи функций модели.",
                "Add any compatible MCP server. Specify a command for stdio or a "
                "Streamable HTTP URL for a remote server. Tool filters are applied "
                "before functions reach the model.",
            )
        )
        intro.setObjectName("SeparatorLabel")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.native_tools_check = QCheckBox(
            _("Разрешить Мите вызывать инструменты MCP", "Allow Mita to call MCP tools")
        )
        self.native_tools_check.setChecked(bool(get_setting(gui, "MCP_NATIVE_TOOLS_ON", False)))
        self.native_tools_check.toggled.connect(
            lambda enabled: set_setting(self._gui, "MCP_NATIVE_TOOLS_ON", bool(enabled))
        )
        root.addWidget(self.native_tools_check)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.server_list = QListWidget()
        self.server_list.setMinimumWidth(230)
        self.server_list.currentItemChanged.connect(lambda *_args: self._sync_buttons())
        splitter.addWidget(self.server_list)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(8, 0, 0, 0)
        details_layout.setSpacing(8)
        self.details_label = QLabel()
        self.details_label.setObjectName("SeparatorLabel")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)

        action_row = QHBoxLayout()
        self.add_button = QPushButton(_("Добавить", "Add"))
        self.edit_button = QPushButton(_("Изменить", "Edit"))
        self.remove_button = QPushButton(_("Удалить", "Remove"))
        self.test_button = QPushButton(_("Проверить соединение", "Test connection"))
        self.reload_button = QPushButton(_("Обновить список", "Reload list"))
        for button in (
            self.add_button,
            self.edit_button,
            self.remove_button,
            self.test_button,
            self.reload_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        details_layout.addLayout(action_row)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Subtle")
        self.status_label.setWordWrap(True)
        details_layout.addWidget(self.status_label)
        details_layout.addStretch(1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter)

        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.remove_button.clicked.connect(self._remove)
        self.test_button.clicked.connect(self._test_selected)
        self.reload_button.clicked.connect(self._reload)
        self._reload()

    def _selected_id(self) -> str:
        item = self.server_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def _selected_config(self) -> MCPServerConfig | None:
        return self._configs.get(self._selected_id())

    def _reload(self) -> None:
        selected_id = self._selected_id()
        self._configs = {config.server_id: config for config in self._store.load()}
        self.server_list.clear()
        selected_item: QListWidgetItem | None = None
        for config in self._configs.values():
            state = _("включён", "enabled") if config.enabled else _("выключен", "disabled")
            transport = MCPTransportKind(config.transport).value
            item = QListWidgetItem(f"{config.name}\n{config.server_id} · {transport} · {state}")
            item.setData(Qt.ItemDataRole.UserRole, config.server_id)
            self.server_list.addItem(item)
            if config.server_id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.server_list.setCurrentItem(selected_item)
        elif self.server_list.count():
            self.server_list.setCurrentRow(0)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        config = self._selected_config()
        selected = config is not None
        self.edit_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)
        self.test_button.setEnabled(selected and bool(config.enabled))
        if config is None:
            self.details_label.setText(_("Выберите сервер или добавьте новый.", "Select a server or add a new one."))
            return
        self.details_label.setText(
            _(
                "{name}\nТранспорт: {transport}\nИнструменты: {tools}\nАвтоподключение: {auto}",
                "{name}\nTransport: {transport}\nTools: {tools}\nAuto-connect: {auto}",
            ).format(
                name=config.name,
                transport=MCPTransportKind(config.transport).value,
                tools=_('включены', 'exposed') if config.expose_tools else _('скрыты', 'hidden'),
                auto=_('да', 'yes') if config.auto_connect else _('нет', 'no'),
            )
        )

    def _add(self) -> None:
        dialog = MCPServerDialog(self._store, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload()
            self.status_label.setText(
                _("Конфигурация сохранена. Перезапустите Миту, чтобы новые инструменты стали доступны модели.",
                  "Configuration saved. Restart Mita to make new tools available to the model.")
            )

    def _edit(self) -> None:
        config = self._selected_config()
        if config is None:
            return
        dialog = MCPServerDialog(self._store, config=config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload()
            self.status_label.setText(
                _("Конфигурация сохранена. Перезапустите Миту, чтобы изменения инструментов вступили в силу.",
                  "Configuration saved. Restart Mita for tool changes to take effect.")
            )

    def _remove(self) -> None:
        config = self._selected_config()
        if config is None:
            return
        answer = QMessageBox.question(
            self,
            _("Удалить MCP-сервер", "Remove MCP server"),
            _("Удалить конфигурацию «{}»?", "Remove configuration for “{}”?").format(config.name),
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        self._store.delete(config.server_id)
        self._reload()
        self.status_label.setText(
            _("Конфигурация удалена. Перезапустите Миту, если сервер был активен.",
              "Configuration removed. Restart Mita if the server was active.")
        )

    def _test_selected(self) -> None:
        config = self._selected_config()
        if config is None:
            return
        self.test_button.setEnabled(False)
        self.status_label.setText(_("Подключение и получение списка инструментов...", "Connecting and listing tools..."))

        def worker() -> int:
            manager = services().get_optional(MCPService)
            if manager is None:
                raise RuntimeError(
                    _(
                        "MCP-движок ещё не готов. Сохраните конфигурацию и перезапустите Миту.",
                        "The MCP runtime is not ready. Save the configuration and restart Mita.",
                    )
                )
            refresher = getattr(manager, "refresh_tools", None)
            if not callable(refresher):
                raise RuntimeError(_("Проверка недоступна в этом запуске.", "Testing is unavailable in this run."))
            return len(tuple(refresher(config.server_id)))

        def success(count: int) -> None:
            self._sync_buttons()
            self.status_label.setText(
                _(
                    "Подключено: найдено инструментов — {}. Перезапустите Миту, чтобы модель увидела их.",
                    "Connected: {} tool(s) found. Restart Mita so the model can use them.",
                ).format(count)
            )

        def failed(error: Exception) -> None:
            self._sync_buttons()
            self.status_label.setText(_("Ошибка подключения: {}", "Connection error: {}").format(error))

        run_async(self, worker, success, failed, name=f"mcp-test:{config.server_id}")


def setup_mcp_settings_controls(gui: Any, parent: QVBoxLayout) -> None:
    create_section_header(parent, _("Подключения MCP", "MCP connections"))
    parent.addWidget(MCPSettingsPanel(gui, parent.parentWidget()))


__all__ = ["MCPServerDialog", "MCPSettingsPanel", "setup_mcp_settings_controls"]
