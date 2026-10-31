# Post-DSL — пользовательские правила обработки ответа и debug-state

**Статус:** `ACTIVE` — создание интерпретатора и вызов из обработки текста; `CONDITIONAL` — реальные правила загружаются, только когда существует `PostScripts/main_rules.postscript`. **Capabilities:** `CAP-POSTDSL-001—004`. **Scope:** реактивные функции, не реализация parser на Rust.

## Пользовательская возможность

Автор prompt pack может задавать правила, которые при получении ответа LLM: 1) ищут текст, регулярное выражение или имя поля structured response, 2) вычисляют новые значения из match captures, 3) обновляют пользовательские параметры персонажа, 4) удаляют или заменяют фрагмент текста до отображения, 5) задают состав диагностических переменных интерфейса.

### Точки входа и порядок

1. При конструировании персонажа `PostDslInterpreter` загружает `PostScripts/main_rules.postscript` из базы персонажа (через `LocalPathResolver`); при отсутствии файла правила и debug-конфигурация пустые (`src/characters/character.py:165-174`, `src/DSL/post_dsl_engine.py:43-51,158-176`).
2. Для обычного text response: `Character.process_response_nlp_commands` вызывает `post_dsl_interpreter.process` **до** извлечения long-term memory, built-in behavior changes и игровых тегов (`src/characters/character.py:409-449`).
3. Для structured response: по каждому `segment.text` применяется text Post-DSL; затем выполняются встроенные операции `custom_params`; после этого `MATCH FIELD` Post-DSL обрабатывает `custom_fields` (`src/characters/character.py:526-631`). **Порядок имеет значение** при одинаковых переменных.
4. Для отображения отладочных переменных `Character.get_debug_variable_string` использует `DEBUG_DISPLAY` из Post-DSL, иначе показывает defaults Attitude/Boredom/Stress и дополнительные поля для Crazy (`src/characters/character.py:1180-1210`).

## Формат правил

| Конструкция | Значение | Source |
|---|---|---|
| `RULE name` … `END_RULE` | Именованное правило, последовательность правил сохраняется | `src/DSL/post_dsl_engine.py:69-123,150-156` |
| `MATCH TEXT "…"` | Буквальное совпадение в тексте | `92-107,352-374` |
| `MATCH REGEX "…" CAPTURE (a,b)` | Regex с передачей групп в выражения действий | `20-40,97-105,221-229,337-350` |
| `MATCH FIELD "field_name"` | Реакция на присутствующее custom structured поле | `106-107,308-320` |
| `ACTIONS` … `END_ACTIONS` | Последовательность `SET`, `SET LOCAL`, `LOG` и text match effects | `108-120,230-306` |
| `REMOVE_MATCH` | Убирает найденный фрагмент из ответа | `20-40,293-306` |
| `REPLACE_MATCH WITH expr` | Заменяет совпадение результатом выражения | `20-40,293-306` |
| `DEBUG_DISPLAY` … `END_DEBUG_DISPLAY` | Label→variable для отображения состояния персонажа | `125-148` |

`PostDslInterpreter.process()` проходит правила последовательно, трансформируя текущий текст; каждое следующее правило видит результат предыдущего (`322-376`). `process_structured_fields()` перебирает только FIELD-правила и передаёт текущее поле как вычислительный контекст (`308-320`).

## Вычисления, состояние и эффекты

Действия используют `safe_eval_expression`, а не произвольный `eval`. Доступны переменные персонажа, локальные переменные, named captures, `app_vars`; функция `default(name, fallback)` и ограниченный набор простых функций (`src/DSL/post_dsl_engine.py:178-209`). `SET` вызывает `character.set_variable`, кроме имён, ранее объявленных локальными; `SET LOCAL` меняет временное состояние интерпретатора (`230-282`). Локальные значения сбрасываются перед отдельной обработкой текста и перед обработкой структурированных полей (`308-325`).

Разница с основным DSL: Post-DSL применяется **после** генерации, может очистить видимые текстовые tags/формулы, изменить параметры по regex/structured field и формирует debug display. Основной DSL строит prompt и может seed memory/graph. Это две разные функциональные стороны системы авторских сценариев; их синтаксис/интерпретаторы не стоит автоматически объединять.

## Требования и проверки

- `REQ-POSTDSL-001`: трансформация текста выполняется в объявленном порядке и не теряет незатронутые фрагменты.
- `REQ-POSTDSL-002`: совпадения и structured fields могут детерминированно обновлять параметры заданного персонажа; именованные captures доступны последующим действиям.
- `REQ-POSTDSL-003`: расширяемый список debug-переменных не зависит от структуры GUI и имеет default при отсутствии файла конфигурации.
- `REQ-POSTDSL-004`: text transformation и field effects различаются по времени выполнения относительно built-in effects.

Future fixtures: literal/regex multiple matches, captured variables, order-dependent rules, replacement failure, no rules, structured field + built-in custom formula, two sequential turns, reload prompt pack, diagnostic labels. **Не выполнялись в этом проходе.**

**Открыто:** содержимое конкретных внешних `.postscript` отсутствует в исследуемом snapshot, следовательно реальный список пользовательских правил и совместимость с ранними prompt packs не установлен. Не объявлять конкретные правила обязательными функциями без файла/активного потребителя.
