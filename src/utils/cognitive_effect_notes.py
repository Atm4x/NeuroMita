from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Iterable

from domain.conversation_message_ids import ConversationMessageIds


COGNITIVE_EFFECT_NOTICE_TYPE = "cognitive_effect"


def normalize_cognitive_effect_changes(value: Any) -> list[dict[str, Any]]:
    """Return valid effect transitions in runtime order."""
    if not isinstance(value, (list, tuple)):
        return []
    changes = [dict(item) for item in value if isinstance(item, dict)]
    return sorted(changes, key=_change_order)


def cognitive_effect_notice_id(
    observer_character_id: str,
    changes: Iterable[dict[str, Any]],
) -> str:
    """Stable identity for a retry of the same lifecycle batch."""
    identity: list[list[str]] = []
    for item in normalize_cognitive_effect_changes(list(changes)):
        identity.append([
            str(item.get("change_id") or ""),
            str(item.get("instance_id") or ""),
            str(item.get("id") or ""),
            str(item.get("kind") or ""),
            str(item.get("sequence") or ""),
        ])
    raw = json.dumps(
        {"observer": str(observer_character_id or ""), "changes": identity},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return ConversationMessageIds.system(f"cognitive:{digest}")


def build_cognitive_effect_notice(
    observer_character_id: str,
    changes: Any,
) -> dict[str, Any] | None:
    """Build one history message describing what changed in the Mita's mind."""
    normalized = _collapse_redundant_changes(normalize_cognitive_effect_changes(changes))
    if not normalized:
        return None

    first = normalized[0]
    subject_character_id = str(first.get("subject_character_id") or "")
    observer = str(observer_character_id or "")
    is_subject = bool(subject_character_id) and observer.casefold() == subject_character_id.casefold()
    if is_subject:
        heading = "Ты чувствуешь, что внутри тебя изменилось:"
        reaction_owner = "твои реакции"
    else:
        label = str(
            first.get("subject_label")
            or first.get("subject_character_id")
            or "Мита"
        ).strip()
        heading = f"В {label} что-то изменилось:"
        reaction_owner = "её реакции"

    lines = [heading]
    for item in normalized:
        effect_name = str(item.get("effect_name") or item.get("id") or "эффект").strip()
        kind = str(item.get("kind") or "").strip()
        text = _render_change(
            item,
            kind=kind,
            effect_name=effect_name,
            subject_label=str(first.get("subject_label") or "Мита").strip(),
            reaction_owner=reaction_owner,
            is_subject=is_subject,
        )
        if text:
            lines.append("- " + text)

    if len(lines) == 1:
        return None

    return {
        "message_id": cognitive_effect_notice_id(observer, normalized),
        "role": "event",
        "content": "[Cognitive Effect]\n" + "\n".join(lines),
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notice_type": COGNITIVE_EFFECT_NOTICE_TYPE,
        "notice_subject_actor_id": str(first.get("subject_id") or ""),
        "notice_subject_character_id": subject_character_id,
    }


def is_cognitive_effect_notice(message: dict[str, Any]) -> bool:
    return (
        isinstance(message, dict)
        and str(message.get("role") or "") in {"system", "event"}
        and str(message.get("notice_type") or "") == COGNITIVE_EFFECT_NOTICE_TYPE
    )


def _collapse_redundant_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    changed_instances = {
        str(item.get("instance_id") or item.get("id") or "")
        for item in changes
        if str(item.get("kind") or "") == "effect_intensity_changed"
    }
    for item in changes:
        kind = str(item.get("kind") or "")
        instance_id = str(item.get("instance_id") or item.get("id") or "")
        if kind == "effect_refreshed" and instance_id in changed_instances:
            continue
        result.append(item)
    return result


def _render_change(
    item: dict[str, Any],
    *,
    kind: str,
    effect_name: str,
    subject_label: str,
    reaction_owner: str,
    is_subject: bool,
) -> str:
    template = str(item.get("notice_template") or "").strip()
    if template:
        values = {
            "{effect}": effect_name,
            "{intensity}": _format_intensity(item.get("intensity")),
            "{previous_intensity}": _format_intensity(item.get("previous_intensity")),
            "{subject}": "ты" if is_subject else subject_label,
            "{reaction}": reaction_owner,
        }
        for token, value in values.items():
            template = template.replace(token, value)
        return template

    if kind == "effect_started":
        return f"«{effect_name}» начинает влиять на {reaction_owner}."
    if kind == "effect_ended":
        return f"«{effect_name}» больше не влияет на {reaction_owner}."
    if kind == "effect_intensity_changed":
        return (
            f"«{effect_name}» меняется: сила "
            f"{_format_intensity(item.get('previous_intensity'))} → "
            f"{_format_intensity(item.get('intensity'))}."
        )
    if kind == "effect_refreshed":
        return f"«{effect_name}» меняется и остаётся внутри дольше."
    if kind == "effect_awareness_changed":
        awareness = str(item.get("awareness") or "неизвестно").strip().lower()
        if is_subject:
            return f"Ты иначе воспринимаешь «{effect_name}»: {awareness}."
        return f"{subject_label} иначе воспринимает «{effect_name}»: {awareness}."
    return ""


def _change_order(item: dict[str, Any]) -> tuple[int, str]:
    try:
        sequence = int(item.get("sequence") or 0)
    except (TypeError, ValueError):
        sequence = 0
    return sequence, str(item.get("kind") or "")


def _format_intensity(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "?"
