# Память запрошенных действий при подготовке и сжатии диалога

**Статус:** `CONDITIONAL` — функция включается `ENABLE_ACTION_MEMORY` (default false по `HistoryController._action_memory_enabled`). **Capabilities:** `CAP-ACTION-HISTORY-001—004`. **Области:** история, structured response, Unity, prompt context. Источник — сохранённые модели ответов, не прямой acknowledgement Unity.

## Зачем нужна

Когда LLM запрашивает анимацию, эмоцию, действие, костюм, движение и другие игровые команды через `structured_data`, обычный текст её реплики может не содержать ни одного из этих действий. Если сохранять в LLM-контексте только текст и summary, на следующем ходу персонаж может забыть, **какое действие было им запрошено**. Эта функция строит компактную производную текстовую проекцию requested actions, не переписывая сохранённое сообщение в SQLite.

Ключевое различие: **requested ≠ executed**. Python Core знает, что команда была предложена в structured ответе, но не обязательно знает, была ли она действительно выполнена Unity (`src/managers/action_memory.py:57-62,110-140`). Поэтому подача этих данных в LLM не должна выдавать команды за подтверждённое состояние игрового мира.

## Модель данных и поля

`requested_actions_from_structured(structured_data)` проходит `segments` и собирает записи из `emotions, animations, idle_animations, commands, movement_modes, visual_effects, clothes, music, interactions, face_params`, а также `start_game`, `end_game`, `intents[type,payload]`. Записи форматируются компактными строками; старые `Clothes:` и `ClothesColor` конвертируются в canonical outfit/recolor summary (`src/managers/action_memory.py:10-100`). Массив сериализуется в хронологическом порядке, payload intents — JSON с сортированными ключами.

| Отрезок истории | Где хранится факт | Как LLM узнаёт действие |
|---|---|---|
| Ещё в живом recent history | `assistant.structured_data` у конкретного сохранённого сообщения | В `_sanitize_history_for_llm()` к тексту этой же реплики добавляется `[REQUESTED ACTIONS THIS TURN]` (`src/controllers/history_controller.py:1822-1830`) |
| Уже вошёл в успешно применённый summary | `ACTION_MEMORY_RETAINED_REQUESTS` (персонажная переменная, JSON list) | `HistoryController._build_action_memory_context` создаёт отдельный `[RECENT ACTIONS BEFORE SUMMARY BOUNDARY]` (`src/controllers/history_controller.py:248-302`) |
| Сжатие не завершилось / не закоммитилось | исходные сообщения и предыдущий retained bridge | Очередное сжатие не должно автоматически заменять эту область; запись происходит только при применении результата (`src/controllers/history_controller.py:575-620,1325-1355`) |

Запись `retained_action_requests` выполняется вместе с обновлением summary text/count/anchor под character lock/epoch guard, затем сбрасываются переменные (`src/controllers/history_controller.py:1325-1355`). Сам building LLM-facing text не меняет сохранённые `structured_data` (`src/managers/action_memory.py:124-140`).

## Политика объёма

Настройка `ACTION_MEMORY_RETAIN_LAST` (default 4, допустимый диапазон 1–20) оставляет последние N записей при успешном сжатии. Дополнительные emergency caps — число записей (default80, 1–1000) и суммарные символы (default8000, 200–100000) на случай длительного отсутствия успешной компрессии (`src/controllers/history_controller.py:224-246`, `src/managers/action_memory.py:143-178`). При превышении сохраняется **самый новый хронологический хвост**, а не первые действия. Редукция размера prompt representation не эквивалентна удалению stored structured messages.

## User-visible сценарий

Игрок просит Миту поменять одежду и двигаться; LLM выдаёт structured запрос. На следующем ходу пока сообщение входит в live context, модель видит requested actions непосредственно при соответствующей реплике. После background summary прежний ход покидает окно, но короткий мост сохраняет последние requested actions. Это особенно важно для долгих разговоров с игровыми действиями и асинхронным Unity consumer.

## Требования и проверки

- `REQ-ACTION-HISTORY-001`: исходный structured ответ хранится отдельно от производной текстовой проекции LLM.
- `REQ-ACTION-HISTORY-002`: действия associate-ятся с конкретным assistant turn, имеют chronological ordering и не выдаются за подтверждённый Unity effect.
- `REQ-ACTION-HISTORY-003`: successful summary переносит только соответствующие requested actions через границу live/summary, не теряя scope персонажа.
- `REQ-ACTION-HISTORY-004`: bounded context сохраняет последние значимые действия при переполнении, а не произвольный набор.

Paritу fixtures (не запускались): multiple segments и intents, старая clothing-команда, утечка action info через saved content недопустима, обычная реплика без structured, summary commit/reject by epoch, две личности, disabled flag, new>old retention limit, memory window overflow и native tools history branch. Эти тесты — требования к проверке, не свидетельство текущего E2E.
