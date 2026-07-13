"""SessionManagerDialog — управление сейвами (сессиями) и их чекпоинтами из песочницы.

Ходит напрямую в SessionService (как _SessionSelector). Мутирующие операции
(переключение сейва, копирование, удаление, чекпоинты, откат) блокируются, когда
подключена игра: тогда сейвами/чекпоинтами управляет клиент Unity, а Python-БД
меняется только по его командам — иначе БД и папка сейва Unity разойдутся.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils import _


class SessionManagerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Сейвы и чекпоинты", "Saves & checkpoints"))
        self.setMinimumSize(720, 460)
        self.setObjectName("SessionManagerDialog")

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # services
    # ------------------------------------------------------------------
    def _service(self):
        try:
            from core.services import use
            from services.contracts import SessionService
            return use(SessionService)
        except Exception:
            return None

    def _game_connected(self) -> bool:
        try:
            from core.services import use
            from services.contracts import GameLinkService
            return bool(use(GameLinkService).is_connected())
        except Exception:
            return False

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setObjectName("SessionManagerHint")
        root.addWidget(self._hint)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        root.addLayout(columns, 1)

        # --- Saves column ---
        saves_box = QVBoxLayout()
        saves_box.setSpacing(6)
        saves_title = QLabel(_("Сейвы", "Saves"))
        saves_title.setStyleSheet("font-weight: 600;")
        saves_box.addWidget(saves_title)

        self._sessions_list = QListWidget()
        self._sessions_list.currentItemChanged.connect(lambda *_: self._on_session_selected())
        saves_box.addWidget(self._sessions_list, 1)

        self._btn_switch = QPushButton(_("Открыть", "Switch to"))
        self._btn_copy = QPushButton(_("Копия / ветка", "Copy / branch"))
        self._btn_rename = QPushButton(_("Переименовать", "Rename"))
        self._btn_clear = QPushButton(_("Очистить", "Clear"))
        self._btn_delete = QPushButton(_("Удалить", "Delete"))
        self._btn_switch.clicked.connect(self._do_switch)
        self._btn_copy.clicked.connect(self._do_copy)
        self._btn_rename.clicked.connect(self._do_rename)
        self._btn_clear.clicked.connect(self._do_clear)
        self._btn_delete.clicked.connect(self._do_delete)
        for b in (self._btn_switch, self._btn_copy, self._btn_rename, self._btn_clear, self._btn_delete):
            saves_box.addWidget(b)

        columns.addLayout(saves_box, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        columns.addWidget(sep)

        # --- Checkpoints column ---
        ck_box = QVBoxLayout()
        ck_box.setSpacing(6)
        self._ck_title = QLabel(_("Чекпоинты", "Checkpoints"))
        self._ck_title.setStyleSheet("font-weight: 600;")
        ck_box.addWidget(self._ck_title)

        self._checkpoints_list = QListWidget()
        self._checkpoints_list.currentItemChanged.connect(lambda *_: self._update_buttons())
        ck_box.addWidget(self._checkpoints_list, 1)

        self._btn_ck_create = QPushButton(_("Создать чекпоинт", "Create checkpoint"))
        self._btn_ck_rollback = QPushButton(_("Откатить к чекпоинту", "Roll back to checkpoint"))
        self._btn_ck_delete = QPushButton(_("Удалить чекпоинт", "Delete checkpoint"))
        self._btn_ck_create.clicked.connect(self._do_create_checkpoint)
        self._btn_ck_rollback.clicked.connect(self._do_rollback)
        self._btn_ck_delete.clicked.connect(self._do_delete_checkpoint)
        for b in (self._btn_ck_create, self._btn_ck_rollback, self._btn_ck_delete):
            ck_box.addWidget(b)

        columns.addLayout(ck_box, 1)

        # --- footer ---
        footer = QHBoxLayout()
        refresh = QPushButton(_("Обновить", "Refresh"))
        refresh.clicked.connect(self.refresh)
        close = QPushButton(_("Закрыть", "Close"))
        close.clicked.connect(self.accept)
        footer.addWidget(refresh)
        footer.addStretch(1)
        footer.addWidget(close)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def _selected_session_id(self) -> Optional[str]:
        item = self._sessions_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _selected_checkpoint_id(self) -> Optional[str]:
        item = self._checkpoints_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole) or "")

    def refresh(self) -> None:
        svc = self._service()
        if svc is None:
            self._hint.setText(_("SessionService недоступен.", "SessionService is unavailable."))
            for b in self._all_buttons():
                b.setEnabled(False)
            return

        try:
            sessions: List[Dict[str, Any]] = svc.list_sessions()
            current = svc.current()
        except Exception as e:
            self._hint.setText(_("Не удалось получить список сейвов: ", "Failed to list saves: ") + str(e))
            return

        prev = self._selected_session_id()
        self._sessions_list.blockSignals(True)
        self._sessions_list.clear()
        select_row = 0
        for i, s in enumerate(sessions):
            sid = str(s.get("session_id", ""))
            is_active = bool(s.get("active"))
            label = sid if sid != "default" else _("Основной (default)", "Main (default)")
            counts = _("И:{h} П:{m} В:{v}", "H:{h} M:{m} V:{v}").format(
                h=s.get("history", 0), m=s.get("memories", 0), v=s.get("variables", 0)
            )
            text = ("● " if is_active else "   ") + f"{label}    {counts}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self._sessions_list.addItem(item)
            if (prev and sid == prev) or (not prev and sid == current):
                select_row = i
        self._sessions_list.blockSignals(False)
        if self._sessions_list.count():
            self._sessions_list.setCurrentRow(select_row)

        self._on_session_selected()

    def _on_session_selected(self) -> None:
        svc = self._service()
        sid = self._selected_session_id()
        self._checkpoints_list.clear()
        if svc is not None and sid:
            self._ck_title.setText(_("Чекпоинты — {s}", "Checkpoints — {s}").format(s=sid))
            try:
                for ck in svc.list_checkpoints(sid):
                    cid = str(ck.get("checkpoint_id", ""))
                    label = ck.get("label") or ""
                    created = str(ck.get("created_at", ""))[:19].replace("T", " ")
                    tag = _("авто", "auto") if ck.get("auto") else _("ручной", "manual")
                    title = label if label else _("(без метки)", "(no label)")
                    item = QListWidgetItem(f"{title}   [{tag}]   {created}")
                    item.setData(Qt.ItemDataRole.UserRole, cid)
                    self._checkpoints_list.addItem(item)
            except Exception:
                pass
        self._update_buttons()

    # ------------------------------------------------------------------
    # buttons enable/disable
    # ------------------------------------------------------------------
    def _all_buttons(self) -> List[QPushButton]:
        return [
            self._btn_switch, self._btn_copy, self._btn_rename, self._btn_clear, self._btn_delete,
            self._btn_ck_create, self._btn_ck_rollback, self._btn_ck_delete,
        ]

    def _update_buttons(self) -> None:
        connected = self._game_connected()
        if connected:
            self._hint.setText(_(
                "⚠ Игра подключена — управление сейвами и чекпоинтами недоступно, "
                "чтобы БД и папка сейва Unity не разошлись. Управляйте из игры. Списки доступны для просмотра.",
                "⚠ The game is connected — save/checkpoint management is disabled to keep the DB "
                "and Unity's save folder in sync. Manage them from the game. Lists are view-only.",
            ))
        else:
            try:
                current = self._service().current() if self._service() else "?"
            except Exception:
                current = "?"
            self._hint.setText(_("Активный сейв: ", "Active save: ") + str(current))

        has_session = bool(self._selected_session_id())
        has_checkpoint = bool(self._selected_checkpoint_id())
        enabled = (not connected)

        self._btn_switch.setEnabled(enabled and has_session)
        self._btn_copy.setEnabled(enabled and has_session)
        self._btn_rename.setEnabled(enabled and has_session)
        self._btn_clear.setEnabled(enabled and has_session)
        self._btn_delete.setEnabled(enabled and has_session)
        self._btn_ck_create.setEnabled(enabled and has_session)
        self._btn_ck_rollback.setEnabled(enabled and has_checkpoint)
        self._btn_ck_delete.setEnabled(enabled and has_checkpoint)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _guard(self):
        """Возвращает сервис, если операция разрешена (игра не подключена), иначе None."""
        if self._game_connected():
            QMessageBox.information(
                self,
                _("Игра подключена", "Game connected"),
                _("Управление недоступно, пока игра запущена.", "Management is disabled while the game is running."),
            )
            return None
        return self._service()

    def _do_switch(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        try:
            svc.switch(sid)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_copy(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        suggestion = f"{sid}-copy"
        dst, ok = QInputDialog.getText(
            self, _("Копия сейва", "Copy save"),
            _("Идентификатор нового сейва:", "New save id:"), text=suggestion,
        )
        if not ok or not dst.strip():
            return
        try:
            if svc.copy(sid, dst.strip(), overwrite=False):
                svc.switch(dst.strip())
            else:
                QMessageBox.warning(self, _("Ошибка", "Error"),
                                    _("Не удалось скопировать (целевой сейв не пуст?).",
                                      "Copy failed (target save not empty?)."))
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_rename(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        if sid == "default":
            QMessageBox.information(self, _("Нельзя", "Not allowed"),
                                    _("Основной сейв переименовать нельзя.", "The main save cannot be renamed."))
            return
        new, ok = QInputDialog.getText(self, _("Переименовать сейв", "Rename save"),
                                       _("Новое имя:", "New id:"), text=sid)
        if not ok or not new.strip() or new.strip() == sid:
            return
        try:
            if not svc.rename(sid, new.strip()):
                QMessageBox.warning(self, _("Ошибка", "Error"),
                                    _("Не удалось переименовать (имя занято?).", "Rename failed (id taken?)."))
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_clear(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        if QMessageBox.question(
            self, _("Очистить сейв", "Clear save"),
            _("Стереть всю историю/память/переменные сейва «{s}»? Сам сейв останется.",
              "Wipe all history/memory/variables of save '{s}'? The save itself stays.").format(s=sid),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.clear(sid)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_delete(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        try:
            if sid == svc.current():
                QMessageBox.information(self, _("Нельзя", "Not allowed"),
                                        _("Нельзя удалить активный сейв — сначала откройте другой.",
                                          "Can't delete the active save — switch to another first."))
                return
        except Exception:
            pass
        if QMessageBox.question(
            self, _("Удалить сейв", "Delete save"),
            _("Удалить сейв «{s}» со всеми чекпоинтами безвозвратно?",
              "Delete save '{s}' and all its checkpoints permanently?").format(s=sid),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete(sid)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_create_checkpoint(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        label, ok = QInputDialog.getText(self, _("Создать чекпоинт", "Create checkpoint"),
                                         _("Метка (необязательно):", "Label (optional):"))
        if not ok:
            return
        try:
            cid = svc.create_checkpoint(sid, label=label.strip())
            if not cid:
                QMessageBox.warning(self, _("Ошибка", "Error"),
                                    _("Не удалось создать чекпоинт.", "Failed to create checkpoint."))
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self._on_session_selected()

    def _do_rollback(self) -> None:
        svc = self._guard()
        cid = self._selected_checkpoint_id()
        if svc is None or not cid:
            return
        if QMessageBox.question(
            self, _("Откат", "Roll back"),
            _("Откатить сейв к этому чекпоинту? Текущие история/память/переменные будут заменены снимком.",
              "Roll the save back to this checkpoint? Current history/memory/variables will be replaced by the snapshot."),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            if not svc.rollback(cid):
                QMessageBox.warning(self, _("Ошибка", "Error"),
                                    _("Не удалось откатить.", "Rollback failed."))
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_delete_checkpoint(self) -> None:
        svc = self._guard()
        cid = self._selected_checkpoint_id()
        if svc is None or not cid:
            return
        if QMessageBox.question(
            self, _("Удалить чекпоинт", "Delete checkpoint"),
            _("Удалить выбранный чекпоинт?", "Delete the selected checkpoint?"),
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            svc.delete_checkpoint(cid)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self._on_session_selected()
