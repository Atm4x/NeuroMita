from __future__ import annotations

from utils.cognitive_effect_notes import build_cognitive_effect_notice


def _change(**overrides):
    value = {
        "change_id": "change-1",
        "sequence": 4,
        "instance_id": "instance-1",
        "id": "literalism",
        "effect_name": "Literalism",
        "kind": "effect_started",
        "subject_character_id": "Kind",
        "subject_label": "Kind",
        "notice_template": "",
    }
    value.update(overrides)
    return value


def test_default_notice_uses_first_person_for_subject() -> None:
    notice = build_cognitive_effect_notice("Kind", [_change()])

    assert notice is not None
    assert notice["role"] == "event"
    assert "[Cognitive Effect]" in notice["content"]
    assert "Ты чувствуешь" in notice["content"]
    assert "Literalism" in notice["content"]


def test_custom_template_can_hide_effect_details() -> None:
    notice = build_cognitive_effect_notice("Kind", [
        _change(notice_template="Ты ощущаешь необъяснимую перемену внутри.")
    ])

    assert notice is not None
    assert "необъяснимую перемену" in notice["content"]
    assert "Literalism" not in notice["content"]


def test_other_participant_gets_third_person_notice() -> None:
    notice = build_cognitive_effect_notice("Crazy", [_change()])

    assert notice is not None
    assert "В Kind что-то изменилось" in notice["content"]
    assert "её реакции" in notice["content"]
    assert "твои реакции" not in notice["content"]


def test_refresh_is_collapsed_when_intensity_changed_is_present() -> None:
    notice = build_cognitive_effect_notice("Kind", [
        _change(kind="effect_refreshed", sequence=5),
        _change(change_id="change-2", kind="effect_intensity_changed", sequence=6, intensity=0.8),
    ])

    assert notice is not None
    assert "остаётся внутри дольше" not in notice["content"]
    assert "0.80" in notice["content"]


def test_intensity_change_shows_previous_and_current_strength() -> None:
    notice = build_cognitive_effect_notice("Kind", [
        _change(kind="effect_intensity_changed", intensity=0.8, previous_intensity=0.4),
    ])

    assert notice is not None
    assert "0.40 → 0.80" in notice["content"]


def test_other_participant_awareness_notice_uses_third_person() -> None:
    notice = build_cognitive_effect_notice("Crazy", [
        _change(kind="effect_awareness_changed", awareness="investigating"),
    ])

    assert notice is not None
    assert "Kind иначе воспринимает" in notice["content"]
    assert "Ты иначе воспринимаешь" not in notice["content"]
