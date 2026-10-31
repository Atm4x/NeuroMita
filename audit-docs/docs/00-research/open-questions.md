# Открытые вопросы

**Текущий список research gates:** [Pass 13](current-functional-baseline.md). Нижеследующие вопросы накопительные: многие являются будущими продуктовыми решениями или runtime QA, а не отсутствием source discovery. Не возвращаться автоматически к первоначальному «не прочитано» без проверки linked follow-up.

Pass 13 уточнил standalone node editor (U-EDITOR-001), metadata/native edges (U-DEPS-001), memory/RAG setting effects и три special cases, history response fencing и per-family installer operations. Непроверенные runtime условия сохраняются. Новый вопрос provenance: upstream num2words2-core имеет расхождение старой registry/tag metadata и текущей LGPL attribution; [точное свидетельство](../04-dependencies/core-niche-alternatives-and-parity-gates.md). Выбор лицензии/дистрибутива этим аудитом не сделан.

## Требуют решения владельца после подготовки фактов

- Q-UNITY-001: какая Unity revision/ветка является целевой парой Python releases? Локальный dirty checkout на отдельной ветке, origin/releases отсутствует. До уточнения описывать local и fetched contract раздельно, не менять working tree.
- Q-RUN-001: какие startup CLI aliases/exit codes относятся к публичному контракту нового приложения, а какие нужны только нынешнему Python launcher?
- Q-RUN-002: нужен ли общий жёсткий deadline shutdown и какой результат показывать при зависших AI/installer tasks?

## Проверяются по исходникам в следующих проходах

- U-RUN-001: частичная ошибка MainController.__init__ — какие уже созданные ресурсы реально остаются без владельца cleanup?
- U-RUN-002: все ли headless действия обходятся без GUI prompts? Telegram auth уже отключён, остальные paths ещё не проверены.
- U-RUN-003: какие фоновый tasks гарантированно завершаются, какие только cancellation-requested, какие daemon?
- U-UPD-001: полный handshake Launcher.exe / restart 42 / post-exit activation и поведение update-check threads при shutdown.
- U-AI-001: основной IPC/зависимость worker от core уже описаны в ai-ipc; осталось завершить payload schemas, compile/installation и независимую упаковку worker.
- U-EDITOR-001: откуда запускается prompt_editor и какие интеграции реально используются?
- U-UNITY-001: отсутствует result/text application ACK; какую гарантию доставки должен обеспечивать новый продукт и как Unity подтверждает её?
- U-UNITY-002: почему loaded_settings принудительно GM_ON=false при другом поведении legacy get_task_status? Сопоставить остальные GM пути и целевое поведение.
- U-INSTALL-001: полноценная headless очередь не найдена; RUN_HEADLESS обслуживает GUI queue controller. Какие administration сценарии нового headless обязательны?
- U-MEDIA-001: orphan cleanup и retry после удаления audio/image artifacts, limits shared files, реальные producers и ошибки decoder.
- U-STATE-001: политика coalescing queued player messages, memory read-forgetting и lossy summary fallback — подтвердить желаемое поведение после полного discovery.

Наличие вопроса не означает необходимость прерывать исследование: независимые runtime-ветви продолжаются.

Уточнение после Python functional pass: основные U-RUN-003 task ownership/deadline/cancel механизмы описаны в background-tasks-and-events, но не все consumers закрыты. U-EDITOR-001: отдельный prompt_editor entrypoint подтверждён, запуска из production core поиском не найдено; full node editor не закрыт. U-MEDIA-001 orphan scan и settings подробно разобраны в images-and-capture; реальные game producers/Unity internals отложены. Обслуживание/восстановление данных теперь в data-maintenance и compatibility-imports. Старые вопросы выше сохраняют контекст и не должны приводить к повторному discovery уже прочитанных основных paths. Дальнейший порядок — research-progress, Python сначала.

## Новые вопросы после последующего прохода

- `U-HOI4-001`: отдельный `src/connetors/hoi4` не импортируется ни одним найденным core module, но содержит standalone runnable server и mod; действительно ли это поддерживаемая пользователями возможность или эксперимент? До ответа статус `EXPERIMENTAL/UNRESOLVED` и **не** обязательный активный parity. См. [анализ](../01-functional/hoi4-standalone-prototype.md).
- `U-DEPS-001`: динамические runtime imports, дополнительные requirements и внешние DLL не покрываются одним AST import inventory; проверить build/deployment и состав Python AI subprocess перед conclusio.
- `U-PRICE-001`: должен ли pricing cache различать endpoint/account для одинакового `protocol_id,model`? Текущий кэш не различает; см. [контракты](../01-functional/token-budget-and-pricing.md).

- `U-PATH-001`: `core.app_paths.checkpoints_dir` и три RAG helper имеют различающиеся относительные/default пути; требуется bundled boot test и явный canonical model asset contract. См. [paths](../03-runtime/filesystem-paths-and-native-loaders.md).
- `U-NATIVE-PATH-001`: short-path fallback зависит от наличия Windows 8.3 names; проверить Silero/GigaAM с non-ASCII каталогами и 8.3 disabled.

## Новые gaps: settings, secrets и presentation (последний проход)

- `U-SET-001`: все ли nested dict/list значения SettingsRegistry меняются через `set/update_many`, или реальные consumers мутируют shallow-возвращённое значение напрямую? Нужен call-site scan, затем тест изменений revision.
- `U-SET-002`: что происходит при наложении shutdown final `_write_file()` на ещё выполняющийся saver thread после 2s join timeout? Обнаружен static concurrency risk, не воспроизводился.
- `U-PRESET-001`: preset export переносит `key`/`reserve_keys` в plaintext JSON; должен ли новый продукт сохранять переносимый export secrets по explicit consent либо вводить безопасный redacted option?
- `U-PRESET-002`: `delete_custom/save_order` не учитывают failure `_save_presets`; проверить failure UI and disk divergence, а также fallback ID remapping.
- `U-SCHEMA-001`: какие custom schema overrides реально используются и какие side effects миграции legacy settings следует сохранять как compatibility semantics?
- `U-UISET-001`: 12 settings pages зарегистрированы, но полный `UI control → config key → consumer/effect` inventory ещё не сделан (83 literal keys не весь universe); пройти ручные viewmodels, actions, modes, dynamic RAG и installer controls.
- `U-SERVICE-001`: reachability/type registry for all optional services and late shutdown; API configuration handle `owns_presets` не означает auto-unregister, требуется проверить composition lifecycle.

Следующий pass по приоритету — **granular GUI/settings/actions**, затем RAG maintenance/graph GC и remainder dependency classification. См. [план и status ledger](audit-coverage-ledger.md).

## Открытые вопросы после GUI / graph-maintenance follow-up

- `U-GRAPH-GC-001`: какой atomicity/cancellation contract принимается для EntityGC merge/GC/retag, если plan stale, rowcount=0 или пользователь отменил modal progress? Текущая реализация не даёт общей транзакционной гарантии. [Graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md).
- `U-CHAT-MEDIA-001`: каков ожидаемый ownership и TTL staging/temp изображений, когда одна thumbnail удалена, но state `ChatController` хранит файл? Нужно тестировать реальную очистку и правильный MIME. [Composer](../02-ui/chat-composer-and-attachments.md).
- `U-CHAT-HISTORY-001`: предел 256 для live ephemeral/stable/tombstone replay приемлем при задержке persistence? Какой exact context snapshot retention и fallback warning? [Chat](../02-ui/chat-stream-history-and-message-actions.md).
- `U-UI-STRUCT-001`: может ли production вызвать отдельный `role=structured` при выключенном показе? Разные predicates статически подтверждены, runtime reachability не проверялась. [Structured](../02-ui/structured-ai-results-presentation.md).
- `U-UI-GALLERY-001`: гарантирован ли photo watcher при создании/удалении каталога Unity, корректна ли статистическая identity изображения и какие formats Unity реально пишет? [Gallery](../02-ui/gallery-lifecycle-and-photo-viewer.md).
- `U-CHAR-UI-001`: инварианты selected vs active character при reload, bulk maintenance cancellation/partial write и последующей обработке `CLEAR_HISTORY` events. [Character settings](../02-ui/character-library-and-maintenance-actions.md).

`U-*` — вопросы для будущих тестов/архитектурного ревью, а не повод автоматически включать workaround в Rust без functional requirement.

`U-UI-NEWS-001`: pending release focus при отсутствии карточки в новом update contour; как формализовать not-found, generation fence и stale Home-cache? [News](../02-ui/news-and-logs-live-ui-contracts.md).

`U-UI-LOGS-001`: принят ли file-tail 64 KiB/500 lines с non-UTF8 replacement как функциональный UX лимит и нужны ли отдельные worker-log filters/export/redaction? [Logs](../02-ui/news-and-logs-live-ui-contracts.md).

`U-UI-HOME-001`: как полноценно представить partial outcome `Python installed / Unity failed`, если пользователь отклонил restart и затем launch Unity? Нужны реальные updater fixtures и процессное fencing. [Home](../02-ui/home-launcher-update-and-game-state.md).

`U-UI-WIKI-001`: canonical Unicode-anchor mapping and future wiki migration if existing legacy hashes were generated ASCII-only. Проверить RU pages and exact links, positional alias collision. [Wiki](../02-ui/wiki-navigation-localization-and-anchors.md).

`U-UI-GUIDE-001`: должен ли изменённый локально язык Guide сохраняться между открытиями отдельно от глобального `LANGUAGE`, и каким должен быть canonical resource root для assets при произвольном cwd? [Guide](../02-ui/guide-walkthrough-and-image-focus.md).

`U-UI-DIALOG-001`: как гарантируется terminal outcome при Stop running reindex: можно ли закрывать progress после одного `requestInterruption`, если worker находится в непрерываемом вызове? Проверить late completions и статус результата. [Dialogs](../02-ui/dialog-interaction-and-background-task-contracts.md).

`U-UI-DIALOG-002`: WindowManager singleton dialog `protocol_pipeline` переиспользует экземпляр; подтвердить отсутствие старого callback после повторного открытия, и формат атомарности сохранения при `on_apply` error. [Dialogs](../02-ui/dialog-interaction-and-background-task-contracts.md).

## Незакрытые вопросы текущего прохода

- `U-MEM-ID-001`: требуется проверить целиком lifetime `(character_id, eternal_id)` в RAG cache, sentence embeddings, delete, duplicate merge, async reindex и миграциях. Воспроизведение физического purge подтверждает рассогласование `memories.id` и `eternal_id`; необходимо оценить масштаб влияния на retrieval. [Evidence](../01-functional/memory-purge-embedding-identity-regression.md).
- `U-GRAPH-LEDGER-001`: после GUI Clear processed-message ledger сохраняется, а failed-extraction может маркироваться как processed. Нужно определить корректное восстановление и перенос этого ledger при смене модели, истории и отмене. [Evidence](../01-functional/graph-extraction-ledger-and-clear-consistency.md).
- `U-HIST-EPOCH-001`: `history_epoch` fences summary, но не является общей транзакцией с memory/graph и не fences всех graph writers. Проверить overlapping clear/extract и частичные ошибки. [Evidence](../01-functional/character-reset-epoch-and-storage-consistency.md).
- `U-CHAR-FORMULA-001`: нужен golden fixture последовательности clamp/formula/save/rollback при нестандартных полях и операциях из разных consumers. [Evidence](../01-functional/character-custom-fields-and-formula-policy.md).
- `U-AI-PY-IMPORT-001`: составить точный standalone Python worker import closure и пакетный manifest; определить минимальный независимый host protocol без переноса inference в Rust. [Evidence](../04-dependencies/ai-worker-python-core-import-boundaries.md).
- `U-TELEGRAM-AUTH-001`: Qt dialog timeout/close, invalid 2FA code, multiple simultaneous challenge, worker shutdown и получение корректного result. [Evidence](../02-ui/telegram-auth-modal-contracts.md).
- `U-INSTALL-CATALOG-001`: lazy loader error recovery, grouped invalidation, stale status probe, custom model refresh и hardware change требуют runtime tests. [Evidence](../01-functional/installable-catalog-lazy-registry-and-status.md).

## Незакрытые **функциональные** вопросы после смены приоритета

- `U-WORLD-002`: может ли конечный пользователь добавлять кастомные JSON worlds через UI/внешние пакеты, или loader лишь технически допускает такие ID? Проверить runtime registration и способ поставки ресурсов, не придумывать редактор мира.
- `U-ENV-002`: какие ограничения пользователь действительно хочет сохранить как неизменную personality policy (название мира, граница дома, сравнение голосов), а какие являются временными фактами версии приложения? Это влияет на будущие требования к обновлению context.
- `U-GM-003`: какой из двух моделей GM является поддерживаемой продуктовой функцией: только фактический Unity structured intent path или также заявляемый новой схемой долгоживущий набор правил сцены? В source snapshot вызов нового registry/context builder в production не найден; не принимать наличие классов за active feature.
- `U-DIALOGUE-002`: какой UI group/session projection считать обязательным (один/несколько NPC, actor duplicates, смена conversation/epoch, disconnected game)? Подтверждён presentational fallback, но не выполнен GUI E2E.

**Приоритет следующей итерации:** искать ещё не охваченные *активные пользовательские сценарии*, их жизненные циклы и границы Core/Unity/AI; не воспроизводить старые дефекты и не проектировать их исправления. `research-progress.md` хранит точную точку продолжения.

## Новые вопросы продолжения 2026-10-31 (функции и ресурсы, не баги)

- `U-CHAR-CATALOG-02`: какой полный список `storage_name` aliases и prompt packs поддерживается при импорте пользовательских персонажей? Действующий стандартный реестр фиксирует девять ID; автоматическую загрузку произвольных пользовательских классов он не доказывает. [Character catalog](../01-functional/registered-character-catalog-and-identity-contracts.md).
- `U-CHAR-ACTIONS-02`: какие Unity `SegmentIntent.type` реально поддерживаются game-client executor, как получить подтверждение запрошенного действия? Python формирует запросы; Unity-side semantics ещё не проверены в этом проходе. [Effects](../01-functional/structured-character-actions-and-side-effects.md).
- `U-DEP-MANIFEST-02`: сопоставить все 52 distributions без прямого AST import с `Requires-Dist`/installer/runtime и не считать их пустыми; особенно `nodriver`, `mistralai`, `google-cloud-storage`, `pyworld`, `onnx`, `pyaudio`. [Full dependency ledger](../04-dependencies/full-requirements-runtime-evidence-ledger.md).
- `U-UI-PARITY-02`: дополнить action→state→side effects→validation в ещё частично исследованных диалогах ASR, голосов, API, RAG и DB editor; не переносить PyQt widgets буквально. [UI documents](../02-ui/asr-model-gallery-and-settings-workflows.md).


## После AI Hub/status functional pass (2026-10-31)

- Подтверждены ID и поведенческие границы каталога; **все ли модели реально запускаются после `ready=true`** на Windows/CPU/DirectML/CUDA — не проверено. `installed`, `ready` и `running` должны оставаться раздельными.
- Для полного закрытия AI Hub settings требуется component-by-component `settings_schema`/persist/compile/end-to-end и реальные installation/repair/cancellation fixtures; один успешный `InstallAdmission` не является доказательством готовности модели.
- Глобальный статус чата связан с GenerationActivityService и chat error projections; фактические гонки нескольких turns, ТTS и compression в живом Qt не проверялись.
