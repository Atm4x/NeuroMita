from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.events import Events, get_event_bus
from main_logger import logger
from managers.conversation_session import ConversationSession, ConversationSessionManager
from managers.settings_manager import SettingsManager


@dataclass
class GameMasterIntervention:
    text: str = ""
    segments: list[dict] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    coach_notes: list[dict] = field(default_factory=list)  # [{"target": "...", "hint": "..."}]
    next_speaker: Optional[str] = None
    roles_fired: list[str] = field(default_factory=list)


class GameMasterOrchestrator:
    """Решает, нужно ли вмешательство GM, готовит контекст и отправляет
    запрос обычному персонажу 'GameMaster' через ChatController.SEND_MESSAGE.

    Использует существующий Character GameMaster (его промпт, DSL, историю).
    """

    _instance: Optional["GameMasterOrchestrator"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._bus = get_event_bus()
        self._sessions = ConversationSessionManager.instance()

    @classmethod
    def instance(cls) -> "GameMasterOrchestrator":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── decisions ────────────────────────────────────────────────────

    def evaluate(self, session: ConversationSession) -> Optional[GameMasterIntervention]:
        if not session.gm_enabled:
            return None
        if not bool(SettingsManager.get("GM_ENABLED", True)):
            return None
        cooldown = float(SettingsManager.get("GM_MIN_COOLDOWN_SEC", 5.0))
        if session.last_gm_intervention_at and (time.time() - session.last_gm_intervention_at) < cooldown:
            return None
        max_int = int(SettingsManager.get("GM_MAX_INTERVENTIONS_PER_SESSION", 20))
        if session.gm_intervention_count >= max_int:
            return None

        roles = self._active_roles(session)
        if not roles:
            return None

        method = str(SettingsManager.get("GM_REPETITION_METHOD", "auto"))
        rep_score = self._sessions.repetition_score(session, method=method)
        rep_thr = float(SettingsManager.get("GM_REPETITION_THRESHOLD", 0.7))
        loop_window = int(SettingsManager.get("GM_LOOP_WINDOW", 6))
        loop_sim = float(SettingsManager.get("GM_LOOP_SIMILARITY", 0.6))
        loop_flag = self._sessions.loop_detected(session, window=loop_window, threshold=loop_sim)
        silence = self._sessions.silence_duration(session)
        pause_thr = float(SettingsManager.get("GM_PAUSE_TIMEOUT_SEC", 30.0))
        narr_every = max(1, int(SettingsManager.get("GM_NARRATOR_EVERY", 5)))

        fire: list[str] = []
        if "moderator" in roles and (rep_score >= rep_thr or loop_flag):
            fire.append("moderator")
        if "narrator" in roles and (silence >= pause_thr or (session.total_turns > 0 and session.total_turns % narr_every == 0)):
            fire.append("narrator")
        if "director" in roles and self._should_fire_director(session, silence=silence, pause_threshold=pause_thr):
            fire.append("director")
        if "coach" in roles and self._detect_player_pattern(session):
            fire.append("coach")

        if not fire:
            return None

        logger.info(
            f"[GameMasterOrchestrator] firing roles={fire} sid={session.session_id} "
            f"rep={rep_score:.2f} loop={loop_flag} silence={silence:.0f}s"
        )
        return self._invoke_gm(session, fire, metrics={
            "repetition": rep_score,
            "loop_detected": loop_flag,
            "silence_sec": silence,
        })

    def suggest_next_speaker(self, session: ConversationSession) -> Optional[str]:
        # Простая эвристика — отдаём слово тому, кто давно не говорил
        spoken: dict[str, int] = {p: 0 for p in session.participants}
        for t in reversed(list(session.turns)[-10:]):
            if t.speaker_id in spoken:
                spoken[t.speaker_id] += 1
        if not spoken:
            return None
        # Сначала те у кого 0, потом по возрастанию
        candidates = sorted(spoken.items(), key=lambda kv: (kv[1], kv[0]))
        return candidates[0][0] if candidates else None

    # ── invocation ───────────────────────────────────────────────────

    def _invoke_gm(self, session: ConversationSession, roles_fired: list[str], metrics: dict) -> Optional[GameMasterIntervention]:
        context_text = self._render_dialogue_context(session, metrics, roles_fired)
        narrator_visible = "narrator" in roles_fired

        # Включаем нужные роли как DSL-переменные НА самом GameMaster-персонаже,
        # чтобы gm_roles.system правильно отработал [IF GM_ROLE_*_ACTIVE].
        try:
            res = self._bus.emit_and_wait(Events.Character.GET, {"character_id": "GameMaster"}, timeout=0.5)
            gm_char = res[0] if res else None
            if gm_char is not None and hasattr(gm_char, "set_variable"):
                for r in ("moderator", "narrator", "director", "coach"):
                    gm_char.set_variable(f"GM_ROLE_{r.upper()}_ACTIVE", (r in roles_fired))
            else:
                logger.warning("[GameMasterOrchestrator] не нашли GameMaster character для установки role-флагов")
        except Exception as e:
            logger.warning(f"[GameMasterOrchestrator] не удалось выставить role-флаги: {e}")

        # Синхронный вызов через emit_and_wait — слишком много завязок;
        # вместо этого мы шлём обычный SEND_MESSAGE и доверяем
        # MitaDialogueOrchestrator поймать ответ на ON_SUCCESSFUL_RESPONSE с is_game_master=True.
        try:
            self._bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": context_text}, sync=True)
        except Exception:
            self._bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {"content": context_text})

        policy = {
            "use_history_in_prompt": True,
            "write_to_history": bool(narrator_visible),
            "allow_voiceover": bool(narrator_visible),
            "allow_streaming": bool(narrator_visible),
            "echo_to_ui": bool(narrator_visible),
            "use_pending_sysinfo": True,
            "system_input_role": "system",
        }

        payload = {
            "user_input": "",
            "character_id": "GameMaster",
            "sender": "Player",
            "participants": ["Player", *session.participants],
            "system_input": "",
            "event_type": "gm_intervention",
            "is_game_master": True,
            "auto_continue": True,
            "session_id": session.session_id,
            "source": session.source,
            "policy": policy,
            "gm_roles_fired": list(roles_fired),
        }

        preset_id = str(SettingsManager.get("GM_MODEL_PRESET_ID", "") or "").strip()
        if bool(SettingsManager.get("GM_USE_SEPARATE_MODEL", False)) and preset_id:
            payload["model_preset_id"] = preset_id

        # Возвращаем «маркер» интервенции; сам ответ придёт асинхронно
        # и обработается в orchestrator._on_successful_response как is_gm_intervention.
        intervention = GameMasterIntervention(roles_fired=roles_fired)
        self._bus.emit(Events.Chat.SEND_MESSAGE, payload)
        self._bus.emit(Events.Conversation.GM_INTERVENTION, {
            "session_id": session.session_id,
            "roles": roles_fired,
            "metrics": metrics,
        })
        return intervention

    def dispatch_intervention(self, session: ConversationSession, intervention: GameMasterIntervention, source: str) -> None:
        # Заглушка: реальный текст GM придёт через ON_SUCCESSFUL_RESPONSE.
        # Здесь только метим, что мы запустили вмешательство.
        logger.debug(f"[GameMasterOrchestrator] dispatched intervention sid={session.session_id}")

    # ── вспомогательные ─────────────────────────────────────────────

    def _active_roles(self, session: ConversationSession) -> set[str]:
        if session.gm_active_roles:
            return set(session.gm_active_roles)
        roles: set[str] = set()
        for name in ("moderator", "narrator", "director", "coach"):
            if bool(SettingsManager.get(f"GM_ROLE_{name.upper()}", name == "moderator")):
                roles.add(name)
        return roles

    def _should_fire_director(
        self,
        session: ConversationSession,
        *,
        silence: float,
        pause_threshold: float,
    ) -> bool:
        mode = str(SettingsManager.get("GM_DIRECTOR_TRIGGER_MODE", "after_player_gap") or "after_player_gap").strip().lower()
        if mode == "never":
            return False
        if mode == "always":
            return True

        min_turns = max(1, int(SettingsManager.get("GM_DIRECTOR_MIN_TURNS_SINCE_PLAYER", 2)))
        if mode == "pause_or_gap":
            return session.turn_count_since_player >= min_turns or silence >= pause_threshold

        return session.turn_count_since_player >= min_turns

    def _detect_player_pattern(self, session: ConversationSession) -> bool:
        # Лёгкая эвристика: последние 3 реплики игрока короткие/повторяющиеся
        player_texts = [t.text for t in list(session.turns)[-10:] if t.speaker_id == "Player"]
        if len(player_texts) < 2:
            return False
        last = player_texts[-1].strip()
        if len(last) < 4:
            return True
        # повтор
        if player_texts.count(last) >= 2:
            return True
        return False

    def _render_dialogue_context(
        self,
        session: ConversationSession,
        metrics: dict,
        roles_fired: list[str],
    ) -> str:
        def _shrink(text: str, limit: int = 160) -> str:
            text = " ".join(str(text or "").split())
            if len(text) <= limit:
                return text
            return text[: max(0, limit - 1)].rstrip() + "…"

        template = self._load_template()
        recent = list(session.turns)[-6:]
        recent_text = "\n".join(
            f"  [{t.turn_number}] {t.speaker_id} -> {t.target_id or 'all'}: {_shrink(t.text)}"
            for t in recent if not t.is_gm_intervention
        ) or "  (no turns yet)"
        gm_history = session.recent_gm_turns()[-3:]
        gm_text = "\n".join(f"  [{t.turn_number}] {_shrink(t.text, 120)}" for t in gm_history) or "  (none)"

        parts_with_stats: list[str] = []
        for p in session.participants:
            try:
                res = self._bus.emit_and_wait(Events.Character.GET, {"character_id": p}, timeout=0.3)
                ch = res[0] if res else None
                if ch and hasattr(ch, "get_stats_dict"):
                    s = ch.get_stats_dict()
                    parts_with_stats.append(
                        f"  - {p}: attitude={s.get('attitude', '?')}, boredom={s.get('boredom', '?')}, stress={s.get('stress', '?')}"
                    )
                else:
                    parts_with_stats.append(f"  - {p}")
            except Exception:
                parts_with_stats.append(f"  - {p}")

        ctx = {
            "TOTAL_TURNS": session.total_turns,
            "TURNS_SINCE_PLAYER": session.turn_count_since_player,
            "PARTICIPANTS_WITH_STATS": "\n".join(parts_with_stats) or "  (empty)",
            "REPETITION_SCORE": f"{float(metrics.get('repetition', 0.0)):.2f}",
            "LOOP_DETECTED": "true" if metrics.get("loop_detected") else "false",
            "SILENCE_SEC": f"{float(metrics.get('silence_sec', 0.0)):.0f}",
            "ACTIVE_ROLES": ", ".join(roles_fired),
            "LAST_GM_INTERVENTIONS": gm_text,
            "RECENT_TURNS_COUNT": str(len(recent)),
            "RECENT_TURNS": recent_text,
        }
        if template:
            try:
                return _safe_format(template, ctx)
            except Exception as e:
                logger.warning(f"[GameMasterOrchestrator] template format failed: {e}")

        # Fallback inline
        return (
            f"Current Dialogue State:\n"
            f"Total turns: {ctx['TOTAL_TURNS']}\n"
            f"Turns since last player: {ctx['TURNS_SINCE_PLAYER']}\n"
            f"Participants:\n{ctx['PARTICIPANTS_WITH_STATS']}\n"
            f"Metrics: repetition={ctx['REPETITION_SCORE']}, loop={ctx['LOOP_DETECTED']}, silence={ctx['SILENCE_SEC']}s\n"
            f"Active roles: {ctx['ACTIVE_ROLES']}\n"
            f"Last GM interventions:\n{ctx['LAST_GM_INTERVENTIONS']}\n"
            f"Recent {ctx['RECENT_TURNS_COUNT']} turns:\n{ctx['RECENT_TURNS']}"
        )

    def _load_template(self) -> str:
        candidates = [
            os.path.join("extra", "Prompts", "GameMaster", "DefaultJson", "dialogue_context.system"),
            os.path.join("Prompts", "GameMaster", "DefaultJson", "dialogue_context.system"),
        ]
        for path in candidates:
            try:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
            except Exception:
                continue
        return ""

    # ── парсинг ответа GM (вызывается из ChatController при is_gm_intervention) ──

    @staticmethod
    def parse_gm_response(response_text: str) -> GameMasterIntervention:
        intervention = GameMasterIntervention()
        if not response_text:
            return intervention
        # Пробуем как JSON ({"segments": [...]})
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and isinstance(data.get("segments"), list):
                segments = data["segments"]
                intervention.segments = segments
                texts: list[str] = []
                for seg in segments:
                    if not isinstance(seg, dict):
                        continue
                    if seg.get("text"):
                        texts.append(str(seg["text"]))
                    cmds = seg.get("commands") or []
                    if isinstance(cmds, list):
                        for c in cmds:
                            sc = str(c).strip()
                            if sc:
                                intervention.commands.append(sc)
                    coach = seg.get("coach_notes") or []
                    if isinstance(coach, list):
                        for note in coach:
                            if isinstance(note, dict) and note.get("target") and note.get("hint"):
                                intervention.coach_notes.append({
                                    "target": str(note["target"]),
                                    "hint": str(note["hint"]),
                                })
                intervention.text = "\n".join(texts)
                for cmd in intervention.commands:
                    if cmd.lower().startswith("speaker,"):
                        intervention.next_speaker = cmd.split(",", 1)[1].strip()
                        break
                return intervention
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: текст + поиск "Speaker,X" в тексте
        intervention.text = response_text
        m = re.search(r"Speaker\s*,\s*([^\r\n;]+)", response_text, flags=re.IGNORECASE)
        if m:
            speaker_name = m.group(1).strip().strip("\"'`").rstrip(" .,!?:")
            if speaker_name:
                intervention.commands.append(f"Speaker,{speaker_name}")
                intervention.next_speaker = speaker_name
        return intervention


def _safe_format(template: str, ctx: dict) -> str:
    out = template
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return out
