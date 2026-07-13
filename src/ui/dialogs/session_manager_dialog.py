"""SessionManagerDialog — управление сейвами (сессиями) и их чекпоинтами из песочницы.

Ходит напрямую в SessionService (как _SessionSelector). Списки с контекстным меню
(правый клик), у каждого сейва/чекпоинта можно задать комментарий и цвет.
Мутирующие операции (переключение, копирование, удаление, чекпоинты, откат)
блокируются, когда подключена игра: тогда сейвами управляет клиент Unity, иначе
Python-БД и папка сейва Unity разойдутся. Списки при этом остаются для просмотра.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils import _

# Пресеты цветов для быстрой пометки (подпись RU/EN + hex).
_COLOR_PRESETS = [
    ("Красный", "Red", "#e53935"),
    ("Оранжевый", "Orange", "#fb8c00"),
    ("Жёлтый", "Yellow", "#fdd835"),
    ("Зелёный", "Green", "#43a047"),
    ("Голубой", "Blue", "#1e88e5"),
    ("Фиолетовый", "Purple", "#8e24aa"),
]


class SessionManagerDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Сейвы и чекпоинты", "Saves & checkpoints"))
        self.setMinimumSize(760, 480)
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
        saves_title = QLabel(_("Сейвы  (правый клик — действия)", "Saves  (right-click for actions)"))
        saves_title.setStyleSheet("font-weight: 600;")
        saves_box.addWidget(saves_title)

        self._sessions_list = QListWidget()
        self._sessions_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sessions_list.customContextMenuRequested.connect(self._sessions_menu)
        self._sessions_list.currentItemChanged.connect(lambda *_: self._on_session_selected())
        self._sessions_list.itemDoubleClicked.connect(lambda *_: self._do_switch())
        saves_box.addWidget(self._sessions_list, 1)
        columns.addLayout(saves_box, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        columns.addWidget(sep)

        # --- Checkpoints column ---
        ck_box = QVBoxLayout()
        ck_box.setSpacing(6)
        self._ck_title = QLabel(_("Чекпоинты  (правый клик — действия)", "Checkpoints  (right-click for actions)"))
        self._ck_title.setStyleSheet("font-weight: 600;")
        ck_box.addWidget(self._ck_title)

        self._checkpoints_list = QListWidget()
        self._checkpoints_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._checkpoints_list.customContextMenuRequested.connect(self._checkpoints_menu)
        self._checkpoints_list.itemDoubleClicked.connect(lambda *_: self._do_rollback())
        ck_box.addWidget(self._checkpoints_list, 1)
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
    # helpers: selection, swatches
    # ------------------------------------------------------------------
    def _selected_session_id(self) -> Optional[str]:
        item = self._sessions_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _selected_checkpoint_id(self) -> Optional[str]:
        item = self._checkpoints_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole) or "")

    @staticmethod
    def _swatch(color_hex: str) -> QIcon:
        pix = QPixmap(14, 14)
        c = QColor(color_hex)
        pix.fill(c if c.isValid() else Qt.GlobalColor.transparent)
        return QIcon(pix)

    def _decorate_item(self, item: QListWidgetItem, color_hex: str, comment: str) -> None:
        if color_hex:
            c = QColor(color_hex)
            if c.isValid():
                item.setIcon(self._swatch(color_hex))
                tint = QColor(c)
                tint.setAlpha(48)
                item.setBackground(tint)
        if comment:
            item.setToolTip(comment)

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        svc = self._service()
        if svc is None:
            self._hint.setText(_("SessionService недоступен.", "SessionService is unavailable."))
            self._sessions_list.clear()
            self._checkpoints_list.clear()
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
            comment = str(s.get("comment", "") or "")
            head = ("● " if is_active else "") + f"{label}    {counts}"
            text = head + (("\n" + comment) if comment else "")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self._decorate_item(item, str(s.get("color", "") or ""), comment)
            self._sessions_list.addItem(item)
            if (prev and sid == prev) or (not prev and sid == current):
                select_row = i
        self._sessions_list.blockSignals(False)
        if self._sessions_list.count():
            self._sessions_list.setCurrentRow(select_row)

        self._update_hint()
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
                    comment = str(ck.get("comment", "") or "")
                    title = label if label else _("(без метки)", "(no label)")
                    head = f"{title}   [{tag}]   {created}"
                    text = head + (("\n" + comment) if comment else "")
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, cid)
                    self._decorate_item(item, str(ck.get("color", "") or ""), comment)
                    self._checkpoints_list.addItem(item)
            except Exception:
                pass

    def _update_hint(self) -> None:
        if self._game_connected():
            self._hint.setText(_(
                "⚠ Игра подключена — изменения заблокированы (иначе БД и папка сейва Unity разойдутся). "
                "Управляйте из игры. Списки доступны для просмотра.",
                "⚠ The game is connected — changes are disabled (otherwise the DB and Unity's save folder drift). "
                "Manage from the game. Lists are view-only.",
            ))
        else:
            try:
                current = self._service().current() if self._service() else "?"
            except Exception:
                current = "?"
            self._hint.setText(_("Активный сейв: ", "Active save: ") + str(current))

    # ------------------------------------------------------------------
    # context menus
    # ------------------------------------------------------------------
    def _sessions_menu(self, pos: QPoint) -> None:
        item = self._sessions_list.itemAt(pos)
        if item is not None:
            self._sessions_list.setCurrentItem(item)
        sid = self._selected_session_id()
        if not sid:
            return
        enabled = not self._game_connected()
        svc = self._service()
        try:
            is_active = bool(svc and sid == svc.current())
        except Exception:
            is_active = False

        menu = QMenu(self)
        act_switch = menu.addAction(_("Открыть", "Switch to"))
        act_switch.setEnabled(enabled and not is_active)
        menu.addSeparator()
        act_ckpt = menu.addAction(_("Создать чекпоинт…", "Create checkpoint…"))
        act_ckpt.setEnabled(enabled)
        menu.addSeparator()
        act_comment = menu.addAction(_("Комментарий…", "Comment…"))
        act_comment.setEnabled(enabled)
        self._add_color_submenu(menu, enabled, lambda c: self._set_session_color(sid, c))
        menu.addSeparator()
        act_copy = menu.addAction(_("Копия / ветка…", "Copy / branch…"))
        act_copy.setEnabled(enabled)
        act_rename = menu.addAction(_("Переименовать…", "Rename…"))
        act_rename.setEnabled(enabled and sid != "default")
        act_clear = menu.addAction(_("Очистить", "Clear"))
        act_clear.setEnabled(enabled)
        act_delete = menu.addAction(_("Удалить", "Delete"))
        act_delete.setEnabled(enabled and not is_active)

        chosen = menu.exec(self._sessions_list.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_switch:
            self._do_switch()
        elif chosen == act_ckpt:
            self._do_create_checkpoint()
        elif chosen == act_comment:
            self._do_session_comment(sid)
        elif chosen == act_copy:
            self._do_copy()
        elif chosen == act_rename:
            self._do_rename()
        elif chosen == act_clear:
            self._do_clear()
        elif chosen == act_delete:
            self._do_delete()

    def _checkpoints_menu(self, pos: QPoint) -> None:
        item = self._checkpoints_list.itemAt(pos)
        enabled = not self._game_connected()
        menu = QMenu(self)
        if item is None:
            # пустая область — предложить создать чекпоинт для выбранного сейва
            act_new = menu.addAction(_("Создать чекпоинт…", "Create checkpoint…"))
            act_new.setEnabled(enabled and bool(self._selected_session_id()))
            if menu.exec(self._checkpoints_list.mapToGlobal(pos)) == act_new:
                self._do_create_checkpoint()
            return

        self._checkpoints_list.setCurrentItem(item)
        cid = self._selected_checkpoint_id()
        if not cid:
            return

        act_rollback = menu.addAction(_("Откатить к чекпоинту", "Roll back to checkpoint"))
        act_rollback.setEnabled(enabled)
        menu.addSeparator()
        act_label = menu.addAction(_("Метка…", "Label…"))
        act_label.setEnabled(enabled)
        act_comment = menu.addAction(_("Комментарий…", "Comment…"))
        act_comment.setEnabled(enabled)
        self._add_color_submenu(menu, enabled, lambda c: self._set_checkpoint_color(cid, c))
        menu.addSeparator()
        act_delete = menu.addAction(_("Удалить чекпоинт", "Delete checkpoint"))
        act_delete.setEnabled(enabled)

        chosen = menu.exec(self._checkpoints_list.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_rollback:
            self._do_rollback()
        elif chosen == act_label:
            self._do_checkpoint_label(cid)
        elif chosen == act_comment:
            self._do_checkpoint_comment(cid)
        elif chosen == act_delete:
            self._do_delete_checkpoint()

    def _add_color_submenu(self, menu: QMenu, enabled: bool, apply_fn) -> None:
        sub = menu.addMenu(_("Цвет", "Color"))
        sub.setEnabled(enabled)
        for ru, en, hex_code in _COLOR_PRESETS:
            act = sub.addAction(self._swatch(hex_code), _(ru, en))
            act.triggered.connect(lambda _checked=False, c=hex_code: apply_fn(c))
        sub.addSeparator()
        pick = sub.addAction(_("Выбрать…", "Pick…"))
        pick.triggered.connect(lambda _checked=False: apply_fn(self._pick_color()))
        clear = sub.addAction(_("Убрать цвет", "Clear color"))
        clear.triggered.connect(lambda _checked=False: apply_fn(""))

    def _pick_color(self) -> Optional[str]:
        col = QColorDialog.getColor(parent=self, title=_("Выбор цвета", "Pick a color"))
        return col.name() if col.isValid() else None

    # ------------------------------------------------------------------
    # meta actions
    # ------------------------------------------------------------------
    def _set_session_color(self, sid: str, color: Optional[str]) -> None:
        svc = self._guard()
        if svc is None or color is None:
            return
        try:
            svc.set_session_meta(sid, color=color)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _set_checkpoint_color(self, cid: str, color: Optional[str]) -> None:
        svc = self._guard()
        if svc is None or color is None:
            return
        try:
            svc.set_checkpoint_meta(cid, color=color)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self._on_session_selected()

    def _do_session_comment(self, sid: str) -> None:
        svc = self._guard()
        if svc is None:
            return
        current = ""
        try:
            current = svc.get_session_meta(sid).get("comment", "")
        except Exception:
            pass
        text, ok = QInputDialog.getMultiLineText(
            self, _("Комментарий к сейву", "Save comment"),
            _("Заметка для «{s}»:", "Note for '{s}':").format(s=sid), current,
        )
        if not ok:
            return
        try:
            svc.set_session_meta(sid, comment=text.strip())
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_checkpoint_comment(self, cid: str) -> None:
        svc = self._guard()
        if svc is None:
            return
        current = ""
        try:
            for ck in svc.list_checkpoints(self._selected_session_id()):
                if ck.get("checkpoint_id") == cid:
                    current = ck.get("comment", "")
                    break
        except Exception:
            pass
        text, ok = QInputDialog.getMultiLineText(
            self, _("Комментарий к чекпоинту", "Checkpoint comment"),
            _("Заметка:", "Note:"), current,
        )
        if not ok:
            return
        try:
            svc.set_checkpoint_meta(cid, comment=text.strip())
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self._on_session_selected()

    def _do_checkpoint_label(self, cid: str) -> None:
        svc = self._guard()
        if svc is None:
            return
        current = ""
        try:
            for ck in svc.list_checkpoints(self._selected_session_id()):
                if ck.get("checkpoint_id") == cid:
                    current = ck.get("label", "")
                    break
        except Exception:
            pass
        text, ok = QInputDialog.getText(self, _("Метка чекпоинта", "Checkpoint label"),
                                        _("Короткая метка:", "Short label:"), text=current)
        if not ok:
            return
        try:
            svc.set_checkpoint_meta(cid, label=text.strip())
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self._on_session_selected()

    # ------------------------------------------------------------------
    # session/checkpoint actions
    # ------------------------------------------------------------------
    def _guard(self):
        """Сервис, если операция разрешена (игра не подключена), иначе None."""
        if self._game_connected():
            QMessageBox.information(
                self, _("Игра подключена", "Game connected"),
                _("Изменения недоступны, пока игра запущена.", "Changes are disabled while the game is running."),
            )
            return None
        return self._service()

    def _do_switch(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        try:
            if sid != svc.current():
                svc.switch(sid)
        except Exception as e:
            QMessageBox.warning(self, _("Ошибка", "Error"), str(e))
        self.refresh()

    def _do_copy(self) -> None:
        svc = self._guard()
        sid = self._selected_session_id()
        if svc is None or not sid:
            return
        dst, ok = QInputDialog.getText(
            self, _("Копия сейва", "Copy save"),
            _("Идентификатор нового сейва:", "New save id:"), text=f"{sid}-copy",
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
        if svc is None or not sid or sid == "default":
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
                QMessageBox.warning(self, _("Ошибка", "Error"), _("Не удалось откатить.", "Rollback failed."))
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
