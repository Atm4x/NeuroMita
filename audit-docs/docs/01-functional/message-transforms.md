# Трансформации сообщений перед LLM: пользовательская функциональность и семантика

**Статус:** CONDITIONAL; pipeline активируется через capabilities/protocol preset. **Источник:** `src/handlers/llm_providers/message_transforms.py:8-445`; связанный `provider-configuration.md`. Static audit; реальный API не проверялся.

## Описание capability CAP-API-006

Пользователь может настраивать упорядоченный pipeline преобразований history/system/user/assistant messages для совместимости с конкретным API. Вход: список сообщений с мультимодальными `content`, возможными `tool_calls`, spec `[{id, params}, ...]`. Выход: новый список wire messages и trace `{id,params,before,after,changed}`; исходная доменная история не должна считаться автоматически преобразованной. Запускается в подготовке provider request, без самостоятельной сетевой операции. Важно фиксировать **порядок шагов**: преобразования некоммутативны.

## Пять фактически зарегистрированных шагов

| ID | Поведение | Реализация |
|---|---|---|
| `normalize_system_messages` | Leading system blocks объединяются; поздние system сохраняют позицию, но становятся user с `[SYSTEM INFO]` | `:193-248`, registry `:406-409` |
| `merge_system_messages` | Склеивает **только начальную непрерывную** последовательность system; поздние system не меняет | `:41-63`, `:410` |
| `ensure_last_message_user` | Добавляет dummy user (по умолчанию `.`) **только** если хвост `assistant`, либо при пустом списке | `:65-74`, `:411-413` |
| `system_to_user_prefix` | Извлекает все system messages и переносит их в первый user; при отсутствии user добавляет его в хвост. Поздние system теряют первоначальное положение | `:133-180`, `:414-416` |
| `ensure_alternating_roles` | Соседние одинаковые роли объединяет; строки склеивает `\n\n`, multimodal blocks конкатенирует; `tool_calls` объединяет списком | `:76-130`, `:417` |

`get_transform_catalog():402-403` возвращает metadata для UI. `apply_transforms():421-445` выполняет шаги по порядку, пропуская неизвестный ID с reason `unknown_transform`. `trailing_system_to_user_prefix():251-265` существует, но в `_TRANSFORMS` **не зарегистрирован**: отдельно ACTIVE не считать. Это важно для анализа reachability.

## Состояния, ошибки, edge cases

- `normalize_system_messages` сохраняет очередность позднего system относительно user/assistant, но меняет роль; leading strings и mixed blocks объединяются по-разному (`:228-248`).
- `system_to_user_prefix` редактирует первый подходящий user message и в случае списка — его content **in place**, а `apply_transforms` начинает с `list(messages)` (только поверхностная копия), поэтому возможна **мутация вложенного content первоначального запроса**. Это вывод из путей `:158-169` и `:425`; воспроизводящий тест ещё не запускался. Для новой реализации обязательна независимая wire-projection или контролируемая ownership-модель.
- `ensure_alternating_roles` сохраняет image blocks при объединении, но произвольные дополнительные поля второго message кроме `tool_calls` не сливаются (`:96-117`). Результаты с tool_call_id/role tool и нестроковым content требуют отдельного contract test.
- `changed` вычисляется сравнением агрегированных `count/roles/last_role/approx_text_chars`, а не полных payloads (`:19-38`, `:438-442`). Смена текста с сохранением длины может не отразиться в `changed`; **это не гарантия отсутствия модификации**.
- Unknown transforms не приводят к отказу: это существующее observable поведение config compatibility, но для будущего typed configuration можно потребовать явную диагностику.

## Новая спецификация и проверка

REQ-PROVIDER-006: хранить step identity и параметры независимо от GUI; сохранить порядок, модель role conversion и мультимодальные части; прозрачно отображать warnings/trace. REQ-PROVIDER-007: transformation не должна менять persisted conversation или input request; test fixtures обязаны покрывать leading+late system, images, tool calls, пустой список, неизвестную step, повторное применение и изменение без изменения summary.

**Возможная реорганизация:** не повторять Python `list[dict]` и текущие функции 1:1; выделить конечную wire projection из неизменяемой диалоговой модели с явно типизированными content parts и trace диагностиками. Конкретные Rust crates, composition и GUI на этапе аудита не выбираются.

## Открытые вопросы

Нужно проследить каждую caller location применяющей pipeline на уровне resolver до exact request snapshot; отдельно проверить место перед Gemini positioned-role normalization и поведение внешнего API с tool outputs. Требуется static+fixture test, сетевых тестов не было.
