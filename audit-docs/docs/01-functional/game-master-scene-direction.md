# GameMaster: управление групповой сценой и границы действующего функционала

**Назначение.** Разобрать игровую роль GameMaster как функцию скрытого руководства сценой, не приравнивая найденные экспериментальные классы к реально исполняемому production-пути. Отдельно рассматриваются: (A) подтверждённый путь Unity task → GameMaster generation → structured intent; (B) созданная, но пока не найденная в составе production composition реализация временных правил сцены.

## CAP-GM-001 — скрытая директива GameMaster через Unity

**Статус:** **ACTIVE/CONDITIONAL** — путь обработки `game_master_observe`/`game_master_command` зарегистрирован, фактический выпуск периодических observe зависит от Unity settings и наличия событий. **Источники:** `src/game_connections/handlers/actions/create_task.py:542-588`; `src/core/request_policy.py:75-91`; `src/controllers/chat_controller.py:553-560,784-928`; `src/controllers/prompt_controller.py:848-865,910-925,1218-1257`; `src/controllers/server_controller.py:458-481`; `src/controllers/model_controller.py:1375-1390`.

**Назначение и сценарии:** GameMaster — отдельная системная роль, способная наблюдать групповое общение и выдавать правила поведения персонажам. Это не ещё один обычный говорящий участник Mita-to-Mita цепочки. Unity может прислать периодическое наблюдение или явную команду режиссёра.

**Вход:** тип события; `req_id`; актуальные `participants`, `game_state`, character stats; явная `command`/`instruction`/`message` (для `game_master_command` не может быть пустой); системное задание из настроек `GM_SMALL_PROMPT` либо инструкций тестирования.

**Последовательность:**

1. Сервер Unity создаёт задачу от `GameMaster` с `sender=GameMaster`, `user_input=""`, `system_input=<command or fallback instruction>` и отдельной `RequestPolicy`.
2. Для GameMaster `ChatController` независимо пересчитывает policy вместо доверия внешнему policy payload. Prompt builder добавляет `[GAME_MASTER_TASK]`, предлагающий выдать `dialogue.send_system_message` с целевым персонажем и текстом директивы.
3. При получении генерации structured segments обрабатываются как семантические игровые действия; обычное сообщение GM не становится очередным ходом NPC в автоматическом диалоге.
4. Если было явно доверенное user/test задание, но модель не выдала применимую директиву, специальный ветвящийся путь может создать системный intent на основе самой инструкции. Это отдельное trusted control plane поведение, не общее правило преобразования всех пользовательских текстов в команды.
5. Unity во входящих `runtime_events` может вернуть след исполнения вида `[GAME_MASTER]: GameMaster said: ...`. `PromptController` отделяет его от обычных событий и передаёт отвечающему персонажу поздним `[GAME_MASTER_DIRECTIVE][MANDATORY]` на следующий ход, чтобы персонаж реагировал естественно и не цитировал скрытый источник.

**Выход и side effects:** штатный task status/structured intents, потенциальная игровая команда на стороне Unity, опциональная озвучка GM при `GM_VOICE`. Пустой видимый текст допустим, когда ответ состоит из игровых сегментов. Гарантии успешного исполнения зависят от Unity intent executor и ответа задачи, а не только от успешной LLM-генерации.

**Граница запуска:** в `ServerController._prepare_loaded_settings_body` значение `GM_ON` для штатной передачи Unity принудительно формируется как `False` (`src/controllers/server_controller.py:458-463`); отдельный status endpoint может читать исходные `GM_ON/GM_REPEAT`. Следовательно, зарегистрированный серверный маршрут существует, но автоматическую периодическую cadence нельзя объявить безусловно включённой. Это классификация фактической доступности, не поиск дефекта/план исправления.

**Инварианты для функционального parity:** GM identity отличается от NPC identity; player/director event не является репликой обычного NPC; управление маршрутизацией и отражение его в контексте — разные события; команда адресуется действительному персонажу; отдача directive не гарантирует исполнение Unity; полный сетевой контракт `req_id` и task status сохраняется; пользовательское explicit направление и результат модели имеют разную степень доверия.

## CAP-GM-002 — временные правила сцены и новый структурированный director (пока НЕ подтверждён ACTIVE)

**Статус:** **EXPERIMENTAL / UNRESOLVED production registration**. **Источники:** `src/domain/game_master.py:8-46`; `src/schemas/game_master_response.py:12-49`; `src/services/game_master_{services,scheduler,directive_registry,context_builder,action_executor}.py`; `src/services/dialogue_transcript_service.py:10-101`; `src/utils/Testing/test_game_master_control_plane.py`, `test_game_master_target_resolution.py`.

В source snapshot находится целостная реализация отдельного механизма:

- `GameMasterResponse.actions` — до 16 структурированных действий: `upsert_rule`, `remove_rule`, `clear_rules`, `route`, `narrate`, `no_action`; схема выдаётся OpenAI/Gemini adapter.
- `GameMasterDirective` хранит `key`, target scope/character, instruction, source (`user_director`/`auto_corrector`), lifetime (`next_reply`, `replies`, `scene`), remaining uses, originating turn.
- `GameMasterDirectiveRegistry` — ephemeral registry по `conversation_id`; правило уникально в слоте `(target,key)`. Пользовательская директива приоритетнее автоматической. При ответе целевого персонажа ограниченный lifetime расходуется; можно очистить конкретную беседу.
- `GameMasterContextBuilder` умеет формировать отдельный контрольный system+user prompt, включающий present participants, anchors, active rules, последние ходы. Отдельный `scene_directives()` возвращает скрытые инструкции для конкретного персонажа.
- `GameMasterActionExecutor` нормализует target через actor/character identifiers присутствующих active/speaking участников и применяет изменение правил либо возвращает routing/narration outcome; `route` и `narrate` имеют capability gates.
- `GameMasterScheduler` считает ответы Mita per conversation и выдаёт сигнал проверки через каждые N ответов (N ограничен 1..100).
- `DialogueTranscriptService` хранит до 64 записей на беседу, выдаёт короткий recent window по количеству и общей длине текста, исключает GM из стенограммы.

**Reachability:** `rg` по production `.py` не выявил вызова `ensure_game_master_services()`, создания `GameMasterContextBuilder`/`GameMasterActionExecutor` и обращения к `scene_directives()` или `note_mita_reply()` вне определений и тестов. Реальный путь `create_task → ChatController → PromptController` продолжает использовать старую structured-intent схему. Поэтому новый control plane нельзя записывать как уже существующую пользовательскую возможность, несмотря на готовые classes/schemas/tests.

**Архитектурный смысл как исследовательская находка, не решение:** обнаружены две различные модели одного домена: короткая адресованная команда на ближайший ход и живущая в рамках conversation директива со временем жизни и приоритетом источника. При будущей отдельной фазе проектирования понадобится выбрать желаемый пользовательский контракт; копировать обе реализации без подтверждения требований не следует.

## Границы и проверка дальнейшего покрытия

1. Отдельно документировать, какие `GM_*` настройки реально достигают Unity клиента, а какие остаются опцией серверного task dispatch.
2. Достаточно исследовать контракт команд Unity; детали анимации и локального scheduler клиента не входят в текущий пользовательский scope.
3. Для production-признания новой системы требуется доказательство composition/startup usage, а не наличие тестового импорта или готовой схемы.
4. Parity scenarios: observe vs command, empty command, target not present, structured directive without visible text, no-action, game disconnect, return feedback, optional voice.

**Смежные документы:** [Unity диалоги](unity-auto-dialogue.md), [структурированный ответ](../03-runtime/structured-response-contract.md), [LLM](llm-and-generation.md), [состояние персонажа](characters.md).
