# Персонажи: идентичность, ресурсы и состояние

Статус: основной runtime lifecycle и mutation paths исследованы. DSL, память и игры описаны отдельно; не все config/schema и GUI rendering details закрыты.

## Настройки персонажа в GUI

CAP-CHAR-005. Character library/search выбирает **конфигурируемого** персонажа, не переключая активного собеседника; последний меняется через sandbox и отдельно отмечается в settings. Provider задаётся для character через CHAR_PROVIDER_<id>, включая current/default preset semantics. Prompt pack выбирается из доступных для character, сохраняется и вызывает reload; есть pack info, открыть pack/history folders и перезагрузить данные. Изменения каталога API presets обновляют choices, характерные IDs сохраняются отдельно от display names. Managed registry знает фиксированные CharacterDefinition и lazy runtimes; GUI-only registry знает выбранный settings id без экземпляра Character. В исследованной странице и поиске create/add/delete_character production GUI для произвольного создания персонажа не найден; это не доказательство отсутствия всех внешних способов добавления контента.

Maintenance текущего/all scope — отдельные operations, не свойства персонажа: [БД и индексы](data-maintenance.md), [старые сохранения](compatibility-imports.md). CharacterSettingsViewModel, wire_character_settings_logic, change_character_actions, on_prompt_set_changed, apply_prompt_set, provider/folder handlers и registry implementations прочитаны по этим путям; полный layout и snapshot prefetch helpers не закрыты.

## Functional Capability: выбор и загрузка персонажа

**ID:** `CAP-CHAR-001`. **Статус:** ACTIVE. **Источники:** `src/controllers/character_controller.py:19 __init__`, `:52 _on_set_current`; `src/managers/character_manager.py:42 _CHARACTER_DEFINITIONS`, `:57 __init__`, `:149 get_character`, `:168 check_change_current_character`; `src/services/character_registry.py`; `src/characters/character.py:79 __init__`, `:213 ensure_runtime_loaded`.

### Назначение, сценарий и данные

Выбрать персонажа для интерфейса/диалога, загрузить его настройки и persistent state, сохраняя независимость нескольких участников. Registry: Crazy, Kind, Cappie, ShortHair, Mila, Sleepy, Creepy, Ghost, GameMaster. Это 8 персонажей и отдельный GameMaster actor kind. Прежние commented-out cartridges не зарегистрированы; их нельзя считать активными по базовому is_cartridge field.

Input — canonical character id; current selection settings CHARACTER. Default при неизвестном initial id — Crazy. На старте материализуется только initial character, остальные lazy при get. Registry.get не является чистым read: может создать персонажа, загрузить историю и память. Stats для не загруженного персонажа читаются напрямую из persisted variables без materialization.

### Идентичность и состояние

Различать char_id (ключ), display_name, storage_name, voice aliases и actor id конкретного Unity участника. Base history scope storage_key=character_id, а не display_name. Current selected character для UI не заменяет explicit responder id в параллельных requests.

CharacterResourceManager владеет едиными HistoryManager/MemoryManager/ReminderManager/WorkingStateManager и выдаёт bound views per character. Bound view активирует ContextVar scope и per-character operation RLock при вызове; сами instances сервисов общие. Это технический способ изоляции Python, не целевая Rust-структура.

### Lifecycle и UI

Character defaults → subclass overrides → optional initial override → config → lazy persisted variables. CharacterController регистрирует ManagedCharacterRegistry взамен shell settings-only registry. При смене current загружается target; ранее загруженный персонаж дополнительно reload-ит config/history/memory и пересоздаёт DSL. CURRENT_CHANGED только при изменении id; requested reload_data может сработать и без смены id.

Reload all data проходит только загруженные instances. Explicit unknown target отклоняется, текущий персонаж остаётся. Ошибки reload логируются; manager может уже установить current до сбоя reload. Full UI settings sync и game effect выбора ещё проверить.

### Prompt set

PROMPT_SET_{char_id} выбирает подпапку Prompts/{char_id}/{set}. Resolver сначала exact path, затем нормализованные variants выбранного имени, затем Default (case-insensitive), затем первый sorted discovered set. При отсутствии папок возвращает Default с диагностикой. Наличие main_template проверяется warning, не является жёстким gate. PROMPT_SET_NAME/PATH записываются как variables и descriptor prompt path обновляется.

### Требования и реорганизация

Нужны стабильные CharacterId, ActorId и отображаемые имена, явный lifecycle загрузки и выбранного presentation target. Предметная идентичность должна передаваться в операции явно; Rust не требует ContextVar/service locator. Возможны owned character states с typed requests либо central store с projections — решение после полного concurrency audit. Сохранить пользовательский выбор наборов промптов и reload, определить поведение отказа загрузки.

## Functional Capability: состояние и эффекты ответа

**ID:** `CAP-CHAR-002`. **Статус:** ACTIVE. **Источники:** `src/characters/character.py:264 set_variable`, `:288 flush_variables`, `:409 process_response_nlp_commands`, `:462 process_structured_response`, `:1218 _stat_change_hard_limit`, `:1239 _adjust_bounded_stat`; `src/characters/__init__.py:10 SecretExposedCharacter`.

### Назначение и правила

Менять отношение/скука/стресс и дополнительные параметры по ответу модели, запускать memory/reminder/game effects и готовить текст для игрока. Base defaults: attitude 60, boredom 10, stress 5; персонажи переопределяют значения. Дельта основных stats округляется до 2 знаков и clamp-ится STAT_CHANGE_HARD_LIMIT (default 6), итог — configurable {stat}_min/max (default 0/100). При max<min bounds отключаются с error log. Это implementation behavior, не желаемая реакция на неверный config в новой модели.

Plain response проходит PostDSL → LongMemoryRememberCount++ → app vars snapshot → memory tags → behavior tags → game tags. Secret-capable Crazy/Ghost/Creepy обрабатывают Secret marker; structured counterpart использует secret_exposed, если secretExposedFirst ещё False. GameMaster plain path удаляет p-tags без изменения своих stats.

Structured: built-in stats → memory ops → reminders/timers → games/commands → text PostDSL на segments → custom params → MATCH FIELD rules. Ошибки отдельных групп ловятся, остальные effects продолжаются: общего effect transaction нет. LongMemoryRememberCount растёт и на intermediate tool responses, поскольку structured processing выполняется до tool continuation.

Custom params: change_command сопоставляется с custom_fields; numeric coercion → change_min/max → max_change для op=add → safe formula либо add/set → result min/max. Формула получает variables/current/value/command/name и разрешённые max/min/abs/int/float/round. Точная safe_eval grammar ещё не исследована. Невалидный параметр пропускается отдельно.

set_variable автоматически преобразует строковые true/false, целые/числовые и quoted strings, добавляет key в dirty set. flush_variables записывает dirty values одним update_variables_batch, очищает dirty set только после вызова. Summary checkpoint действительно использует этот SQL batch, но если commit бросит ошибку, in-memory variables уже могли измениться.

### Memory/reminder/game effects

Structured memory_add поддерживает priority|content|entities и island:<type>|content как upsert; update — id|priority|content либо id|content; delete — ids/ranges; merge — target/sources с optional merged content, удаляет sources только после успешного update target. Merge состоит из отдельных операций и не подтверждён как atomic.

Reminder add: due_iso|text. Timer: delay_seconds|instruction. Delete reminder: numeric id. Игровые segments start_game/end_game/commands вызывают GameManager. Это orchestration contracts; ограничения фактических операций будут описаны в отдельных доменах.

### Требования

Разделить model proposal, validated domain operation и committed effect. Сохранить ограничения stats/custom params и настройки персонажей, но не размывать все типы в универсальный mutable dictionary автоматически. Текстовые tags/config formulas требуют отдельного compatibility решения. Эффекты UI/мира должны различать requested/executed/failed.

## Functional Capability: очистка состояния персонажа

**ID:** `CAP-CHAR-003`. **Статус:** ACTIVE. **Источники:** `src/characters/character.py:1100 clear_history`; `src/managers/character_manager.py:201 clear_all_histories`; `src/controllers/character_controller.py:104 _on_clear_history`.

Очистка одного загруженного персонажа повышает history_epoch, уведомляет HistoryService, сбрасывает sticky triggers и working state, восстанавливает defaults/config, удаляет stale variables из DB, flush-ит defaults, очищает memories/history и graph. Это намного шире удаления текста чата. UI получает HISTORY_CLEARED.

Важная граница lock: сам epoch increment защищён character_lock, остальное clear_history выполняется после его освобождения. Поэтому нельзя утверждать, что весь reset атомарен относительно всех mutations только на основании комментария. Epoch предотвращает commit старого summary, но возможное пересечение нового turn/reset требует отдельной проверки.

Clear-all для загруженных вызывает полный clear_history; для незагруженных очищает history/memory/working state/graph через resources, без той же процедуры удаления variables/reset defaults. Это наблюдаемая асимметрия, точные пользовательские последствия требуют теста.

### Требования и ошибки

Новая система должна явно назвать область reset (история, память, состояние, граф, текущая игра, timers) и обеспечить единый контракт для loaded/unloaded characters. Остановить или версионировать конкурирующие generation/jobs. Текущий reset не одна SQL transaction; ошибки некоторых cleanup шагов логируются и могут оставлять частичный reset.

## Functional Capability: временный working state

**ID:** `CAP-CHAR-004`. **Статус:** CONDITIONAL: response profile working_state. **Источники:** `src/managers/working_state_manager.py:16 WorkingStateManager`; ModelController final structured path; PromptController.build.

Model-produced snapshot focus/situation/assumptions/open_loops/next_steps — только in-process, отдельно от history, memory и объективного GameState. Обновление заменяет состояние, нормализует whitespace; общий max_chars минимум 200/default 2000, focus≤600, остальные до 6 entries≤400 с общим remaining budget. Пустое очищает. Restart/clear-chat начинает новую сессию. В prompt выводится assistant-role block с пометкой временной интерпретации.

Это контекст следующего turn, не persistence и не права управления миром. Сохранить privacy/ephemeral lifetime и приоритет новых наблюдений; не смешивать со сводкой или history records.
