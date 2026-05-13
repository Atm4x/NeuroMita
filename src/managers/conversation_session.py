from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from main_logger import logger


MAX_TURNS_RETAINED = 30
MAX_GM_HISTORY_TAIL = 5


@dataclass
class SpeakerTurn:
    speaker_id: str
    target_id: Optional[str]
    text: str
    turn_number: int
    timestamp: float
    message_id: Optional[str] = None
    is_gm_intervention: bool = False


@dataclass
class ConversationSession:
    session_id: str
    participants: tuple[str, ...]
    source: str
    turns: deque[SpeakerTurn] = field(default_factory=lambda: deque(maxlen=MAX_TURNS_RETAINED))
    gm_enabled: bool = False
    gm_active_roles: set[str] = field(default_factory=set)
    turn_count_since_player: int = 0
    total_turns: int = 0
    last_gm_intervention_at: float = 0.0
    gm_intervention_count: int = 0
    pending_speakers: list[str] = field(default_factory=list)
    pending_coach_hints: dict[str, list[str]] = field(default_factory=dict)
    pending_system_infos: list[str] = field(default_factory=list)
    last_event_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    def recent_gm_turns(self) -> list[SpeakerTurn]:
        return [t for t in self.turns if t.is_gm_intervention][-MAX_GM_HISTORY_TAIL:]

    def consume_coach_hints(self, character_id: str) -> list[str]:
        if not character_id:
            return []
        hints = self.pending_coach_hints.pop(character_id, None) or []
        return list(hints)

    def push_coach_hint(self, character_id: str, hint: str) -> None:
        if not character_id or not hint:
            return
        self.pending_coach_hints.setdefault(character_id, []).append(hint)

    def append_pending_speaker(self, speaker_id: str) -> None:
        if speaker_id and speaker_id != "Player":
            self.pending_speakers.append(speaker_id)

    def next_pending_speaker(self) -> Optional[str]:
        return self.pending_speakers.pop(0) if self.pending_speakers else None

    def clear_pending(self) -> None:
        self.pending_speakers.clear()
        self.pending_system_infos.clear()


def _normalize_participants(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        value = [p.strip() for p in value.split(",") if p.strip()]
    if not isinstance(value, (list, tuple, set)):
        return tuple()
    out: list[str] = []
    seen: set[str] = set()
    for x in value:
        s = str(x or "").strip()
        if not s:
            continue
        if s.lower() == "player":
            continue
        if s in seen:
            continue
        out.append(s)
        seen.add(s)
    return tuple(sorted(out))


class ConversationSessionManager:
    _instance: Optional["ConversationSessionManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, ConversationSession] = {}
        self._by_key: dict[tuple[str, tuple[str, ...]], str] = {}

    @classmethod
    def instance(cls) -> "ConversationSessionManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_or_create(
        self,
        participants: Iterable[str],
        source: str = "unity",
        gm_enabled: Optional[bool] = None,
        gm_active_roles: Optional[set[str]] = None,
    ) -> ConversationSession:
        parts = _normalize_participants(participants)
        # Если флаги не заданы — берём из настроек
        if gm_active_roles is None or gm_enabled is None:
            try:
                from managers.settings_manager import SettingsManager
                if gm_enabled is None:
                    gm_enabled = bool(SettingsManager.get("GM_ENABLED", True))
                if gm_active_roles is None:
                    roles: set[str] = set()
                    for name in ("moderator", "narrator", "director", "coach"):
                        if bool(SettingsManager.get(f"GM_ROLE_{name.upper()}", name == "moderator")):
                            roles.add(name)
                    gm_active_roles = roles
            except Exception:
                gm_enabled = bool(gm_enabled)
                gm_active_roles = set(gm_active_roles or ())
        key = (source, parts)
        with self._lock:
            existing_sid = self._by_key.get(key)
            if existing_sid and existing_sid in self._sessions:
                sess = self._sessions[existing_sid]
                if gm_active_roles is not None:
                    sess.gm_active_roles = set(gm_active_roles)
                    sess.gm_enabled = gm_enabled or bool(gm_active_roles)
                return sess
            # «Похожий» состав — пересекается > 50% — переиспользуем, обновляя participants
            for (src, existing_parts), sid in list(self._by_key.items()):
                if src != source or sid not in self._sessions:
                    continue
                if not existing_parts or not parts:
                    continue
                overlap = len(set(existing_parts) & set(parts))
                threshold = max(1, len(existing_parts) // 2)
                if overlap >= threshold and abs(len(existing_parts) - len(parts)) <= 1:
                    sess = self._sessions[sid]
                    del self._by_key[(src, existing_parts)]
                    sess.participants = parts
                    self._by_key[(source, parts)] = sid
                    if gm_active_roles is not None:
                        sess.gm_active_roles = set(gm_active_roles)
                        sess.gm_enabled = gm_enabled or bool(gm_active_roles)
                    return sess
            # Создаём новую
            sid = uuid.uuid4().hex[:12]
            sess = ConversationSession(
                session_id=sid,
                participants=parts,
                source=source,
                gm_enabled=gm_enabled or bool(gm_active_roles),
                gm_active_roles=set(gm_active_roles or ()),
            )
            self._sessions[sid] = sess
            self._by_key[key] = sid
            logger.info(
                f"[ConversationSession] created sid={sid} source={source} participants={parts} "
                f"gm_enabled={sess.gm_enabled} roles={sess.gm_active_roles}"
            )
            return sess

    def get(self, session_id: str) -> Optional[ConversationSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> None:
        with self._lock:
            sess = self._sessions.pop(session_id, None)
            if not sess:
                return
            for k, sid in list(self._by_key.items()):
                if sid == session_id:
                    del self._by_key[k]
            logger.info(f"[ConversationSession] ended sid={session_id}")

    def end_for_source(self, source: str) -> None:
        with self._lock:
            for sid in [s for s, sess in self._sessions.items() if sess.source == source]:
                self.end_session(sid)

    def record_turn(
        self,
        session: ConversationSession,
        *,
        speaker_id: str,
        target_id: Optional[str],
        text: str,
        message_id: Optional[str] = None,
        is_gm_intervention: bool = False,
    ) -> SpeakerTurn:
        with self._lock:
            session.total_turns += 1
            if speaker_id == "Player":
                session.turn_count_since_player = 0
            elif not is_gm_intervention:
                session.turn_count_since_player += 1
            turn = SpeakerTurn(
                speaker_id=str(speaker_id),
                target_id=(str(target_id) if target_id else None),
                text=str(text or ""),
                turn_number=session.total_turns,
                timestamp=time.time(),
                message_id=message_id,
                is_gm_intervention=is_gm_intervention,
            )
            session.turns.append(turn)
            session.last_event_at = turn.timestamp
            if is_gm_intervention:
                session.last_gm_intervention_at = turn.timestamp
                session.gm_intervention_count += 1
            return turn

    # ── метрики ──────────────────────────────────────────────────────

    def silence_duration(self, session: ConversationSession) -> float:
        return max(0.0, time.time() - session.last_event_at)

    def repetition_score_ngram(self, session: ConversationSession, *, window: int = 6, n: int = 3) -> float:
        turns = [t for t in list(session.turns)[-window - 1:] if not t.is_gm_intervention and t.text]
        if len(turns) < 2:
            return 0.0
        last = turns[-1].text.lower()
        prev_texts = [t.text.lower() for t in turns[:-1]]

        def ngrams(s: str) -> set[str]:
            s = "".join(ch for ch in s if not ch.isspace())
            if len(s) < n:
                return {s} if s else set()
            return {s[i:i + n] for i in range(len(s) - n + 1)}

        last_ng = ngrams(last)
        if not last_ng:
            return 0.0
        best = 0.0
        for txt in prev_texts:
            other = ngrams(txt)
            if not other:
                continue
            inter = len(last_ng & other)
            union = len(last_ng | other)
            j = inter / union if union else 0.0
            if j > best:
                best = j
        return float(best)

    def repetition_score(self, session: ConversationSession, *, method: str = "auto") -> float:
        # Embedding-режим пока отложен (требует синхронного embedder). Auto = ngram fallback.
        return self.repetition_score_ngram(session)

    def loop_detected(self, session: ConversationSession, *, window: int, threshold: float) -> bool:
        turns = [t for t in list(session.turns)[-window:] if not t.is_gm_intervention and t.text]
        if len(turns) < window:
            return False
        # Считаем pairwise n-gram схожесть последних `window` реплик; если средняя > threshold — цикл.
        def ngrams(s: str, n: int = 3) -> set[str]:
            s = "".join(ch for ch in s.lower() if not ch.isspace())
            if len(s) < n:
                return {s} if s else set()
            return {s[i:i + n] for i in range(len(s) - n + 1)}

        sets = [ngrams(t.text) for t in turns]
        scores: list[float] = []
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                a, b = sets[i], sets[j]
                if not a or not b:
                    continue
                u = len(a | b)
                scores.append(len(a & b) / u if u else 0.0)
        if not scores:
            return False
        avg = sum(scores) / len(scores)
        return avg >= float(threshold)
