# Структурированные ответы: состояния персонажа, команды и игровые действия

**Статус:** `ACTIVE` для контракта structured response и локальных эффектов; `CONDITIONAL` для запуска мини-игр, инструментов, RAG/graph, Unity-команд и специальных полей. **Ревизия:** локальный snapshot Python `CodeNow.zip`, исторически помеченный как `releases / 38172493` в предыдущем аудите; git metadata в архиве нет, идентичность SHA здесь независимо не проверена. **Назначение:** описание *поведения* и границ локальных/игровых побочных эффектов, а не перенос `Character` как Rust-класса.

## 1. Модель результата

`src/schemas/structured_response.py:260-365,378-474` определяет ответ как упорядоченные `segments` и глобальные поля. Каждый сегмент содержит произносимый `text`, optional addressee `target`, `hint`, `allow_sleep`, списки команд `emotions`, `animations`, `idle_animations`, `commands`, `movement_modes`, `visual_effects`, `clothes`, `music`, `interactions`, `face_params`; может запускать/завершать игру (`start_game`/`end_game`) и передавать произвольные `intents` вида `{type, payload}`. Это **позиционные действия**, связанные с последовательностью фрагментов ответа; их нельзя заменять одним unordered map состояния.

Глобальные поля: `attitude_change`, `boredom_change`, `stress_change`; `secret_exposed`; CRUD/merge долгосрочной памяти; создание/удаление reminders, создание автономных timers; `entities`/`relations` графа; `tool_call`; `custom_fields` персонажа; `working_state`; скрытые `reasoning` и `image_description`. `ResponseSegment.target` — адресат речи среди участников диалога, **не** target Unity-object и **не** поле команды. `SegmentIntent` принимает любой непустой тип, без жёсткого списка допустимых game intents на Python-границе: исполнение конкретного типа делегируется Unity. Для inventory-type строковый payload нормализуется в `{object: name}`, неподходящий payload превращается в `{}` (`structured_response.py:260-366`).

`RESPONSE_PROTOCOL_VERSION=3` (`structured_response.py:30-34`); `src/controllers/chat_controller.py:1208-1235` формирует task response с `response_protocol_version`, текстом, сегментами, некоторыми глобальными полями, `structured_parse_level` и `control_plane_trusted`. Не путать `task result` с full Pydantic/schema object и persistent history: это различные проекции.

## 2. От входа до эффектов

1. Provider output парсится в structured object, затем request-specific capability profile санитизирует запрещённые поля (`src/controllers/model_controller.py:2251-2275`; `services/structured_response_capabilities.py:123-140,171-253`). `ENABLE_GAMES=false` удаляет `start_game/end_game` из segment schema, RAG+GRAPH gate управляет entity/relation, `REMINDERS_ENABLED` — reminders/timer, tools gate — tool_call, `secret_capable/secret_revealed` — secret, а `ENABLE_WORKING_STATE` — перенос краткого состояния на следующий ход. Runtime capabilities также запрещают отдельные Unity-поля.
2. Под per-character lock применяется `Character.process_structured_response`, затем сбрасываются переменные и формируется voice profile (`model_controller.py:2278-2293`). Локальный порядок: инкремент счётчика ходов/обновление app vars → изменения трёх статистик → memory operations → reminder/timer operations → start/stop мини-игры и её команды → PostDSL для текста каждого сегмента → custom-field updates → PostDSL field rules (`characters/character.py:462-635`). Исключения в большинстве групп перехватываются отдельно; нельзя трактовать группу изменений как единую атомарную транзакцию.
3. Если ответ просит tool call, управление переходит в tool chain; ранее выполненные локальные изменения не отменяются. `working_state` финализируется только при окончательном ответе, не на промежуточном tool step (`model_controller.py:2294-2356`).
4. Финальный ответ преобразуется в `result_dict`, его текст и `structured_data` могут записываться в историю; `working_state` удаляется из UI/task/persisted projection, `_raw_json` доступен для debug, но не становится обычным видимым ответом (`model_controller.py:2374-2439`). `MESSAGE_COMPLETED` содержит текст, memory IDs, optional inline graph payload и отправляется подписчикам (`:2450-2477`).
5. `ChatController` преобразует результат в task status, UI events и game-facing result (`chat_controller.py:773-1013,1208-1235`). Для GameMaster существует отдельная обработка `dialogue.send_system_message` и `dialogue.broadcast_system_message`, сохранение explicit directive на соответствующем пути (`:805-869`). Это частный control-plane сценарий; обычные сегменты нельзя автоматически трактовать как GameMaster directives.

## 3. Что изменяется локально, что только запрашивается

| Семейство результата | Фактическая область эффекта | Статус исполнения |
|---|---|---|
| Statistics/custom fields/secret | локальные переменные и состояние персонажа | результат изменения при применении к Character; ограничения по min/max и formula |
| Memory CRUD/merge | memory storage / derived indexing | вызываются операции character memory; отдельное состояние последующей индексации |
| Reminders/timers | планировщик персонажа, persisted reminders и autonomous follow-up | локальный side effect уже в этом ходе |
| Mini-games (`start_game`, `end_game`, часть `commands`) | `GameManager` и GUI мини-игры | локальная попытка запуска/завершения; зависит от настройки/идентификатора/текущей игры |
| Unity segment lists и `intents` | Unity task/segment consumer | **запрос** на действие, не подтверждение фактического исполнения Unity |
| `entities`/`relations` | graph extraction event | event side effect, а не синхронная гарантия построенного графа |
| `tool_call` | выбранный builtin tool + follow-up LLM | отдельная цепочка с лимитом глубины и возможными необратимыми side effects |
| `working_state` | краткое состояние следующего хода | финальный invisible handoff, не long-term memory |

`src/managers/action_memory.py:8-110` выводит из уже сохранённых сегментов *requested actions* (`emotion`, `animation`, `outfit`, `intent`, `start_game` и т.п.) для следующего контекста. Это не авторитетный Unity receipt; код прямо квалифицирует действия как *requested* и обрезает старые records только защитным cap. Система summary должна различать прошлую просьбу об эффекте и подтверждённое состояние игрового мира.

## 4. Состояния и границы

- `attitude/boredom/stress`: значение по умолчанию и ограничение на величину изменения задаются `Character._adjust_bounded_stat`; delta round2, hard cap `STAT_CHANGE_HARD_LIMIT` (default 6), собственные `_min/_max` (default 0–100), затем запись переменной (`characters/character.py:1218-1285`). Per-turn model-prompt recommendations не заменяют runtime clamp.
- `custom_fields` поддерживает `add`, `set` и безопасно ограниченную формулу; порядок clamp входа → max per-turn add → formula/op → clamp конечного значения (`characters/character.py:536-635`); отдельные формальные детали в `character-custom-fields-and-formula-policy.md`.
- `secret_exposed` формально присутствует, только если персонаж может раскрыть секрет и не раскрыл его. Конкретная обработка является character-specific; не обобщать для всех персонажей без реестра overrides (`structured_response_capabilities.py:220-225`; поиск special implementations остаётся задачей).
- У мини-игры есть два кодовых ingress: новые structured `start_game/end_game` и старые текстовые теги `<StartGame>/<EndGame>` (`characters/character.py:786-834`). `characters/character.py:409-460` сохраняет отдельный legacy text-processing pipeline; его production reachability нужно учитывать только после call-graph подтверждения, а не по наличию функции.
- Команды игры из `segments.commands` передаются активной мини-игре только при `playingGame`; обычные Unity-related сегментные поля не исполняются в этой функции Python (`characters/character.py:786-802`).

## 5. Функциональные требования для нового Rust Core (без выбора архитектуры)

- Поддерживать ordered segments с позиционными действиями и явно различать `visible text`, `internal state handoff`, `Core side effect`, `requested game action` и `confirmed world state`.
- Сохранять семантику глобальных character deltas, custom fields, memory, reminder/timer, мини-игр и графовых events. Никакой Python-классовой композиции из этих фактов не следует.
- Иметь request-specific feature gate / schema capabilities, сохранять безопасность обработки неполных intents и provider-specific schema representations.
- Эксплицитно сохранять личность персонажа, conversation/task IDs, request outcome/parse trust и корректные границы emission/commit.
- Проверять будущим parity fixture: сегментное упорядочение, serialisation task response v3, local effects vs Unity requests, `target`, tool continuation, feature gates, memory/timer side effects, summary action projection.

**Открыто:** точный Unity-side executor/ack contract не подтверждён этим Python snapshot; подробный реестр character-specific overrides и legacy text path production reachability требует отдельного прохода. **Уверенность:** CONFIRMED для перечисленных Python branches; UNKNOWN для фактического выполнения игровых команд клиентом Unity. Библиотеки Rust не выбирались.
