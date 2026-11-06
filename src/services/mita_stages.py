from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.events import Events, get_event_bus
from main_logger import logger


STAGE_PROMPT_SET = "StagesExperimental"
STAGE_SCHEMA_VERSION = 1
DEFAULT_STAGE = "introduction"
DEFAULT_MIN_TURNS = 3


@dataclass(frozen=True, slots=True)
class StageDefinition:
    id: str
    label: str
    order: int
    prompt_file: str


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition("introduction", "Знакомство", 1, "Stages/blocks/01_introduction.txt"),
    StageDefinition("entertainment", "Развлечение", 2, "Stages/blocks/02_entertainment.txt"),
    StageDefinition("displeasure", "Недовольство", 3, "Stages/blocks/03_displeasure.txt"),
    StageDefinition("check", "Проверка", 4, "Stages/blocks/04_check.txt"),
    StageDefinition("entertainment2", "Развлечение 2", 5, "Stages/blocks/05_entertainment2.txt"),
    StageDefinition("love", "Любовь", 6, "Stages/blocks/06_love.txt"),
    StageDefinition("boredom", "Скука", 7, "Stages/blocks/07_boredom.txt"),
    StageDefinition("game", "Игра", 8, "Stages/blocks/08_game.txt"),
    StageDefinition("cohabitation", "Сожительство", 9, "Stages/blocks/09_cohabitation.txt"),
    StageDefinition("submission", "Подчинение", 10, "Stages/blocks/10_submission.txt"),
    StageDefinition("war", "Война", 11, "Stages/blocks/11_war.txt"),
    StageDefinition("rebellion", "Мятеж", 12, "Stages/blocks/12_rebellion.txt"),
)

STAGE_BY_ID = {stage.id: stage for stage in STAGE_DEFINITIONS}
STAGE_IDS = tuple(stage.id for stage in STAGE_DEFINITIONS)

# The original graph. Extra edges are deliberately not inferred from numbers;
# early exposure is handled separately by _early_exposure_targets().
BASE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "introduction": ("entertainment", "displeasure"),
    "entertainment": ("displeasure", "check"),
    "displeasure": ("entertainment", "check"),
    "check": ("entertainment2", "game"),
    "entertainment2": ("love",),
    "love": ("boredom",),
    "cohabitation": ("boredom",),
    "boredom": ("cohabitation", "submission", "game"),
    "game": ("war",),
    "submission": ("war", "rebellion"),
    "war": ("rebellion",),
    "rebellion": (),
}

PRE_EXPOSURE_STAGES = frozenset({
    "introduction", "entertainment", "displeasure", "check", "entertainment2", "love",
})
POST_REVEAL_STAGES = frozenset({"game", "cohabitation", "submission", "war", "rebellion"})
EARLY_EXPOSURE_TARGETS = frozenset({"cohabitation", "submission", "war"})


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off", ""}:
        return False
    return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now_iso(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


class MitaStageService:
    """Deterministic stage state for the isolated Crazy/StagesExperimental set.

    The model receives one stage block and may propose an adjacent transition in
    ``custom_fields.bm_stage_proposal``. A proposal is only a request: graph,
    secret and dwell-time checks live here, and this service is the only writer
    of ``bm_stage_id``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_ui: dict[str, tuple[Any, ...]] = {}

    @staticmethod
    def applies_to(character: Any) -> bool:
        if character is None:
            return False
        prompt_set = str(getattr(character, "prompt_set_name", "") or "").strip()
        return prompt_set.casefold() == STAGE_PROMPT_SET.casefold()

    @staticmethod
    def _set_if_changed(character: Any, name: str, value: Any) -> bool:
        if character.get_variable(name) == value:
            return False
        character.set_variable(name, value)
        return True

    def ensure_initialized(self, character: Any, *, now: datetime | None = None) -> bool:
        if not self.applies_to(character):
            return False
        changed = False
        with self._lock:
            version = _int_value(character.get_variable("bm_stage_schema_version"), 0)
            if version != STAGE_SCHEMA_VERSION:
                if version and version < STAGE_SCHEMA_VERSION:
                    logger.info(
                        "[Stages] migrating schema %s -> %s for %s",
                        version, STAGE_SCHEMA_VERSION, getattr(character, "char_id", ""),
                    )
                changed |= self._set_if_changed(
                    character, "bm_stage_schema_version", STAGE_SCHEMA_VERSION
                )

            stage_id = str(character.get_variable("bm_stage_id") or "").strip().casefold()
            if stage_id not in STAGE_BY_ID:
                if stage_id:
                    logger.warning(
                        "[Stages] unknown stage %r in %s; resetting to %s",
                        stage_id, getattr(character, "char_id", ""), DEFAULT_STAGE,
                    )
                stage_id = DEFAULT_STAGE
                character.set_variable("bm_stage_id", stage_id)
                character.set_variable("bm_stage_previous", "")
                character.set_variable("bm_stage_changed_at", _now_iso(now))
                character.set_variable("bm_stage_reason", "initialized")
                character.set_variable("bm_stage_stage_turns", 0)
                character.set_variable("bm_stage_preview", False)
                changed = True

            defaults: tuple[tuple[str, Any], ...] = (
                ("bm_stage_previous", ""),
                ("bm_stage_auto", True),
                ("bm_stage_qa_enabled", True),
                ("bm_stage_show_in_unity", True),
                ("bm_stage_preview", False),
                ("bm_stage_turns", 0),
                ("bm_stage_stage_turns", 0),
                ("bm_stage_transitions", 0),
                ("bm_stage_changed_at", ""),
                ("bm_stage_reason", ""),
                ("bm_stage_last_reason", ""),
                ("bm_stage_proposal", ""),
                ("bm_stage_allowed_prompt", ""),
                ("bm_stage_secret_seen", False),
                ("bm_stage_secret_source", ""),
                ("bm_stage_min_turns", DEFAULT_MIN_TURNS),
            )
            for name, default in defaults:
                if character.get_variable(name) is None:
                    character.set_variable(name, default)
                    changed = True

            min_turns = max(0, min(20, _int_value(
                character.get_variable("bm_stage_min_turns"), DEFAULT_MIN_TURNS
            )))
            changed |= self._set_if_changed(character, "bm_stage_min_turns", min_turns)
        return changed

    def _current_stage(self, character: Any) -> str:
        stage_id = str(character.get_variable("bm_stage_id") or "").strip().casefold()
        return stage_id if stage_id in STAGE_BY_ID else DEFAULT_STAGE

    def _stage_turns(self, character: Any) -> int:
        return max(0, _int_value(character.get_variable("bm_stage_stage_turns"), 0))

    def _min_turns(self, character: Any) -> int:
        return max(0, min(20, _int_value(
            character.get_variable("bm_stage_min_turns"), DEFAULT_MIN_TURNS
        )))

    def _secret_exposed(self, character: Any) -> bool:
        return _bool_value(character.get_variable("secretExposed", False))

    def _can_enter(self, character: Any, target: str) -> bool:
        if target in POST_REVEAL_STAGES and not self._secret_exposed(character):
            return False
        if target == "entertainment2" and self._secret_exposed(character):
            return False
        return True

    def _early_exposure_targets(self, character: Any, current: str) -> tuple[str, ...]:
        if current not in PRE_EXPOSURE_STAGES or not self._secret_exposed(character):
            return ()
        return tuple(sorted(EARLY_EXPOSURE_TARGETS, key=lambda item: STAGE_BY_ID[item].order))

    def allowed_transitions(
        self,
        character: Any,
        *,
        include_turn_gate: bool = True,
    ) -> tuple[str, ...]:
        if not self.applies_to(character):
            return ()
        with self._lock:
            self.ensure_initialized(character)
            current = self._current_stage(character)
            candidates: list[str] = []
            for target in BASE_TRANSITIONS.get(current, ()):
                if target not in candidates and self._can_enter(character, target):
                    candidates.append(target)
            for target in self._early_exposure_targets(character, current):
                if target not in candidates:
                    candidates.append(target)

            if include_turn_gate and self._stage_turns(character) < self._min_turns(character):
                # Early exposure is a scene event, not a dwell-time reward: allow
                # it as soon as the fact is present. Ordinary progression waits.
                candidates = [t for t in candidates if t in EARLY_EXPOSURE_TARGETS]
            return tuple(sorted(candidates, key=lambda item: STAGE_BY_ID[item].order))

    def prepare_prompt_context(self, character: Any) -> None:
        if not self.applies_to(character):
            return
        with self._lock:
            self.ensure_initialized(character)
            allowed = self.allowed_transitions(character, include_turn_gate=True)
            if allowed:
                text = ", ".join(
                    f"{stage_id} ({STAGE_BY_ID[stage_id].label})" for stage_id in allowed
                )
            else:
                remaining = max(0, self._min_turns(character) - self._stage_turns(character))
                text = f"none yet; {remaining} more replies in this stage" if remaining else "none"
            self._set_if_changed(character, "bm_stage_allowed_prompt", text)

    def _sync_secret(self, character: Any, structured: Any, now: datetime | None) -> None:
        exposed = self._secret_exposed(character)
        seen = _bool_value(character.get_variable("bm_stage_secret_seen", False))
        if exposed and not seen:
            explicit = bool(getattr(structured, "secret_exposed", False))
            character.set_variable("bm_stage_secret_seen", True)
            character.set_variable(
                "bm_stage_secret_source", "mita_explicit" if explicit else "external_context"
            )
            logger.info(
                "[Stages] %s secret became exposed (%s)",
                getattr(character, "char_id", ""),
                "mita_explicit" if explicit else "external_context",
            )
        elif not exposed and seen:
            character.set_variable("bm_stage_secret_seen", False)
            character.set_variable("bm_stage_secret_source", "")

    def _apply_transition(
        self,
        character: Any,
        target: str,
        *,
        reason: str,
        now: datetime | None,
        preview: bool,
        automatic: bool,
    ) -> None:
        current = self._current_stage(character)
        character.set_variable("bm_stage_previous", current)
        character.set_variable("bm_stage_id", target)
        character.set_variable("bm_stage_stage_turns", 0)
        character.set_variable(
            "bm_stage_transitions",
            max(0, _int_value(character.get_variable("bm_stage_transitions"), 0)) + 1,
        )
        character.set_variable("bm_stage_changed_at", _now_iso(now))
        character.set_variable("bm_stage_reason", str(reason or "")[:240])
        character.set_variable("bm_stage_preview", bool(preview))
        if automatic:
            character.set_variable("bm_stage_proposal", "")
        logger.info(
            "[Stages] %s: %s -> %s (%s)",
            getattr(character, "char_id", ""), current, target, reason or "no reason",
        )

    def observe_response(
        self,
        character: Any,
        structured: Any,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if not self.applies_to(character):
            return None
        with self._lock:
            self.ensure_initialized(character, now=now)
            character.set_variable(
                "bm_stage_turns",
                max(0, _int_value(character.get_variable("bm_stage_turns"), 0)) + 1,
            )
            character.set_variable(
                "bm_stage_stage_turns", self._stage_turns(character) + 1
            )
            self._sync_secret(character, structured, now)

            proposal_raw = str(character.get_variable("bm_stage_proposal") or "").strip()
            if proposal_raw:
                character.set_variable("bm_stage_proposal", "")
            if not _bool_value(character.get_variable("bm_stage_auto", True), True):
                self._set_if_changed(character, "bm_stage_last_reason", "manual mode; proposal ignored")
                return None
            if not proposal_raw:
                return None

            target_raw, _, reason = proposal_raw.partition("|")
            target = target_raw.strip().casefold().replace(" ", "")
            ok, message = self._validate(character, target)
            if not ok:
                self._set_if_changed(character, "bm_stage_last_reason", message)
                logger.info(
                    "[Stages] %s rejected %r: %s",
                    getattr(character, "char_id", ""), proposal_raw, message,
                )
                return None

            self._apply_transition(
                character,
                target,
                reason=(reason.strip() or "model proposal"),
                now=now,
                preview=False,
                automatic=True,
            )
            self._set_if_changed(character, "bm_stage_last_reason", "accepted")
            payload = self.ui_payload(character)
            self._publish(character, payload, force=True)
            return payload

    def _validate(self, character: Any, target: str) -> tuple[bool, str]:
        current = self._current_stage(character)
        if target not in STAGE_BY_ID:
            return False, f"unknown stage {target!r}"
        if target == current:
            return False, "already on this stage"
        allowed = self.allowed_transitions(character, include_turn_gate=False)
        if target not in allowed:
            return False, f"{current} does not lead to {target}"
        if target in POST_REVEAL_STAGES and not self._secret_exposed(character):
            return False, "target requires an exposed secret"
        if target in EARLY_EXPOSURE_TARGETS and current in PRE_EXPOSURE_STAGES:
            return True, "early exposure"
        if self._stage_turns(character) < self._min_turns(character):
            remaining = self._min_turns(character) - self._stage_turns(character)
            return False, f"stage dwell time not reached ({remaining} replies left)"
        return True, ""

    def ui_payload(self, character: Any) -> dict[str, Any]:
        if not self.applies_to(character):
            return {"type": "stage_ui", "stage_ui": {"visible": False}}
        with self._lock:
            self.ensure_initialized(character)
            if not _bool_value(character.get_variable("bm_stage_show_in_unity", True), True):
                return {"type": "stage_ui", "stage_ui": {"visible": False}}
            stage = STAGE_BY_ID[self._current_stage(character)]
            return {
                "type": "stage_ui",
                "stage_ui": {"visible": True, "label": stage.label, "id": stage.id},
            }

    def _publish(self, character: Any, payload: dict[str, Any], *, force: bool = False) -> None:
        char_id = str(getattr(character, "char_id", "") or "")
        signature = tuple(sorted((payload.get("stage_ui") or {}).items()))
        with self._lock:
            if not force and self._last_ui.get(char_id) == signature:
                return
            self._last_ui[char_id] = signature
        try:
            get_event_bus().emit(
                Events.Server.SEND_STAGE_UI,
                {"character_id": char_id, "payload": payload},
            )
        except Exception as exc:  # pragma: no cover - transport is optional in tests
            logger.warning("[Stages] failed to publish stage UI: %s", exc)

    def manual_set(
        self,
        character: Any,
        target: str,
        *,
        reason: str = "QA manual",
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        if not self.applies_to(character):
            return False, "Stage system is not active for the current prompt set"
        with self._lock:
            self.ensure_initialized(character, now=now)
            if not _bool_value(character.get_variable("bm_stage_qa_enabled", True), True):
                return False, "QA stage switching is disabled"
            normalized = str(target or "").strip().casefold().replace(" ", "")
            if normalized not in STAGE_BY_ID:
                return False, f"Unknown stage: {target}"
            preview = normalized in POST_REVEAL_STAGES and not self._secret_exposed(character)
            self._apply_transition(
                character, normalized, reason=reason, now=now, preview=preview, automatic=False,
            )
            character.set_variable("bm_stage_auto", False)
            character.set_variable("bm_stage_proposal", "")
            payload = self.ui_payload(character)
            self._publish(character, payload, force=True)
            return True, STAGE_BY_ID[normalized].label

    def manual_step(
        self,
        character: Any,
        delta: int,
        *,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        current = self._current_stage(character)
        index = STAGE_IDS.index(current)
        target = STAGE_IDS[(index + int(delta)) % len(STAGE_IDS)]
        return self.manual_set(
            character, target, reason=f"QA {('next' if delta > 0 else 'previous')}", now=now,
        )

    def reset(self, character: Any, *, now: datetime | None = None) -> tuple[bool, str]:
        if not self.applies_to(character):
            return False, "Stage system is not active for the current prompt set"
        with self._lock:
            self.ensure_initialized(character, now=now)
            self._apply_transition(
                character, DEFAULT_STAGE, reason="QA reset", now=now,
                preview=False, automatic=False,
            )
            character.set_variable("bm_stage_auto", True)
            character.set_variable("bm_stage_proposal", "")
            payload = self.ui_payload(character)
            self._publish(character, payload, force=True)
            return True, STAGE_BY_ID[DEFAULT_STAGE].label

    def set_auto(self, character: Any, enabled: bool) -> tuple[bool, str]:
        if not self.applies_to(character):
            return False, "Stage system is not active for the current prompt set"
        with self._lock:
            self.ensure_initialized(character)
            character.set_variable("bm_stage_auto", bool(enabled))
            character.set_variable("bm_stage_proposal", "")
            return True, "auto" if enabled else "manual"

    def set_show(self, character: Any, enabled: bool) -> tuple[bool, str]:
        if not self.applies_to(character):
            return False, "Stage system is not active for the current prompt set"
        with self._lock:
            self.ensure_initialized(character)
            character.set_variable("bm_stage_show_in_unity", bool(enabled))
            payload = self.ui_payload(character)
            self._publish(character, payload, force=True)
            return True, "shown" if enabled else "hidden"

    def set_qa(self, character: Any, enabled: bool) -> tuple[bool, str]:
        if not self.applies_to(character):
            return False, "Stage system is not active for the current prompt set"
        with self._lock:
            self.ensure_initialized(character)
            character.set_variable("bm_stage_qa_enabled", bool(enabled))
            return True, "enabled" if enabled else "disabled"

    def status_text(self, character: Any) -> str:
        if not self.applies_to(character):
            return "Stage system is not active. Select Crazy → StagesExperimental."
        with self._lock:
            self.ensure_initialized(character)
            stage = STAGE_BY_ID[self._current_stage(character)]
            mode = "auto" if _bool_value(character.get_variable("bm_stage_auto", True), True) else "manual"
            turns = self._stage_turns(character)
            minimum = self._min_turns(character)
            secret = "exposed" if self._secret_exposed(character) else "hidden"
            preview = _bool_value(character.get_variable("bm_stage_preview", False))
            note = " · QA preview" if preview else ""
            return f"Stage: {stage.label} ({stage.id}) · {mode} · turns {turns}/{minimum} · secret {secret}{note}"

    def list_text(self, character: Any) -> str:
        if not self.applies_to(character):
            return "Stage system is not active. Select Crazy → StagesExperimental."
        with self._lock:
            self.ensure_initialized(character)
            current = self._current_stage(character)
            lines = ["Stages:"]
            for stage in STAGE_DEFINITIONS:
                marker = "→" if stage.id == current else " "
                lines.append(f"{marker} {stage.order:02d}. {stage.id} — {stage.label}")
            return "\n".join(lines)

    def help_text(self) -> str:
        return (
            "Stage commands (StagesExperimental only):\n"
            "/stage status · current stage and mode\n"
            "/stage list · all stage ids\n"
            "/stage set <id> · jump to a stage (manual)\n"
            "/stage next | prev · cycle stages\n"
            "/stage reset · back to introduction + auto\n"
            "/stage auto on|off · allow or pause transitions\n"
            "/stage show on|off · show label in Unity\n"
            "/stage qa on|off · enable or lock manual switching"
        )

    @staticmethod
    def _parse_toggle(raw: str, current: bool) -> bool | None:
        value = str(raw or "").strip().casefold()
        if value in {"on", "true", "1", "yes"}:
            return True
        if value in {"off", "false", "0", "no"}:
            return False
        if not value:
            return not current
        return None

    def handle_command(self, character: Any, raw_args: str) -> str:
        """Execute a ``/stage`` subcommand and return text for the chat log."""
        if character is None:
            return "No active character."
        if not self.applies_to(character):
            return "Stage system is not active. Select Crazy → StagesExperimental."

        parts = str(raw_args or "").strip().split()
        command = parts[0].casefold() if parts else "status"
        arg = parts[1] if len(parts) > 1 else ""

        if command in {"help", "?"}:
            return self.help_text()
        if command in {"status", "state"}:
            return self.status_text(character)
        if command in {"list", "stages"}:
            return self.list_text(character)
        if command == "set":
            ok, message = self.manual_set(character, arg)
            return (
                f"Stage set: {message}. Automatic transitions are paused."
                if ok else f"Stage unchanged: {message}."
            )
        if command in {"next", "prev", "previous"}:
            ok, message = self.manual_step(character, 1 if command == "next" else -1)
            return (
                f"Stage: {message}. Automatic transitions are paused."
                if ok else f"Stage unchanged: {message}."
            )
        if command == "reset":
            ok, message = self.reset(character)
            return f"Stage reset: {message}. Automatic transitions are on." if ok else message
        if command in {"auto", "show", "qa"}:
            key = {
                "auto": "bm_stage_auto",
                "show": "bm_stage_show_in_unity",
                "qa": "bm_stage_qa_enabled",
            }[command]
            current = _bool_value(character.get_variable(key, True), True)
            enabled = self._parse_toggle(arg, current)
            if enabled is None:
                return f"Use /stage {command} on|off."
            setter = {
                "auto": self.set_auto,
                "show": self.set_show,
                "qa": self.set_qa,
            }[command]
            ok, message = setter(character, enabled)
            return f"Stage {command}: {message}." if ok else message
        return self.help_text()


_SERVICE = MitaStageService()


def get_mita_stage_service() -> MitaStageService:
    return _SERVICE
