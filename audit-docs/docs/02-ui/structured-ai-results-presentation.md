# Визуализация structured AI results и сегментированных сообщений

**Capability:** `CAP-UI-CHAT-005` — `ACTIVE` при наличии structured output и включённого соответствующего UI-режима. **Статус inference effects:** эта страница документирует только отображение, не авторизацию и не применение команд. Evidence: `src/ui/chat/structured_panel.py`, `src/ui/chat/message_renderer.py`, `src/ui/settings/debug_settings.py` на срезе `CodeNow.zip` от 2026-10-30.

## Семантика

Structured AI response — не просто текст: итоговый structured payload содержит `segments`, числовые изменения `attitude_change/boredom_change/stress_change`, операции памяти, напоминания, таймеры, сущности/отношения графа и `tool_call`. Представление объясняет пользователю/отладчику содержимое, но его создание не означает, что последствия выполнены в Unity, памяти или инструменте.

`src/ui/chat/structured_panel.py:67-135` строит сегменты с labels нескольких действий (`emotions`, `animations`, `commands`, `movement_modes`, `visual_effects`, `clothes`, `music`, `interactions`, `face_params`, `intents`) и дополнительными `start_game/end_game/target/hint`. Memory/Reminder/Graph/ToolCall отдельные визуальные блоки (`structured_panel.py:137-237`). Сервисные значения числовых delta отображаются badge, `0` получает `±0` (`:46-65,267-274`).

## Режимы и user actions

- `SHOW_STRUCTURED_IN_GUI`: tri-state пользовательская настройка «Выкл/Кратко/JSON» (`src/ui/settings/debug_settings.py:43-60`). `STRUCTURED_EXPANDED_DEFAULT` определяет состояние раскрытия для обычной assistant bubble и stream attachment (`debug_settings.py:61-73`, `message_renderer.py:482-496,781-806`).
- `StructuredOutputPanel` умеет переключать collapsed/expanded нажатием на header (`structured_panel.py:238-289,323-326`). Краткий режим рендерит сегменты, tool call, memory actions, reminders/timers, graph; JSON режим рендерит `_raw_json` либо сериализованный payload как `PlainText` с выделением, чтобы JSON не интерпретировался как HTML (`:291-321`).
- `message_renderer.py:482-511` присоединяет structured panel к assistant-message, а сегменты группируются по target; при нескольких группах renderer делит их на несколько пузырей, добавляет подпись «speaker → target» и оставляет avatar на последнем элементе (`:513-530`). Это **presentation split**, не доказательство нескольких LLM turns.
- `message_renderer.py:781-828` для stream присоединяет structured panel к уже существующему bubble, с разветвлением multi-target; если stream widget отсутствует, quietly returns (`:785-788`). Отдельный role `structured` рендерится через `:346-369` и имеет **другую ветку feature check**, описано ниже.

## Обнаруженная неоднородность настроек

В обычной assistant bubble и streaming используется `_is_struct_off(mode)` для выключения (`message_renderer.py:141-181,482,783`). Однако branch `role == "structured"` проверяет `if not gui._get_setting("SHOW_STRUCTURED_IN_GUI", True)` (`:346-348`): строка `"Выкл"` **truthy**, поэтому отдельное сообщение с ролью `structured` может рендериться даже когда пользователь выбрал «Выкл», тогда как встроенный panel/stream скрыт. Это исходно подтверждённое расхождение predicates; его фактическая достижимость зависит от наличия событий с отдельной ролью `structured`. Не объявлять воспроизведённым UI bug без runtime fixture.

## Состояния, инварианты и риски

- Structured visual projection должна быть read-only и не выполнять изменяющие эффекты при повторном рендере/history replay.
- При смене локали режимы хранятся через локализованные значения `"Выкл"`, `"Кратко"` (также обработаны английские `"Off"`, `"Brief"` в renderer), а `"JSON"` одинаков. **Принцип нового функционального контракта:** stable режим `off/brief/json`, перевод только display label; это не решение о Rust UI framework.
- `_make_badge` ожидает числа и использует сравнения `>`, `<` (`structured_panel.py:46-65`). Для неожиданного string/non-numeric value UI может дать исключение; типизированная валидация на входе должна быть отдельным контрактом.
- `MemoryBlock`, `ReminderBlock`, `GraphBlock` обрабатывают списки различного формата, строки или dicts (`structured_panel.py:137-216`); семантика fallback для старых сохранений должна быть отдельной compatibility fixture.
- Группировка `target` не изменяет role/assistant-authoring semantics, но потенциально воздействует на копирование отдельных bubble, привязку `message_id`, regenerate/rating и replay. Эти downstream interactions не покрыты динамическими тестами.

## Требования к новой реализации

- `REQ-UI-STRUCT-001`: единая state semantics `off/brief/json`, одна проверка видимости независимо от отдельной `structured` role, assistant payload или streaming completion.
- `REQ-UI-STRUCT-002`: одно read-only представление typed structured data: tags/segments, tool call, memory/reminders/timers/graph и delta с JSON fallback без эффекта повторного применения.
- `REQ-UI-STRUCT-003`: одинаковое поведение для persisted history, live event и stream, включая разбиение multi-target и идентичность исходного сообщения.
- `REQ-UI-STRUCT-004`: validate numeric/object/list input и безопасный plain-text JSON/LLM-originated fields; сохранение полного `_raw_json`, когда он доступен.

## Граница будущей архитектуры

Можно менять GUI и модель представления, но нельзя переводить события управления игрой в «просто красивый текст» или выводить факт выполненных команд из наличия UI-визуализации. Application effects и structured **display** имеют независимый lifecycle. Нельзя копировать текущий прямой способ хранения Qt widgets в think block dictionary как обязательный паттерн.

## Validation backlog

Реально подать `structured` role при `SHOW_STRUCTURED_IN_GUI="Выкл"`; сравнить direct, live/stream and history; проверить malformed delta, dict/list legacy variants, multiple targets, смену персонажа и чистоту replay при remount.
