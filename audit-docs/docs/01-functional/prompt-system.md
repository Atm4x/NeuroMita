# Формирование контекста и шаблоны

**Capability:** `CAP-PROMPT-001`. **Статус:** ACTIVE. **Домен:** context composition. Исследован основной builder; DSL syntax/primitives, template assets и все ветви helpers ещё требуют подробного прохода.

**Источники:** `src/controllers/prompt_controller.py:337 _resolve_examples_profile`, `:371 _setup_character_for_prompt`, `:399 _build_system_messages`, `:648 _is_volatile_system_block`, `:679 _neutralize_world_state_tags`, `:927 build`; `src/controllers/model_controller.py:1353 _generate_chat_serialized`.

## Назначение и сценарий

Собрать для конкретного персонажа актуальный контекст реплики: его идентичность/правила, память, историю, окружение, возможности приложения и текущее обращение. Это подготовка данных для generation, а не неизменяемое чтение шаблона.

Вход — PromptBuildRequest с персонажем, policy, game snapshot, messages/images, retrieved memories, runtime response profile, dialogue/source context. Выход — ordered messages, history_messages, текущий user_message и support_intents. Отсутствие char_id — ValueError.

## Состояние и владельцы

Builder читает HistoryService, memory/reminder systems персонажа, его DSL interpreter, variables, working state и minigame state. На время build вызывающий ModelController держит character state lock. `_setup_character_for_prompt` и `_build_system_messages` записывают derived variables в character: runtime effects, GM instruction, tools/schema/features, reply defaults, EXAMPLES_PROFILE. Это побочные эффекты нынешнего builder; в новой архитектуре возможно передавать immutable context вместо изменения persistent character.

## Выбор шаблона и examples

Policy template override используется только при существующем файле. Для react fallback: character react_template.txt → Common/react_template.txt по относительному пути → основной шаблон персонажа. Для прочих событий — основной шаблон. Фактические пути и включения выясняются через DSL/path resolver.

Examples profile: валидная пользовательская настройка → EXAMPLES_PROFILE_OVERRIDE персонажа → MAX_MODEL_TOKENS и пороги compact/clean → full. Допустимы full/clean/compact/none. Defaults compact≤12000, clean≤24000. Это пороги настройки, не измеренная ёмкость модели.

DSL process_main_template получает ephemeral feature_overrides; L1 принудительно отключает support_intents. Выбранный шаблон определяет intents support. При DSL exception helper возвращает пустые stable/volatile/info blocks и логирует error; весь build не обязательно завершается ошибкой. Новая система должна явно определить, допустим ли degraded prompt.

## Порядок контекста

1. Stable template blocks + Available Tools + sparse response contract (если требуется).
2. DSL system infos.
3. Static Unity rules, intent contract и catalog.
4. Exact core-memory context, history summary, working-state protocol.
5. Action-memory summary bridge как assistant; ограниченная история.
6. Working-state data как assistant.
7. Активная игра и shared minigame context; при отсутствии explicit dialogue — participant prompt.
8. Volatile template blocks, DSL context infos, active memory/reminder blocks.
9. RAG context, behavior state (если шаблон не объявляет custom), temporary system infos.
10. Dynamic Unity capabilities/world/shared world/character world/events.
11. Current State (дата, время, отсутствие/возвращение), System State, Character Environment и group conversation.
12. System/event input, hidden image descriptions, GM directives.
13. Inline image description instruction и source-transition notice, если нужны.
14. User content: текст с speaker prefix при non-Player sender и изображения.

Это общий порядок builder до provider transforms, не гарантированная wire serialization. Разделение stable/volatile преследует cache reuse; фактическая эффективность кэширования не измерялась. SEPARATE_PROMPTS управляет объединением template blocks; не означает объединение всех system messages.

## History, runtime и trust

HistoryService.prepare_for_prompt вызывается только при use_history_in_prompt; возвращает messages, summary, optional action_context и last_message_at. Image quality policy передаётся в history preparation. Полный алгоритм compression/limits — отдельный audit.

Explicit game_connected=False подавляет весь Unity static/dynamic snapshot, чтобы устаревшее состояние после disconnect не попало в desktop chat. None (unknown) не подавляет. Source application/game/NONE отдельно описывает происхождение текущего player turn; наличие подключения не означает, что сообщение пришло из игры.

System State различает configured TTS, actual ASR availability и vision native/description/unavailable. Character Environment уточняет фактическую установку/инициализацию. Источники этих readiness facts проверяются при сервисных ветвях.

Unity world state оформляется как data; reserved control tags и closing tags заменяются читаемыми lookalike brackets. Это защита от подделки текстовых delimiters, не доказательство полной prompt-injection isolation. Explicit GM directives добавляются поздно как управляющие инструкции. Working state model-produced data идёт assistant role и уступает новым наблюдениям.

## Dialogue и пользовательский ввод

Explicit dialogue перечисляет присутствующих участников и сообщает, что speaker order/followup scheduling принадлежат Unity. При двух и более non-player participants без такого context применяется participants system prompt.

System_input использует policy role system/event; idle/timer/reminder переводятся в event. Current user text и images объединяются в user content chunks. Non-player sender получает поясняющий префикс в тексте. User-message metadata содержит timestamp/sender/participants и возвращается для history, но builder сам не является основным write_turn.

## Lifecycle, ошибки и эффекты

Builder вызывается для каждого turn; cancellation проверяется снаружи до/после build, а не между всеми его шагами. Memory/game/reminder helper errors могут подавляться с warning. Ошибка верхнего build превращается в «Failed to build prompt» и None generation result. Дисковая/сетевая активность внутренних DSL includes и history preparation пока не исследована полностью.

## Требования к системе с нуля

Сохранить смысл и приоритеты контекста, отделение current observation от исторического snapshot, explicit source identity, историю/память/working state как разные данные. Представить prompt composition как проверяемый результат с provenance блоков и capability profile. Не считать каждый нынешний block обязательным отдельным Rust service.

Исследовать pure context snapshot + renderer против stateful interpreter. Выбор Rust DSL/templating parser отложен до полного каталога языка и пользовательских файлов. Важно определить совместимость пользовательских шаблонов отдельно от внутренней структуры prompt builder.

## Неясности

Полная DSL grammar, dynamic includes, safe evaluation, post-response DSL, volatile-prefix table, reply defaults, per-character overrides, group topology, exact return-reaction thresholds, memory island rendering, user template authoring UI и reload behavior. Все входят в дальнейший объём.
