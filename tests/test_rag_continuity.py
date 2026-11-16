import pytest

from services.rag_continuity import is_followup


@pytest.mark.parametrize("query", [
    "Я хочу, чтобы ты рассказал мне подробности этой истории.",
    "А потом?", "Почему она так сделала?", "Tell me more", "What happened next?",
    "Это должно быть воспоминание о нем. Что еще ты помнишь?",
])
def test_followups_need_the_previous_subject(query):
    assert is_followup(query)


@pytest.mark.parametrize("query", [
    "Расскажи подробнее о Кепочке", "Что ты сделала с Милой?", "Включи музыку", "Mila visited you?",
])
def test_explicit_subjects_do_not_borrow_another_character_topic(query):
    assert not is_followup(query)


def test_mila_declension_is_an_entity_not_an_anonymous_followup():
    from managers.rag.rag_utils import entity_alias_phrases
    assert "Mila" in entity_alias_phrases("Расскажи подробнее о Милой")
    assert not is_followup("Расскажи подробнее о Милой")
