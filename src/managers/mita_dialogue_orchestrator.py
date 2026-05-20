from __future__ import annotations

import threading
import time
import re
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

    @staticmethod
    def _canon_actor_name(value: str) -> str:
        return re.sub(r"[\s_\-]+", "", str(value or "").strip()).lower()

    def _resolve_participant_id(self, session: ConversationSession, raw_value: str) -> Optional[str]:
        candidate = str(raw_value or "").strip()
        if not candidate or candidate == "Player":
            return None

        canon = self._canon_actor_name(candidate)
        if not canon:
            return None

        for pid in session.participants:
            if self._canon_actor_name(pid) == canon:
                return pid

        for pid in session.participants:
            try:
                res = self._bus.emit_and_wait(Events.Character.GET, {"character_id": pid}, timeout=0.3)
                ch = res[0] if res else None
            except Exception:
                ch = None

            aliases = [
                pid,
                getattr(ch, "char_id", ""),
                getattr(ch, "name", ""),
                getattr(ch, "short_name", ""),
            ]
            for alias in aliases:
                if self._canon_actor_name(alias) == canon:
                    return pid

        return None

    @staticmethod
    def _describe_auto_chain_reason(reason: Optional[str], speaker_id: str, last_speaker: str) -> str:
        reason_key = str(reason or "unspecified").strip().lower()
        mapping = {
            "direct_target": f"You were addressed directly, so reply as {speaker_id}.",
            "gm_selected": f"The hidden GameMaster selected you to continue after {last_speaker}.",
            "gm_command": "The hidden GameMaster explicitly queued you as the next speaker.",
            "auto_round_robin": "You have been silent longer than the others, so you should react now.",
            "react_interrupt": "A recent react/interrupt event requires you to respond in character now.",
            "unspecified": f"It is your turn to keep the dialogue moving after {last_speaker}.",
        }
        return mapping.get(reason_key, mapping["unspecified"])

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
            source_raw = str(data.get("source") or "").strip()

            if not character_id:
                return
            if not participants:
                return
            non_player = [p for p in participants if p and p != "Player"]
            if len(non_player) < 2 and not is_gm:
                # Один на один с игроком — оркестрация не нужна
                return

            # Если source не указан, пытаемся найти существующую сессию по составу
            # (unity → sandbox). Дефолтимся на 'unity', потому что мульти-мита сейчас
            # запускается из Unity-стороны заметно чаще, чем из песочницы.
            source = source_raw
            if not source:
                for candidate in ("unity", "sandbox"):
                    cand_sess = self._sessions.get(self._sessions._by_key.get((candidate, tuple(sorted(non_player))), ""))
                    if cand_sess is not None:
                        source = candidate
                        break
                if not source:
                    source = "unity"
                logger.debug(
                    f"[MitaDialogueOrchestrator] TURN_RECORDED без source — выбран '{source}' для participants={non_player}"
                )

            sess = self._sessions.get_or_create(non_player, source=source)
            primary_target = self._resolve_participant_id(sess, str(targets[0])) if targets else None

            self._sessions.record_turn(
                sess,
                speaker_id=character_id,
                target_id=primary_target,
                text=response_text,
                message_id=str(message_id) if message_id else None,
                is_gm_intervention=is_gm,
            )

            if character_id == "Player":
                return

            if is_gm:
                self._apply_gm_response(sess, data)
                gm_roles_fired = data.get("gm_roles_fired") or []
                # GM виден игроку только в narrator-режиме. Без gm_roles_fired
                # (legacy/text) считаем интервенцию скрытой — соответствует policy,
                # которую формирует GameMasterOrchestrator для не-narrator вызовов.
                gm_visible = bool(gm_roles_fired) and ("narrator" in gm_roles_fired)
                if source == "unity" and gm_visible:
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
                resolved = self._resolve_participant_id(sess, str(t))
                if resolved and resolved != character_id:
                    sess.append_pending_speaker(resolved, reason="direct_target")

            # Если очередь пуста и включена авто-цепочка — выбираем следующего оратора
            auto_on = bool(SettingsManager.get("MITADIALOGUE_AUTO", False)) or bool(SettingsManager.get("MITA_DIALOGUE_AUTO", False))
            if not sess.pending_speakers and auto_on:
                next_speaker = self._pick_next_speaker_round_robin(sess, exclude=character_id)
                if next_speaker:
                    sess.append_pending_speaker(next_speaker, reason="auto_round_robin")
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

        # Сбрасываем GM_ROLE_*_ACTIVE на GameMaster-character: они уже использованы
        # при BUILD_PROMPT, дальше держать их «грязными» нельзя — следующая
        # интервенция в другой сессии может прийти с другим набором ролей.
        try:
            res = self._bus.emit_and_wait(Events.Character.GET, {"character_id": "GameMaster"}, timeout=0.3)
            gm_char = res[0] if res else None
            if gm_char is not None and hasattr(gm_char, "set_variable"):
                for r in ("moderator", "narrator", "director", "coach"):
                    gm_char.set_variable(f"GM_ROLE_{r.upper()}_ACTIVE", False)
        except Exception:
            pass

        # Speaker,X команды → pending_speakers (приоритет — GM-указанный говорящий).
        # append_pending_speaker сам соблюдает порядок приоритетов (gm_selected/gm_command выше остальных).
        resolved_next = self._resolve_participant_id(session, intervention.next_speaker or "")
        if resolved_next:
            session.append_pending_speaker(resolved_next, reason="gm_selected")
        for cmd in intervention.commands:
            if cmd.lower().startswith("speaker,"):
                name = cmd.split(",", 1)[1].strip()
                resolved = self._resolve_participant_id(session, name)
                if resolved and resolved != resolved_next:
                    session.append_pending_speaker(resolved, reason="gm_command")

        # Coach-хинты → pending_coach_hints
        for note in intervention.coach_notes:
            target = note.get("target")
            hint = note.get("hint")
            resolved_target = self._resolve_participant_id(session, str(target or ""))
            if resolved_target and hint:
                session.push_coach_hint(resolved_target, str(hint))

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
                next_speaker = self._resolve_participant_id(session, c.split(",", 1)[1].strip())
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

        next_speaker, reason = session.next_pending_speaker()
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
                self._dispatch_next_message(session, next_speaker, source=source, reason=reason)
            finally:
                with self._lock:
                    if self._cancel_flags.get(session.session_id) is cancel_ev:
                        del self._cancel_flags[session.session_id]

        threading.Thread(target=fire, name=f"MitaChain-{session.session_id}", daemon=True).start()

    def _dispatch_next_message(
        self,
        session: ConversationSession,
        speaker_id: str,
        source: str,
        reason: Optional[str] = None,
    ) -> None:
        if cancel_ev_set(self._cancel_flags.get(session.session_id)):
            return

        resolved_speaker_id = self._resolve_participant_id(session, speaker_id)
        if not resolved_speaker_id:
            logger.warning(
                f"[MitaDialogueOrchestrator] next speaker '{speaker_id}' is not part of session {session.session_id}"
            )
            return
        speaker_id = resolved_speaker_id

        coach_hints = session.consume_coach_hints(speaker_id)
        pending_infos = list(session.pending_system_infos)
        session.pending_system_infos.clear()

        last_speaker = _last_other_speaker(session, speaker_id) or "Player"

        # Контекст авто-цепочки — единым system_input блоком (event role).
        # ВАЖНО: не используем фиктивный user_input, иначе он попадает в историю
        # каждой миты как реальное сообщение пользователя и засоряет контекст.
        chain_hint_parts = [
            "[AUTO_CHAIN]",
            f"It is now your turn to respond as {speaker_id} in this multi-character dialogue.",
            f"The previous speaker was {last_speaker}. React to their latest message that appears in the dialogue history above.",
            self._describe_auto_chain_reason(reason, speaker_id, last_speaker),
            f"You are NOT the Player and NOT {last_speaker}. Stay strictly in character as {speaker_id}; do not impersonate anyone else.",
        ]
        chain_hint = "\n".join(chain_hint_parts)

        system_input_parts: list[str] = [chain_hint]
        if coach_hints:
            system_input_parts.append("[COACH_HINTS]\n" + "\n".join(f"- {h}" for h in coach_hints))
        if pending_infos:
            system_input_parts.extend(pending_infos)
        system_input = "\n\n".join(p for p in system_input_parts if p).strip()

        # Гарантируем, что system_input уйдёт в промпт с ролью 'event', а не
        # сохранится в истории как user message. Policy включает system_input_role='event'
        # и write_to_history=False для самой стаб-генерации (assistant ответ всё равно
        # запишется через event_writer).
        from core.request_policy import resolve_policy
        chain_policy = resolve_policy(model_event_type="auto_chain")
        chain_policy.system_input_role = "event"
        chain_policy.use_pending_sysinfo = False

        payload = {
            "user_input": "",
            "character_id": speaker_id,
            "sender": last_speaker,
            "participants": ["Player", *session.participants],
            "system_input": system_input,
            "event_type": "auto_chain",
            "auto_chain_reason": reason or "unspecified",
            "auto_continue": True,
            "source": source,
            "session_id": session.session_id,
            "policy": chain_policy.to_dict(),
        }
        logger.info(
            f"[MitaDialogueOrchestrator] dispatch_next sid={session.session_id} "
            f"speaker={speaker_id} prev_speaker={last_speaker} "
            f"reason={reason or 'unspecified'} "
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
