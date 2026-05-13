from __future__ import annotations

import threading
import time
from typing import Any, Optional

from core.events import Events, get_event_bus
from main_logger import logger
from managers.conversation_session import ConversationSession, ConversationSessionManager
from managers.settings_manager import SettingsManager


DEFAULT_INTERRUPT_PRIORITY_RULES: dict[str, str] = {
    "PlayerDeath": "cancel_chain",
    "PlayerRespawn": "cancel_chain",
    "PlayerAttacked": "cancel_chain",
    "MannequinsSpawned": "cancel_chain",
    "FightRoundOutcome": "cancel_chain",
    "RoomEnter": "inject_context",
    "LongWatching": "inject_context",
    "CartridgeInserted": "inject_context",
}


class MitaDialogueOrchestrator:
    """Управляет очерёдностью реплик в мульти-персонажном диалоге.

    Заменяет логику Unity: CharacterControl.nextAnswer + GlobalFollowUpProcessor.
    Подключается к событиям Model.ON_SUCCESSFUL_RESPONSE и сам решает,
    кто говорит следующим.
    """

    _instance: Optional["MitaDialogueOrchestrator"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._bus = get_event_bus()
        self._lock = threading.RLock()
        self._sessions = ConversationSessionManager.instance()
        # Запланированные следующие ходы (по session_id): timer-like state
        self._cancel_flags: dict[str, threading.Event] = {}
        self._gm_orchestrator: Any = None  # ставится извне

        # Подписки. ON_SUCCESSFUL_RESPONSE эмитится без данных, поэтому используем
        # отдельное событие TURN_RECORDED, которое шлёт ConversationEventWriter.write_turn.
        self._bus.subscribe(Events.Conversation.TURN_RECORDED, self._on_successful_response, weak=False)
        self._bus.subscribe(Events.Conversation.CHAIN_CANCELLED, self._on_chain_cancelled, weak=False)

    @classmethod
    def instance(cls) -> "MitaDialogueOrchestrator":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def attach_gm_orchestrator(self, gm_orchestrator: Any) -> None:
        self._gm_orchestrator = gm_orchestrator

    # ── public API ───────────────────────────────────────────────────

    def on_react(self, character_id: str, participants: list[str], react_data: dict, source: str = "unity") -> str:
        """Возвращает: 'cancel_chain' | 'inject_context' | 'none'."""
        reason_type = str(react_data.get("reason_type") or "").strip()
        explicit_priority = str(react_data.get("interrupt_priority") or "").strip().lower()
        cancel_flag = bool(react_data.get("cancel_chain"))

        rules = SettingsManager.get("MITADIALOGUE_INTERRUPT_PRIORITY_RULES", None) or DEFAULT_INTERRUPT_PRIORITY_RULES
        rule = str(rules.get(reason_type, "")).strip().lower() if isinstance(rules, dict) else ""

        if cancel_flag or explicit_priority == "high" or rule == "cancel_chain":
            sess = self._sessions.get_or_create(participants or [character_id], source=source)
            self.cancel_chain(sess.session_id)
            sess.pending_system_infos.append(
                f"[REACT/{reason_type}] {react_data.get('reason_content', '')}".strip()
            )
            logger.info(f"[MitaDialogueOrchestrator] react cancel_chain reason={reason_type} sid={sess.session_id}")
            return "cancel_chain"

        if rule == "inject_context" or explicit_priority == "normal":
            sess = self._sessions.get_or_create(participants or [character_id], source=source)
            sess.pending_system_infos.append(
                f"[REACT/{reason_type}] {react_data.get('reason_content', '')}".strip()
            )
            return "inject_context"

        return "none"

    def cancel_chain(self, session_id: str) -> None:
        with self._lock:
            ev = self._cancel_flags.get(session_id)
            if ev:
                ev.set()
            sess = self._sessions.get(session_id)
            if sess:
                sess.clear_pending()
        self._bus.emit(Events.Conversation.CHAIN_CANCELLED, {"session_id": session_id})

    # ── обработка ответов ────────────────────────────────────────────

    def _on_chain_cancelled(self, event) -> None:
        # внешняя ручная отмена — уже отработана в cancel_chain; ничего не делаем здесь
        return None

    def _on_successful_response(self, event) -> None:
        data = event.data or {}
        try:
            character_id = str(data.get("character_id") or "").strip()
            sender = str(data.get("sender") or "Player")
            participants = data.get("participants") or []
            response_text = str(data.get("response") or data.get("text") or "")
            message_id = data.get("message_id")
            targets = data.get("targets") or []
            is_gm = bool(data.get("is_game_master"))
            source = str(data.get("source") or ("unity" if data.get("from_unity") else "sandbox"))

            if not character_id:
                return
            if not participants:
                return
            non_player = [p for p in participants if p and p != "Player"]
            if len(non_player) < 2 and not is_gm:
                # Один на один с игроком — оркестрация не нужна
                return

            sess = self._sessions.get_or_create(non_player, source=source)

            self._sessions.record_turn(
                sess,
                speaker_id=character_id,
                target_id=(str(targets[0]) if targets else None),
                text=response_text,
                message_id=str(message_id) if message_id else None,
                is_gm_intervention=is_gm,
            )

            if is_gm:
                self._apply_gm_response(sess, data)
                if source == "unity":
                    self._push_gm_to_unity(sess, data)
                self._continue_chain(sess, source=source)
                return

            # Сначала проверяем GM
            intervention = None
            if self._gm_orchestrator and sess.gm_enabled:
                try:
                    intervention = self._gm_orchestrator.evaluate(sess)
                except Exception as e:
                    logger.warning(f"[MitaDialogueOrchestrator] GM evaluate failed: {e}", exc_info=True)

            if intervention:
                self._gm_orchestrator.dispatch_intervention(sess, intervention, source=source)
                return

            # Добавляем targets из ответа в очередь
            for t in targets:
                if t and t != "Player" and t != character_id:
                    sess.append_pending_speaker(str(t))

            # Если очередь пуста и включена авто-цепочка — выбираем следующего оратора
            auto_on = bool(SettingsManager.get("MITADIALOGUE_AUTO", False)) or bool(SettingsManager.get("MITA_DIALOGUE_AUTO", False))
            if not sess.pending_speakers and auto_on:
                next_speaker = self._pick_next_speaker_round_robin(sess, exclude=character_id)
                if next_speaker:
                    sess.append_pending_speaker(next_speaker)
                    logger.info(f"[MitaDialogueOrchestrator] auto-chain picks next speaker: {next_speaker}")

            self._continue_chain(sess, source=source)
        except Exception as e:
            logger.error(f"[MitaDialogueOrchestrator] _on_successful_response error: {e}", exc_info=True)

    def _pick_next_speaker_round_robin(self, session: ConversationSession, exclude: str) -> Optional[str]:
        """Возвращает миту из participants, которая дольше всех молчала (не считая Player и exclude)."""
        candidates = [p for p in session.participants if p and p != "Player" and p != exclude]
        if not candidates:
            return None
        # Считаем последний turn_number для каждой миты
        last_at: dict[str, int] = {c: 0 for c in candidates}
        for t in list(session.turns):
            if t.is_gm_intervention:
                continue
            if t.speaker_id in last_at:
                last_at[t.speaker_id] = max(last_at[t.speaker_id], t.turn_number)
        # Выбираем кандидата с наименьшим last_at (молчавшую дольше всех)
        candidates.sort(key=lambda c: (last_at[c], c))
        return candidates[0]

    def _apply_gm_response(self, session: ConversationSession, response_data: dict) -> None:
        """Парсит GM-ответ: извлекает Speaker,X команды и coach_notes."""
        from managers.game_master_orchestrator import GameMasterOrchestrator
        structured = response_data.get("structured_data") or {}
        text = str(response_data.get("response") or "")

        intervention = None
        if isinstance(structured, dict) and structured.get("segments"):
            intervention = GameMasterOrchestrator.parse_gm_response(
                __import__("json").dumps(structured)
            )
        if intervention is None:
            intervention = GameMasterOrchestrator.parse_gm_response(text)

        # Speaker,X команды → pending_speakers (приоритет — GM-указанный говорящий)
        if intervention.next_speaker and intervention.next_speaker != "Player":
            session.pending_speakers.insert(0, intervention.next_speaker)
        for cmd in intervention.commands:
            if cmd.lower().startswith("speaker,"):
                name = cmd.split(",", 1)[1].strip()
                if name and name != "Player" and name != intervention.next_speaker:
                    session.pending_speakers.append(name)

        # Coach-хинты → pending_coach_hints
        for note in intervention.coach_notes:
            target = note.get("target")
            hint = note.get("hint")
            if target and hint:
                session.push_coach_hint(str(target), str(hint))

    def _push_gm_to_unity(self, session: ConversationSession, data: dict) -> None:
        structured = data.get("structured_data") or {}
        segments = []
        if isinstance(structured, dict) and isinstance(structured.get("segments"), list):
            segments = structured["segments"]
        else:
            text = str(data.get("response") or "")
            if text:
                segments = [{"text": text}]
        commands: list[str] = []
        for seg in segments:
            if isinstance(seg, dict):
                for c in (seg.get("commands") or []):
                    sc = str(c).strip()
                    if sc:
                        commands.append(sc)
        next_speaker = None
        for c in commands:
            if c.lower().startswith("speaker,"):
                next_speaker = c.split(",", 1)[1].strip()
                break
        try:
            from managers.settings_manager import SettingsManager
            payload = {
                "session_id": session.session_id,
                "push_type": "gm_narration",
                "character": "GameMaster",
                "data": {
                    "segments": segments,
                    "next_speaker": next_speaker,
                    "commands": commands,
                    "gm_read": True,
                    "gm_voice": bool(SettingsManager.get("GM_VOICE", False)),
                },
            }
            self._bus.emit(Events.Conversation.PUSH_TO_UNITY, payload)
        except Exception as e:
            logger.warning(f"[MitaDialogueOrchestrator] push_gm_to_unity failed: {e}", exc_info=True)

    def _continue_chain(self, session: ConversationSession, source: str) -> None:
        if session.turn_count_since_player >= int(SettingsManager.get("MITADIALOGUE_MAX_AUTO_TURNS", 3)):
            session.clear_pending()
            return

        next_speaker = session.next_pending_speaker()
        if not next_speaker:
            return

        mode = str(SettingsManager.get("MITADIALOGUE_CHAIN_MODE", "adaptive")).lower()
        window = float(SettingsManager.get("MITADIALOGUE_INTERRUPT_WINDOW_SEC", 3.0))

        cancel_ev = threading.Event()
        with self._lock:
            self._cancel_flags[session.session_id] = cancel_ev

        def fire() -> None:
            try:
                if mode == "adaptive" and window > 0:
                    if cancel_ev.wait(timeout=window):
                        logger.debug(f"[MitaDialogueOrchestrator] chain cancelled before firing sid={session.session_id}")
                        return
                # wait_display пока эквивалентен immediate; реализация — позже
                self._dispatch_next_message(session, next_speaker, source=source)
            finally:
                with self._lock:
                    if self._cancel_flags.get(session.session_id) is cancel_ev:
                        del self._cancel_flags[session.session_id]

        threading.Thread(target=fire, name=f"MitaChain-{session.session_id}", daemon=True).start()

    def _dispatch_next_message(self, session: ConversationSession, speaker_id: str, source: str) -> None:
        if cancel_ev_set(self._cancel_flags.get(session.session_id)):
            return

        coach_hints = session.consume_coach_hints(speaker_id)
        pending_infos = list(session.pending_system_infos)
        session.pending_system_infos.clear()

        last_speaker = _last_other_speaker(session, speaker_id) or "Player"

        # Контекст авто-цепочки идёт в промпт через ADD_TEMPORARY_SYSTEM_INFO —
        # минуя UI-эхо, но попадая в next BUILD_PROMPT.
        chain_hint = (
            f"[AUTO_CHAIN]\n"
            f"It is now your ({speaker_id}) turn to respond in this multi-character dialogue.\n"
            f"The previous speaker was {last_speaker}. React to their latest message that appears in the history.\n"
            f"You are NOT the Player and NOT {last_speaker} — respond as {speaker_id} in character. "
            f"Do not echo or impersonate the player."
        )
        try:
            self._bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": chain_hint}, sync=True)
        except Exception:
            self._bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": chain_hint})

        # system_input — только UI-видимые подсказки (coach + pending infos)
        system_input_parts: list[str] = []
        if coach_hints:
            system_input_parts.append("[COACH_HINTS]\n" + "\n".join(f"- {h}" for h in coach_hints))
        if pending_infos:
            system_input_parts.extend(pending_infos)
        system_input = "\n\n".join(system_input_parts).strip()

        # Пользовательский ввод подделываем кратко: "your turn" — чтобы был user-turn в промпте.
        # LLM лучше реагирует когда есть явный last user message.
        user_input_stub = f"({last_speaker} только что говорил(а) — твоя очередь, {speaker_id}.)"

        payload = {
            "user_input": user_input_stub,
            "character_id": speaker_id,
            "sender": last_speaker,
            "participants": ["Player", *session.participants],
            "system_input": system_input,
            "event_type": "auto_chain",
            "auto_continue": True,
            "source": source,
            "session_id": session.session_id,
        }
        logger.info(
            f"[MitaDialogueOrchestrator] dispatch_next sid={session.session_id} "
            f"speaker={speaker_id} prev_speaker={last_speaker} "
            f"(coach_hints={len(coach_hints)}, infos={len(pending_infos)})"
        )
        self._bus.emit(Events.Chat.SEND_MESSAGE, payload)


def cancel_ev_set(ev: Optional[threading.Event]) -> bool:
    return bool(ev and ev.is_set())


def _last_other_speaker(session: ConversationSession, exclude: str) -> Optional[str]:
    for t in reversed(list(session.turns)):
        if t.speaker_id and t.speaker_id != exclude and not t.is_gm_intervention:
            return t.speaker_id
    return None
