# Напоминания и автономные таймеры

**Capability:** `CAP-SCHEDULE-001`. **Статус:** CONDITIONAL: REMINDERS_ENABLED. **Источники:** `src/managers/reminder_manager.py:28 ReminderManager`, `:164 add_reminder`, `:192 add_timer`, `:218 get_due_reminders`; `src/controllers/reminder_controller.py:12 ReminderController`; Character structured reminder operations; MainController reminder registration/factory.

## Назначение и сценарий

Сохранить будущую задачу персонажа, дождаться срока и инициировать реплику/действие через обычный dialogue pipeline. Два вида: reminder с датой и timer с положительной задержкой. Источники — model structured output и reminder tool; их entry→mutation пути уточнены в Pass 13 ниже. Live GUI/network/scheduler E2E не выполнялся.

## Данные и хранение

На персонажа JSON Histories/{character_id}/{character_id}_reminders.json: list N/text/due_iso/created_iso/kind. State lazy-loaded, ids max N+1. Запись sibling temp+flush/fsync+os.replace. `_save_state` ловит ошибку и не возвращает failure; in-memory add/delete и notification могут считаться успешными после disk failure. Corrupt read очищает in-memory list с error log; quarantine не обнаружен.

add_reminder валидирует fromisoformat, kind нормализует reminder/timer; text отдельно не ограничивает. add_timer требует finite positive float и вычисляет local datetime deadline с microseconds. Timezone-aware due_iso может распарситься, но сравнивается с naive now; due query ловит exception и пропускает record. Политика timezone должна быть явной в новой реализации.

## Scheduler и ownership

ReminderController владеет supervised thread, stop/wake events и subscriptions на schedule/activity changes. Обходит all_ids registry и получает reminder resources без обязательной materialization, если передан CharacterResourceManager. Ближайший due определяет sleep; отсутствие/overdue — fallback 30 s. Schedule change будит ожидание, завершение generation будит deferred timer.

На сроке проверяет active_generation_count(character)>0 и откладывает, если персонаж занят. Затем try_emit SEND_MESSAGE с user_input пустым, system_input `[Timer fired] ...` либо `[Reminder] ...`, event_type timer/reminder. При bus acceptance reminder сразу dismiss-ится. Bus acceptance не означает generation admission или successful commit: при downstream queue saturation/ошибке событие уже могло быть удалено из расписания. Это текущая граница delivery guarantee.

В wake loop `_wake_event.clear()` выполняется до расчёта deadline; потерю wake между предыдущей проверкой и clear следует оценивать отдельно. Shutdown ставит stop/wake, закрывает subscriptions и join до 2 s. Runtime feature manager выключает scheduler при setting disabled, persisted records остаются.

## UI и эффекты

Pending reminders включаются в prompt персонажа, N используется для удаления. Fire может вызвать LLM, history write, TTS и game actions согласно обычной policy. Dismiss физически убирает record из списка. Character.clear_history в просмотренном методе не вызывает clear_reminders; слово «очистка истории» не означает очистку расписания.

## Требования и альтернативы

Развести scheduled→claimed→admitted→completed/failed, определить restart/due-overdue semantics, timezone, duplicate firing и retry policy. Не обещать exactly-once от atomic JSON replace. Typed time/deadline и owned scheduler могут реализовываться event loop либо отдельной task; выбор Rust timer library отложен. Persisted reminder и ephemeral working-state имеют разные lifetimes.

## Pass 13: tool, structured effects и prompt projection

Источники дочитаны: `managers/tools/builtin/reminder_tool.py` целиком; `characters/character.py:746–784`; `services/structured_response_capabilities.py:197–202`; `model_controller.py:1489`; `prompt_controller.py:541–544`; `main_controller.py:424–427,554+`; model interaction settings tool descriptor.

| Entry | Вход и результат | Scope / ошибка |
|---|---|---|
| Tool list | action=list → formatted pending list либо «Нет активных напоминаний» | CharacterRegistry получает захваченный tool char_id; без reminder resource возвращается строка ошибки |
| Tool add | text + due → собственный RU/EN parser → local datetime ISO seconds → add_reminder → номер N и текст подтверждения | Missing text/due и unparsed date возвращают tool result с диагностикой; mutation exception также превращается в текст |
| Tool timer | instruction + delay_seconds → float → add_timer; возвращает N и задержку | Manager требует finite positive delay; type/value failures имеют отдельную диагностику |
| Tool delete | n → int → delete_reminder; distinguishes deleted/not found | Нет N → диагностическая строка; int conversion не обёрнута локальным try этой ветки, общий tool error policy отдельно |
| Structured reminder_add | Каждая строка `due_iso|text`, split только по первому `|` → add_reminder | Не использует natural-language `_parse_due`; missing delimiter пропускается с warning; ошибки каждой записи логируются отдельно |
| Structured timer_add | Каждая строка `delay_seconds|instruction` → float → add_timer | Та же per-entry изоляция; это autonomous future turn, не sleep внутри генерации |
| Structured reminder_delete | Цифровые строки → delete_reminder(int) | Нецелые/отрицательные строковые формы не принимаются этой проверкой; результат not found отдельно в логике эффекта не отображается |

Friendly date parser реализован собственным Python кодом, не dateutil: RU «через N секунд/минут/часов/дней/недель», фиксированный месяц=30 дней, полчаса/час/неделя; EN in N seconds/minutes/hours/days/weeks, in an hour, tomorrow; RU сегодня/завтра с часами и ISO с минутами/секундами/только датой. Это конечный набор regex/strptime, **не универсальное распознавание естественных дат**. Порядок fullmatch-or-search и пересекающиеся слова требуют corpus checks (например, «завтра» внутри более длинного слова); желаемую точность новой системы нельзя выводить из перечисления patterns.

Tool доступен по TOOLS_ON/per-tool gate и `REMINDERS_ENABLED`; ModelController исключает его при выключенных reminders. MainController этим же reminder flag управляет scheduler optional feature. Structured capability policy исключает reminder_add/reminder_delete/timer_add, когда flag выключен. Tool checkbox в model interaction settings включает именно TOOL_ENABLED_reminder; не заменяет общий scheduler/tool gate.

Pending list добавляется PromptController в volatile system context текущего character отдельно от памяти. В найденном fragment этот блок сам не проверяет REMINDERS_ENABLED: остановка scheduler и исчезновение ранее сохранённых записей из всех представлений не равнозначны. Standalone GUI список с ручным reminder CRUD при данном source review не подтверждён; не добавлять его в обязательный parity только по наличию tool checkbox.

`REQ-SCHEDULE-INPUT-001`: различать tool natural-language due, structured ISO due и numeric timer; ошибки, local timezone, character scope и неизвестный action должны быть частью контракта. Будущие проверки: каждый action, malformed/aware dates, disabled scheduler с уже сохранёнными reminders, restart overdue, busy character и downstream admission failure. Source paths описаны, эти проверки в Pass 13 не исполнялись.
