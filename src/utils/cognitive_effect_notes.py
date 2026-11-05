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


def cognitive_effect_change_ids(message: Any) -> set[str]:
    """Return lifecycle IDs already represented by one history message."""
    if not isinstance(message, dict):
        return set()
    values = message.get("cognitive_effect_change_ids")
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {str(value).strip() for value in values if str(value or "").strip()}


def build_cognitive_effect_notice(
    observer_character_id: str,
    changes: Any,
    *,
    seen_change_ids: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    """Build one history message describing what changed in the Mita's mind."""
    normalized = _collapse_redundant_changes(normalize_cognitive_effect_changes(changes))
    seen = {str(value).strip() for value in (seen_change_ids or ()) if str(value or "").strip()}
    if seen:
        normalized = [
            item for item in normalized
            if not str(item.get("change_id") or "").strip()
            or str(item.get("change_id") or "").strip() not in seen
        ]
    if not normalized:
        return None

    first = normalized[0]
    subject_character_id = str(first.get("subject_character_id") or "")
    observer = str(observer_character_id or "")
    recorded_observer = str(first.get("observer_character_id") or observer)
    is_subject = bool(first.get("observer_is_subject")) or (
        bool(subject_character_id) and recorded_observer.casefold() == subject_character_id.casefold()
    )
    is_mutual_other = (
        str(first.get("direction") or "").strip().lower() == "mutual"
        and bool(first.get("observer_is_affected", True))
        and not is_subject
    )
    counterpart = str(
        first.get("counterpart_character_id")
        or first.get("other_character_id")
        or first.get("other_id")
        or "другой участник"
    ).strip()
    if is_subject:
        heading = "Ты чувствуешь, что внутри тебя изменилось:"
        reaction_owner = "твои реакции"
    elif is_mutual_other:
        heading = f"Ты чувствуешь, что ваша связь с {counterpart} изменилась:"
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
    rendered_changes: list[tuple[str, int]] = []
    rendered_indexes: dict[str, int] = {}
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
            is_mutual_other=is_mutual_other,
        )
        if text:
            if text in rendered_indexes:
                index = rendered_indexes[text]
                rendered_changes[index] = (text, rendered_changes[index][1] + 1)
            else:
                rendered_indexes[text] = len(rendered_changes)
                rendered_changes.append((text, 1))

    for text, count in rendered_changes:
        lines.append("- " + text + (f" (×{count})" if count > 1 else ""))

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
        "cognitive_effect_change_ids": [
            str(item.get("change_id") or "").strip()
            for item in normalized
            if str(item.get("change_id") or "").strip()
        ],
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
    is_mutual_other: bool,
) -> str:
    template = str(item.get("notice_template") or "").strip()
    if template:
        values = {
            "{effect}": effect_name,
            "{intensity}": _format_intensity(item.get("intensity")),
            "{previous_intensity}": _format_intensity(item.get("previous_intensity")),
            "{subject}": "ты" if is_subject or is_mutual_other else subject_label,
            "{reaction}": reaction_owner,
        }
        for token, value in values.items():
            template = template.replace(token, value)
        return template

    awareness = str(item.get("awareness") or "").strip().lower()
    identifies_effect = awareness in {"investigating", "adapting", "resisting"}
    remembers_change = is_subject or is_mutual_other

    if not identifies_effect and awareness in {"unaware", "noticing"}:
        if kind == "effect_started":
            return (
                "Ты замечаешь, что твои реакции стали необычными, но не понимаешь почему."
                if awareness == "noticing"
                else "Что-то неуловимо меняет твои реакции; причина пока не ясна."
            )
        if kind == "effect_ended":
            return "Необычное изменение проходит, и твои реакции постепенно возвращаются к прежним."
        if kind == "effect_intensity_changed":
            return (
                "Сила необычного изменения внутри тебя "
                f"{_format_intensity(item.get('previous_intensity'))} → "
                f"{_format_intensity(item.get('intensity'))}."
            )
        if kind == "effect_refreshed":
            return "Необычное состояние внутри тебя становится устойчивее."

    if kind == "effect_awareness_changed":
        awareness = str(item.get("awareness") or "неизвестно").strip().lower()
        if identifies_effect:
            return (
                f"Ты понимаешь, что причина перемены — «{effect_name}»."
                if remembers_change
                else f"{subject_label} понимает, что причина перемены — «{effect_name}»."
            )
        if awareness == "noticing":
            return "Ты начинаешь замечать необычную перемену в своих реакциях."
        if awareness == "unaware":
            return "Ощущение необычности становится слабее."

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
        if remembers_change:
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
