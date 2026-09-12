from decimal import Decimal, InvalidOperation
import re

from utils import _


GENERATION_FIELDS = {
    "temperature": dict(title=("Температура", "Temperature"), description=("Разнообразие ответов: ниже — предсказуемее, выше — свободнее.", "Response variety: lower is more predictable, higher is more varied."), setting="MODEL_TEMPERATURE", default="1.0", kind="float", minimum=0, maximum=2),
    "max_tokens": dict(title=("Макс. токенов", "Max tokens"), description=("Максимальная длина ответа в токенах.", "Maximum response length in tokens."), setting="MODEL_MAX_RESPONSE_TOKENS", default="2500", kind="int", minimum=1, maximum=None),
    "top_p": dict(title=("Top-P", "Top-P"), description=("Ограничивает выбор слов по суммарной вероятности.", "Limits word selection by cumulative probability."), setting="MODEL_TOP_P", default="1.0", kind="float", minimum=0, maximum=1),
    "top_k": dict(title=("Top-K", "Top-K"), description=("Число кандидатов при выборе следующего токена; 0 — без ограничения.", "Number of candidates for the next token; 0 means no limit."), setting="MODEL_TOP_K", default="0", kind="int", minimum=0, maximum=None),
    "presence_penalty": dict(title=("Штраф присутствия", "Presence penalty"), description=("Снижает вероятность повторного использования уже встречавшихся слов.", "Reduces reuse of words already present in the response."), setting="MODEL_PRESENCE_PENALTY", default="0.0", kind="float", minimum=-2, maximum=2),
    "frequency_penalty": dict(title=("Штраф частоты", "Frequency penalty"), description=("Снижает вероятность слов пропорционально числу их повторений.", "Penalizes words in proportion to how often they repeat."), setting="MODEL_FREQUENCY_PENALTY", default="0.0", kind="float", minimum=-2, maximum=2),
    "thinking_budget": dict(title=("Бюджет мышления", "Thinking budget"), description=("Лимит токенов размышления для поддерживаемых провайдеров.", "Reasoning token limit for supported providers."), setting="MODEL_THINKING_BUDGET", default="0", kind="int", minimum=0, maximum=None),
    "gemini_thinking_budget": dict(title=("Бюджет мышления Gemini", "Gemini thinking budget"), description=("Лимит токенов размышления: -1 — автоматически, 0 — отключить, если модель поддерживает.", "Reasoning token limit: -1 is automatic, 0 disables it when supported."), setting="GEMINI_THINKING_BUDGET", default="8192", kind="int", minimum=-1, maximum=None),
}


def field_error(key, text):
    spec = GENERATION_FIELDS[key]
    raw = str(text).strip()
    if not raw:
        return str(_("Введите значение.", "Enter a value."))
    if spec["kind"] == "int" and not re.fullmatch(r"[+-]?\d+", raw):
        return str(_("Требуется целое число.", "An integer is required."))
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return str(_("Требуется число.", "A number is required."))
    if not value.is_finite():
        return str(_("Требуется конечное число.", "A finite number is required."))
    low, high = spec["minimum"], spec["maximum"]
    if value < low or (high is not None and value > high):
        if high is None:
            return str(_("Минимум: ", "Minimum: ")) + str(low)
        return str(_("Диапазон: ", "Range: ")) + f"{low} … {high}"
    return ""


def field_default(view, key):
    spec = GENERATION_FIELDS[key]
    settings = getattr(view, "settings", None)
    value = settings.get(spec["setting"]) if settings is not None else None
    return str(value) if value is not None and not field_error(key, value) else spec["default"]


def validate_generation(view):
    valid = True
    for key, (enabled, field) in getattr(view, "gen_override_widgets", {}).items():
        if key not in GENERATION_FIELDS:
            continue
        error = field_error(key, field.text()) if enabled.isChecked() else ""
        invalid = bool(error)
        if field.property("invalid") != invalid:
            field.setProperty("invalid", invalid)
            field.style().unpolish(field)
            field.style().polish(field)
            field.update()
        field.setToolTip(error)
        valid = valid and not invalid
    return valid
