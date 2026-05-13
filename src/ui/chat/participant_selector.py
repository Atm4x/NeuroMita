from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.events import Events, get_event_bus
from main_logger import logger


DEFAULT_NPCS: tuple[str, ...] = (
    "Crazy", "Kind", "Cappy", "ShortHair", "Mila", "Sleepy", "Creepy", "Ghost",
)

GM_ROLES: tuple[str, ...] = ("moderator", "narrator", "director", "coach")


class ParticipantSelector(QWidget):
    """Виджет выбора участников мульти-персонажного диалога в Sandbox.

    Сигналы:
        participantsChanged(list[str], dict)  — список участников и {role: bool}
    """

    participantsChanged = pyqtSignal(list, dict)
    sessionResetRequested = pyqtSignal(list, dict)

    def __init__(self, parent: QWidget | None = None, *, characters: Iterable[str] | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ParticipantSelector")
        self._characters = list(characters or DEFAULT_NPCS)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._gm_role_checkboxes: dict[str, QCheckBox] = {}
        self._gm_master_cb: QCheckBox | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title = QLabel("Participants", self)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        for char_id in self._characters:
            cb = QCheckBox(char_id, self)
            cb.stateChanged.connect(self._emit_changed)
            self._checkboxes[char_id] = cb
            layout.addWidget(cb)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Авто-цепочка реплик мит (round-robin без GM)
        self._auto_chain_cb = QCheckBox("Авто-цепочка мит (без GM)", self)
        self._auto_chain_cb.setToolTip(
            "Если включено, миты говорят по очереди (round-robin) без вмешательства GameMaster.\n"
            "Если выключено, следующая мита отвечает только если предыдущая явно к ней обратилась (target)."
        )
        self._auto_chain_cb.stateChanged.connect(self._on_auto_chain_toggled)
        layout.addWidget(self._auto_chain_cb)

        sep_auto = QFrame(self)
        sep_auto.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep_auto)

        gm_master = QCheckBox("GameMaster (orchestrator)", self)
        gm_master.stateChanged.connect(self._emit_changed)
        self._gm_master_cb = gm_master
        layout.addWidget(gm_master)

        roles_row = QHBoxLayout()
        roles_row.setSpacing(6)
        for role in GM_ROLES:
            cb = QCheckBox(role, self)
            cb.stateChanged.connect(self._emit_changed)
            self._gm_role_checkboxes[role] = cb
            roles_row.addWidget(cb)
        roles_row.addStretch(1)
        layout.addLayout(roles_row)

        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        btn = QPushButton("Сбросить историю сессии", self)
        btn.setToolTip(
            "Завершает текущую sandbox-сессию и создаёт новую с теми же участниками.\n"
            "Полезно, когда хочется начать диалог с чистым счётчиком (GM cooldown, метрики)."
        )
        btn.clicked.connect(self._on_reset_clicked)
        layout.addWidget(btn)
        layout.addStretch(1)

        # Синхронизация с глобальными настройками при создании
        self._load_from_settings()

    # ── API ──

    def selected_participants(self) -> list[str]:
        return [name for name, cb in self._checkboxes.items() if cb.isChecked()]

    def gm_roles(self) -> dict[str, bool]:
        if not self._gm_master_cb or not self._gm_master_cb.isChecked():
            return {r: False for r in GM_ROLES}
        return {r: cb.isChecked() for r, cb in self._gm_role_checkboxes.items()}

    def set_participants(self, names: Iterable[str]) -> None:
        s = set(names or [])
        for n, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(n in s)
            cb.blockSignals(False)
        self._emit_changed()

    # ── settings sync ──

    def _load_from_settings(self) -> None:
        try:
            from managers.settings_manager import SettingsManager
            gm_on = bool(SettingsManager.get("GM_ENABLED", True))
            if self._gm_master_cb:
                self._gm_master_cb.blockSignals(True)
                self._gm_master_cb.setChecked(gm_on)
                self._gm_master_cb.blockSignals(False)
            for role, cb in self._gm_role_checkboxes.items():
                val = bool(SettingsManager.get(f"GM_ROLE_{role.upper()}", role == "moderator"))
                cb.blockSignals(True)
                cb.setChecked(val)
                cb.blockSignals(False)
            auto_on = bool(SettingsManager.get("MITADIALOGUE_AUTO", False)) or bool(SettingsManager.get("MITA_DIALOGUE_AUTO", False))
            self._auto_chain_cb.blockSignals(True)
            self._auto_chain_cb.setChecked(auto_on)
            self._auto_chain_cb.blockSignals(False)
        except Exception as e:
            logger.debug(f"[ParticipantSelector] load_from_settings failed: {e}")

    def _on_auto_chain_toggled(self, _state: int) -> None:
        try:
            from managers.settings_manager import SettingsManager
            on = self._auto_chain_cb.isChecked()
            # Пишем в обе настройки для совместимости (старая MITA_DIALOGUE_AUTO + новая MITADIALOGUE_AUTO)
            SettingsManager.set("MITADIALOGUE_AUTO", bool(on))
            SettingsManager.set("MITA_DIALOGUE_AUTO", bool(on))
            logger.info(f"[ParticipantSelector] MITADIALOGUE_AUTO = {on}")
        except Exception as e:
            logger.warning(f"[ParticipantSelector] failed to save auto-chain setting: {e}")
        self._emit_changed()

    # ── handlers ──

    def _emit_changed(self) -> None:
        participants = self.selected_participants()
        roles = self.gm_roles()
        # Синхронизируем глобальные настройки GM с состоянием чекбоксов
        try:
            from managers.settings_manager import SettingsManager
            gm_on = bool(self._gm_master_cb and self._gm_master_cb.isChecked())
            SettingsManager.set("GM_ENABLED", gm_on)
            for role, cb in self._gm_role_checkboxes.items():
                SettingsManager.set(f"GM_ROLE_{role.upper()}", bool(cb.isChecked()))
        except Exception as e:
            logger.debug(f"[ParticipantSelector] sync settings failed: {e}")
        try:
            self.participantsChanged.emit(participants, roles)
        except Exception as e:
            logger.debug(f"[ParticipantSelector] emit changed failed: {e}")

    def _on_reset_clicked(self) -> None:
        participants = self.selected_participants()
        roles = self.gm_roles()
        try:
            from managers.conversation_session import ConversationSessionManager
            mgr = ConversationSessionManager.instance()
            mgr.end_for_source("sandbox")
            active = {r for r, on in roles.items() if on}
            sess = mgr.get_or_create(
                participants,
                source="sandbox",
                gm_enabled=bool(self._gm_master_cb and self._gm_master_cb.isChecked()),
                gm_active_roles=active,
            )
            logger.info(f"[ParticipantSelector] new sandbox session sid={sess.session_id} participants={participants} roles={active}")
            try:
                get_event_bus().emit(Events.Conversation.SESSION_START, {
                    "session_id": sess.session_id,
                    "participants": list(sess.participants),
                    "source": "sandbox",
                    "gm_roles": list(active),
                })
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[ParticipantSelector] failed to reset session: {e}", exc_info=True)
        try:
            self.sessionResetRequested.emit(participants, roles)
        except Exception:
            pass
