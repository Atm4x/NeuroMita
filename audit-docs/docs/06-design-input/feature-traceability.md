# Матрица прослеживаемости функциональности Python → требования → проверка

**Назначение:** рабочий cross-reference для следующего независимого архитектора. Этот документ сознательно **не проектирует Rust-модули**, не заменяет detailed capability specifications и не объявляет недочитанные runtime paths проверенными. Владелец указывается как **функциональный кандидат на ответственность**, не как будущий класс/сервис. В текущем Windows checkout Pass 13 Git HEAD и origin/releases подтверждены: `38172493fa0d1caf1a5225bc1c559f095f18bb7a`; 1024 .py и 160 non-Python файлов CodeNow.zip совпали с рабочим деревом по SHA-256. Прежнее отсутствие `.git` относилось к среде полученного архивного аудита. [Актуальная база](../00-research/current-functional-baseline.md).

Обозначения: `CONFIRMED` = источник подтверждает названную ветвь; `CONDITIONAL` = сценарий зависит от настройки/установки; `EXP/UNRESOLVED` = пока не обязательный active parity. Каждая строка указывает путь к подробному документу: там фиксируются state, ошибки, ограничения и степень завершённости исследования. **Validation** — будущая проверка, а не уже выполненный тест.

## Pass 13: уточнение существующих capabilities

| Capability / source → effect | Требования | Validation / фактический evidence |
|---|---|---|
| CAP-RAG-001: repositories/model key/combiner → candidate/provenance | REQ-RAG-SPACE-001, REQ-RAG-RECALL-001 | [RAG source + isolated SQL PASS](../01-functional/rag-mixed-model-recall-and-provenance.md); real model/ranking не запускались |
| CAP-CONFIG-001 / CAP-MEM-001 / CAP-GRAPH-002: setting consumer → TTL/maintenance/query/cache | REQ-SET-SEMANTICS-001/002/003 | [Consumer semantics](../02-ui/memory-rag-settings-consumer-semantics.md); live edits/cache E2E остаётся |
| CAP-HIST-001/UI: initial/older events → final Qt callback/coordinator | REQ-HIST-PAGING-001/002 | [History plan fixture PASS](../02-ui/history-page-fencing-and-live-replay.md); older page Qt/DB concurrency не запускались |
| CAP-DATA-WORLD-001—003: export/import → scoped portable rows/transaction | REQ-DATA-EXCHANGE-001/002 | [Synthetic SQLite fixture PASS](../01-functional/world-db-exchange-isolated-validation.md); реальные legacy DB/artifacts отдельно |
| Standalone prompt editor: buffer→node AST→preview/Apply/metadata | REQ-EDIT-NODE-001/002 | [Parser/codegen fixture PASS + source](../02-ui/prompt-editor-authoring-and-node-workflow.md); unsupported RUN loss подтверждён, Qt node CRUD не подтверждён |
| CAP-API/UI dialogs: pipeline/model params/model catalog → draft/save; compile/system action | REQ-DIALOG-OUTCOME-001 | [Final callbacks](../02-ui/dialog-class-reachability-and-action-outcomes.md); регистрация VCR не доказала production emission |
| CAP-INSTALL: model/backend family operations → status/plan/initialize/remove | REQ-INSTALL-OUTCOME-001 | [Per-component matrix Pass 13](installables-component-by-component-parity-matrix.md); 0/31 physical E2E сохраняется |
| Core dependency consumer → alternative capability/native/license boundary | REQ-DEP-PROVENANCE-001/002 | [Wheel/PE](../04-dependencies/installed-wheel-metadata-and-native-evidence.md), [niche](../04-dependencies/core-niche-alternatives-and-parity-gates.md), [common](../04-dependencies/core-library-alternatives-and-native-costs.md); no Rust build/corpus parity |
| CAP-SCHEDULE-001: tool/structured entries → ReminderManager → scheduler → turn trigger | REQ-SCHEDULE-INPUT-001 | [Entry formats и gates](../01-functional/reminders-and-timers.md); source confirmed, scheduler/network E2E не запускались |
| CAP-UI-AIHUB-001: schema renderer/VM/facade → configurable component validate/save/invalidate | REQ-HUB-SETTINGS-001/002 | [AI Hub Pass 13](../02-ui/ai-hub.md); load migration write и empty-on-error описаны, no Qt E2E |
| CAP-INSTALL: packaging Requirement/Version/markers → target readiness checks | REQ-INSTALL-TARGET-001 | [Packaging follow-up](../04-dependencies/core-library-alternatives-and-native-costs.md); native Rust PEP parsers не собирались |
| CAP-RAG-001 + audio monitor/playback: NumPy exact numeric/DSP work outside inference | REQ-NUMERIC-CORE-001 | [Numeric/DSP follow-up](../04-dependencies/core-library-alternatives-and-native-costs.md); source, не numeric benchmark |
| CAP-LAUNCH-001 / CAP-UPDATE: process marker/discovery/stop + compile cache worker ownership | REQ-PROCESS-IDENTITY-001 | [Implicit psutil consumers](../04-dependencies/core-library-alternatives-and-native-costs.md); реальные процессы не останавливались |
| CAP-HIST-004: snapshot → reserved/used IDs + character-scoped match → SQL sync + variable upsert | REQ-IMPORT-SNAPSHOT-001 | [Identity source](../01-functional/history.md); separate snapshot DB/GUI fixture не исполнялся |

## Накопительная матрица предыдущих проходов

| Capability / статус | Source → функциональный контракт | Requirement | Функциональный owner candidate, без архитектурного решения | Validation, не исполнено |
|---|---|---|---|---|
| CAP-RUN-001/003 · ACTIVE/COND | `src/__main__.py` mode parsing + `startup/headless_runtime.py`; [startup](../03-runtime/startup-and-shutdown.md) | REQ-RUN-001, REQ-RUN-010 | lifecycle приложения | GUI/full/gui_only/headless; graceful stop и exit code |
| CAP-RUN-002/005 · ACTIVE | `startup/gui_backend_loader.py`, `services/runtime_features.py`; [availability](../03-runtime/optional-features.md) | REQ-RUN-002—006 | управление готовностью | disable during startup, late result fence, dependency DAG |
| CAP-RUN-004 · ACTIVE | `controllers/main_controller.py:667+`; [shutdown](../03-runtime/startup-and-shutdown.md) | REQ-RUN-007—009 | владение ресурсами runtime | повторный stop, отдельные failures, дочерние workers |
| CAP-LLM-001/003 · ACTIVE | `ChatController`, `ModelController`, LLMRequestRunner; [turn](../01-functional/llm-and-generation.md), [deadlines](../03-runtime/llm-requests.md) | REQ-TURN-001—003 | диалоговый turn | отмена, retry, duplicate suppression, character scope |
| CAP-LLM-002 · COND | structured parser/effect gates; [structured](../03-runtime/structured-response-contract.md) | REQ-TURN-004—005 | выполнение эффектов | malformed/repaired, trusted flags, schema reject |
| CAP-PROMPT-001—006 · ACTIVE/COND | PromptController + DSL/PostDSL + pack catalogue; [prompt](../01-functional/prompt-system.md), [DSL](../01-functional/prompt-language-and-packs.md) | REQ-CONTENT-001—003 | prompt composition | missing asset, nested pack, language aliases, invalid DSL |
| CAP-HIST-001—005 · ACTIVE | `HistoryManager`, `HistoryController`, conversation writer; [history](../01-functional/history.md), [compression](../01-functional/history-compression.md) | REQ-HIST-001—002 | dialogue persistence | fan-out partial failure, edit/delete/regenerate, epoch coverage |
| CAP-MEM-001/002 · ACTIVE/COND | `MemoryManager` CRUD, TTL, semantic merge; [memory](../01-functional/memory.md), [maintenance](../01-functional/data-maintenance.md) | REQ-MEM-001—002 | long-term memory | cross-character scope, dedup model identity, TTL conflict |
| CAP-RAG-001/002 · COND | RAG pipelines, retrievers and reindex; [rag](../01-functional/rag.md), [maintenance](../01-functional/data-maintenance.md) | REQ-RAG-001, REQ-DERIVED-001 | retrieval/query and index lifecycle | disabled model, reload, full/missing index, cache invalidation |
| CAP-GRAPH-001—004 · COND | `GraphController`, `GraphStore`, maintenance GUI; [graph](../01-functional/knowledge-graph.md), [maintenance](../01-functional/data-maintenance.md) | REQ-DERIVED-001—002 | derived knowledge | failed extraction, processed ledger, GC, incremental revision |
| CAP-REM-001 · COND | `ReminderManager`, `ReminderController`; [reminders](../01-functional/reminders-and-timers.md) | REQ-REM-001 | scheduled actions | restart, expired/dismissed event, dispatch acceptance |
| CAP-AI-001/002 · ACTIVE/COND | `AIEngineController`, worker_process, runtime_environment; [AI IPC](../03-runtime/ai-ipc.md) / [environments](../03-runtime/ai-environments.md) | REQ-AI-001—003 | worker boundary | stale request, process crash, cancellation, versioned payload |
| CAP-AI-003 · COND | `runtime_failure_policy.py`, worker CUDA exit; [fatal failure](../03-runtime/cuda-fatal-worker-recovery.md) | REQ-AI-FAIL-001—003 | AI worker supervision | CUDA poisoned context, exit70, parent recovery, no replay |
| CAP-VOICE-001 · COND | AudioController + Local/Remote voice; [voice](../01-functional/voice-output.md) | REQ-VOICE-001 | audio synthesis/playback | TTS switching, audio device loss, voice late callback |
| CAP-VOICE-002—005 · COND | voice settings/catalog/presets + GUI; [voice controls](../02-ui/voice-controls.md) | REQ-VOICE-002 | character voice preferences | cancel install, per-character overrides, failed preview |
| CAP-SPEECH-001 · COND | SpeechController/gate/capture; [speech](../01-functional/speech-input.md) | REQ-SPEECH-001—003 | audio input/transcription | PTT, VAD segmentation, hotplug, unavailable ASR |
| CAP-TG-001—002 · COND | Telegram auth, voice converter, UI; [telegram](../01-functional/telegram-voice.md), [controls](../02-ui/voice-controls.md) | REQ-VOICE-002 | Telegram external integration | code/2FA/cancel/revoke, missing credentials; live API not checked |
| CAP-IMAGE-001—006 · COND | screen/camera handlers, image cleanup, history; [images](../01-functional/images-and-capture.md) | REQ-IMAGE-001—003 | media capture and attachment | multi-frame camera, orphan safety, device unavailable |
| CAP-TOOLS-001—006 · COND | `ToolManager`, builtins and native/schema dispatch; [tools](../01-functional/tools-and-web.md) | REQ-TOOLS-001—003 | tools/action authorization | cross-character concurrency, disabled tool, network failure |
| CAP-BEAT-001—004 · COND | BeatService/analysis cache/worker; [beats](../01-functional/music-beats.md) | REQ-BEAT-001 | music analysis | cache invalidation on settings change, async batch cancellation |
| CAP-GAME-001—004 · COND | ChessGame/SeaBattleGame/available_games; [desktop games](../01-functional/desktop-mini-games.md) | REQ-GAME-001—002 | independent mini-games | state reset, illegal move, game enable/disable, engine missing |
| CAP-UNITY-001 · ACTIVE | Python network/server, retry outbox; [transport](../03-runtime/unity-transport.md), [delivery](../03-runtime/unity-retry-outbox.md) | REQ-UNITY-001—002 | game session transport | reconnect, duplicate send, application ACK absent |
| CAP-UNITY-002/003 · COND | game media/settings, auto-dialogue and ASR admission; [media](../03-runtime/unity-media-transfer.md), [admission](../01-functional/unity-dialogue-admission.md) | REQ-UNITY-002—003 | game orchestration | stale media artifact, concurrent speech, delayed Unity state |
| CAP-INSTALL-001/002 · COND | `InstallController`, component plans; [installer](../01-functional/installations.md), [components](../01-functional/installer-component-plans.md) | REQ-INSTALL-001—005 | AI component catalogue and orchestration | interrupted download, install status, version mismatch |
| CAP-INSTALL-LIFECYCLE/CANCEL/UNINSTALL/REPAIR · ACTIVE/COND | installer, pip installer, environments; [recovery](../03-runtime/installer-recovery-and-uninstall.md) | REQ-INSTALL-LIFE-001 | install lifecycle / compensation | force reinstall, rollback, partial uninstall, locked Windows DLL |
| CAP-INSTALL-ASR-001 · COND | ASR installables/recognizers; [component plans](../01-functional/asr-rag-beat-install-plans.md) | REQ-ASR-INSTALL-001 | AI speech model distribution | deps installed vs weights missing, offline/no CUDA |
| CAP-INSTALL-RAG-001 · COND | RAG install spec; [component plans](../01-functional/asr-rag-beat-install-plans.md) | REQ-RAG-INSTALL-001 | retrieval model distribution | no-op uninstall, wrong checkpoint readiness, different presets |
| CAP-INSTALL-BEAT-001 · COND | `beat_install.py`; [component plans](../01-functional/asr-rag-beat-install-plans.md) | REQ-BEAT-INSTALL-001 | beat model distribution | CPU/GPU, cancelled dependency, component readiness |
| CAP-VOICE-ASSETS-001 · COND | `voice_assets_installer.py`, voice manifest; [bundles](../01-functional/voice-asset-distribution.md) | REQ-ASSET-001 | voice asset distribution | halfway extraction, partial promotion, false remove success |
| CAP-API-001—007 · ACTIVE/COND | providers, protocol registry and transforms; [providers](../01-functional/provider-configuration.md), [transforms](../01-functional/message-transforms.md) | REQ-API-001, REQ-PROVIDER-006—008 | model configuration/protocol | role/content mutation, endpoint switch, provider-specific error |
| CAP-PROTOCOL-CHAT/RESPONSES · COND | protocol adapters; [wire state machines](../03-runtime/openai-protocol-state-machines.md) | REQ-PROTO-001 | LLM protocol codec | tool IDs, response stream partial, schema 400 downgrade |
| CAP-AUTH-PLAN-001/002 · EXP/COND | `chatgpt_plan_auth.py`, Plan transport; [accounts](../01-functional/account-authentication.md), [Plan wire](../03-runtime/provider-wire-contracts.md) | REQ-PROVIDER-008 | external OAuth credential session | DPAPI lock, expired token, no redirect, signed-out session |
| CAP-TOKEN-001/CAP-PRICE-001—002 · ACTIVE/COND | `context_counter.py`, `model_pricing_manager.py`; [budget/pricing](../01-functional/token-budget-and-pricing.md) | REQ-TOKEN-001, REQ-PRICE-001 | observability/context cost | unknown vs zero, cross-account model name, per-character display |
| CAP-LAUNCH-001/CAP-UPDATE-001—004 · ACTIVE/COND | launcher/update/download/process guard; [update](../01-functional/launcher-and-updates.md), [distribution](../03-runtime/build-and-release-distribution.md) | REQ-UPDATE-001, REQ-DIST-001 | application release/update lifecycle | pending activation, blocked game, corrupted full/patch asset |
| CAP-NETWORK-001—003 · ACTIVE/COND | `src/core/networking/{http_clients,errors}.py`; [HTTP lifecycle](../03-runtime/network-client-ownership-and-errors.md) | REQ-NET-001—004 | transport resources / network error presentation | TLS/DNS/status/cancel, stream close, sensitive URL redaction |
| CAP-CONFIG-001 · ACTIVE | SettingsRegistry/Manager; [settings](../03-runtime/settings-and-preferences-store.md) | REQ-CONFIG-001 | user preference store | mutation notification, batched change, invalid JSON, crash save |
| CAP-PATH-001—004 · ACTIVE/COND | AppPaths/native path/RAG/storage/logging; [paths](../03-runtime/filesystem-paths-and-native-loaders.md) | REQ-PATH-001—005 | user files and managed asset paths | external override, Unicode no 8.3, different cwd, worker crash |
| CAP-DATA-004—009 · ACTIVE/COND | DB viewer/migrations/archive restore; [data maintenance](../01-functional/data-maintenance.md), [compatibility](../01-functional/compatibility-imports.md) | REQ-DATA-001—004 | data management/migration | partial import, WAL backup, replay idempotency, cache invalidation |
| CAP-JOB-001—003/CAP-EVENT-001 · ACTIVE | task supervisor/executors/event bus; [tasks](../03-runtime/background-tasks-and-events.md) | REQ-JOB-001, REQ-EVENT-001 | background work ownership | stop/late result, ordering, saturation, wait_idle accounting |
| CAP-UI-NAV/GALLERY/NEWS/HELP/LOGS · ACTIVE/COND | page registries/view models; [navigation](../02-ui/navigation-gallery-and-help.md) | REQ-NAV-001, REQ-UI-001 | presentation interaction | offline news, stale result after repo switch, empty gallery |
| CAP-IPC-CTRL-001 · COND | `RuntimeIPCService` local commands; [local control](../03-runtime/local-control-ipc.md) | REQ-AI-003 | local control plane (не AI inference) | malformed JSON, authorization/allowlist, shutdown race |
| CAP-I18N-001—002 · ACTIVE | localization registries and preference GUI; [localization](../02-ui/localization-and-preferences.md) | REQ-UI-001 | interface localization | switch language at runtime, stable key aliases, missing catalog |
| CAP-WEB-001—002 · EXP | `src/web/server.py` standalone; [web](../01-functional/standalone-web-surface.md) | REQ-WEB-001 (scope decision) | отдельный web tool, если подтверждён | product reachability, manual launch/authorization |
| CAP-HOI4-EXPERIMENTAL-001—002 · EXP/UNRESOLVED | `src/connetors/hoi4` standalone; [HOI4](../01-functional/hoi4-standalone-prototype.md) | **Нет обязательного REQ** до подтверждения | standalone external game integration | externally launched? incomplete mod hooks? real support? |

| CAP-UI-GUIDE-001—006 · ACTIVE/COND | `src/ui/widgets/guide_widget.py:15-1920`, `src/ui/windows/guide_dialog.py:14-85`; [Guide](../02-ui/guide-walkthrough-and-image-focus.md) | REQ-UI-GUIDE-002—006 | UI walkthrough, screenshot/step presentation | levels 3/5/13; missing assets; absent steps; RU/EN; reopen/Wiki callback |

| CAP-UI-DIALOG-001—005 · ACTIVE/COND | `src/ui/dialogs/{background_task_dialog,message_processing_dialog,export_dialog,db_export_dialog,styled_message}.py`, callers; [dialogs](../02-ui/dialog-interaction-and-background-task-contracts.md) | REQ-UI-DIALOG-001—005 | UI interaction and task presentation | hide/stop/race, cancel/apply/reopen, output failure, status alerts |

## Пробелы и честная граница готовности

- Эта матрица объединяет **подтверждённые основные ветви**, но не представляет по одному CAP ID на каждую кнопку/setting/dialog, каждую модель instal­ler, все Unity commands или каждый worker subprocess method. Отсутствие строки **не** означает `LEGACY`.
- Источник в таблице иногда указывает модуль/symbol, не диапазон строк. Локальные подробные документы могут иметь точные ranges; там, где нет, следует расширить evidence при последующем проходе.
- `Requirement` — **предварительно извлечённый** ожидаемый функциональный контракт. Если старый behavior — обнаруженная ошибка, требование ориентируется на пользовательскую гарантию, а не воспроизведение дефекта.
- `owner candidate` — только **понятийная ответственность**, без actor/shared service/trait/GUI выбора. Rust-архитектуру проектировать после независимого ревью.
- В графе validation перечислены **предлагаемые** property/integration/fixture тесты; они не запускались, результаты не доказаны.
- После завершения discovery эту таблицу надо перейти от широких `CAP-*` семейств к конкретным единичным capabilities и привязать к каждой статус доказанности/функциональный сценарий и полное покрытие `Source → Capability → Requirement → Candidate Ownership → Validation`.

## Продолжение traceability: конфигурация и settings GUI

| Capability / статус | Source → контракт | Requirement | Functional responsibility candidate | Validation (не выполнено) |
|---|---|---|---|---|
| CAP-SET-001/002 · ACTIVE | `settings_manager.py`, `settings_registry.py`, `update_contour.py`; [settings](../01-functional/settings-storage-and-migrations.md) | REQ-SET-001—002, REQ-SET-004—005 | preferences/persistence/compatibility migration | corrupt JSON, explicit contour vs marker, concurrent writer, revision |
| CAP-SET-003/004 · CONDITIONAL | `api_presets_controller.py`, `model_settings/*`; [API schema](../01-functional/settings-storage-and-migrations.md) | REQ-SET-003, REQ-SET-006 | API credentials/preset/schema state | import/export preserves order, dialect constraints, custom overrides |
| CAP-SET-005/006 · CONDITIONAL | `chatgpt_plan_auth.py`, `general_settings.py`; [secrets](../01-functional/settings-storage-and-migrations.md) | REQ-SET-007 | credential lifecycle / UI display policy | DPAPI and cross-account refusal; exported preset has secrets warning |
| CAP-SERVICE-001 / CAP-SET-OBSERVER-001 · ACTIVE | `core/services.py`, `settings_registry.py`; [ownership](../03-runtime/typed-services-and-settings-observers.md) | REQ-SERVICE-001—002, REQ-OBSERVER-001 | lifetime/admission/notification | owner handle race, replay, unsubscribe, lost delivery |
| CAP-UI-SET-001—003 · ACTIVE/CONDITIONAL | `section_registry.py`, `section_access.py`, `settings_page_widget.py`, `settings_binding.py`; [UI navigation](../02-ui/settings-navigation-and-lazy-pages.md) | REQ-UISET-001—005 | Settings presentation / feature readiness | all 12 registered sections, section-level lifecycle, deep link, component unavailable |

`Source → Capability → Requirement → Functional responsibility → Validation` здесь по-прежнему свернуто по доменным семействам; следующая фаза — granular per-setting/per-action rows.

## Продолжение матрицы: UI actions, RAG maintenance, character settings

| Source → Capability / status | Requirement | Functional responsibility candidate (не архитектурное решение) | Validation fixture (НЕ выполнялся) |
|---|---|---|---|
| `settings` builders + consumer references → `CAP-UI-SET-004` · ACTIVE/COND; [matrix](../02-ui/settings-key-consumer-evidence.md) | `REQ-SET-KEY-001—003` | settings values/callbacks/side effects | all 83 literal keys and 6 dynamic targets, falsify unused key hypothesis |
| `entity_gc/entity_typing/rag_memory_controller` → `CAP-GRAPH-MAINT-001—003` · COND; [graph](../01-functional/graph-maintenance-and-entity-lifecycle.md) | `REQ-GRAPH-MAINT-001—007` | graph data maintenance | partial apply vs requested action counter, retype same-name entities, cancel |
| `graph_view_widget/db_viewer` → `CAP-UI-GRAPH-001—003` · COND; [viewer](../02-ui/graph-viewer-interactions.md) | `REQ-UI-GRAPH-001—004` | graph read projection and editing intent | filter/search, late selection, cancel and callback race |
| `sandbox_page/sandbox_page_view_model` → `CAP-UI-SANDBOX-001—003` · ACTIVE; [sandbox](../02-ui/sandbox-page-functional-contract.md) | `REQ-UI-SANDBOX-001—005` | sandbox session/settings presentation | game disable/reenable preserves policy, concurrent latency |
| `chat_panel/chat_controller/app_shell_controller` → `CAP-UI-CHAT-001` · ACTIVE; [composer](../02-ui/chat-composer-and-attachments.md) | `REQ-UI-CHAT-001—005` | chat composition/media leases | 8 files per batch vs total, delete preview, retain MIME |
| `presentation_coordinator/message_widget/chat_message_actions_view_model` → `CAP-UI-CHAT-002—004` · ACTIVE/COND; [chat](../02-ui/chat-stream-history-and-message-actions.md) | `REQ-UI-CHAT-006—010` | chat rendering/history identity/actions | 256 cache, character switch, streamed ack, ctx exact/fallback |
| `structured_panel/message_renderer/debug_settings` → `CAP-UI-CHAT-005` · ACTIVE/COND; [structured](../02-ui/structured-ai-results-presentation.md) | `REQ-UI-STRUCT-001—004` | structured read-only presentation | role=structured with off, invalid delta, multi-target history replay |
| `photo_gallery/gallery_page_view_model/gallery_viewer` → `CAP-UI-GALLERY-001` · ACTIVE; [gallery](../02-ui/gallery-lifecycle-and-photo-viewer.md) | `REQ-UI-GALLERY-001—004` | file collection/decode/viewer projection | dir change, stat mutation, invalid image, stale result |
| `character_settings_logic/ui` → `CAP-UI-CHAR-001—003` · ACTIVE/COND; [characters](../02-ui/character-library-and-maintenance-actions.md) | `REQ-UI-CHAR-001—004` | character config/maintenance command scope | selected != active, bulk partial and child worker cancelled |

Это дополнительная прослеживаемость основных действий, не исчерпывающее one-row-per-active-control покрытие всех Qt экранов.

### News/Logs UI source-to-requirement дополнение

| Source → capability / статус | Requirement | Candidate functional owner (без Rust architecture) | Validation |
|---|---|---|---|
| `news_page_view_model/news_page.py` → `CAP-UI-NEWS-DETAIL-001` ACTIVE/COND; [news](../02-ui/news-and-logs-live-ui-contracts.md) | `REQ-UI-NEWS-001—002` | repository selection, cache/feeds, release focus | changing contour during request, missing release id |
| `logs_page_view_model/logs_page.py` → `CAP-UI-LOGS-DETAIL-001` ACTIVE; [logs](../02-ui/news-and-logs-live-ui-contracts.md) | `REQ-UI-LOGS-001—002` | bounded journal reader/read-only UI | file truncation/rotation, non-UTF8, navigation on/off |

### Home primary/update UX

| Source → capability | Requirement | Candidate functional owner (не Rust architecture) | Validation fixture |
|---|---|---|---|
| `home_page_view_model/home_page` → `CAP-UI-HOME-001—003` ACTIVE/COND; [home](../02-ui/home-launcher-update-and-game-state.md) | `REQ-UI-HOME-001—004` | application game/update state orchestration & presentation | Python applied then Unity fail; test-contour admission; cancel; restart prompt; primary action priority |

### Wiki/Guide navigation traceability

| Source → capability | Requirement | Candidate functional owner (не Rust architecture) | Validation fixture |
|---|---|---|---|
| `wiki_page.py` → `CAP-UI-WIKI-001—003` ACTIVE; [wiki](../02-ui/wiki-navigation-localization-and-anchors.md) | `REQ-UI-WIKI-001—003` | local documentation/resource path and navigation projection | Russian anchors, skipped heading order, locale fallback, link containment |
| `guide_dialog.py/guide_widget.py` → `CAP-UI-GUIDE-001` ACTIVE, depth PARTIAL; [boundary](../02-ui/wiki-navigation-localization-and-anchors.md) | `REQ-UI-GUIDE-001` | on-boarding workflow and external help launch | hide/reopen guide, step state, image/locale interactions |

### Текущий проход: восстановление и исчерпывающий identity contract

| Source → Capability / status | Requirement | Functional owner candidate (не готовая архитектура) | Validation |
|---|---|---|---|
| `graph_store.py; rag_memory_controller.py` → `CAP-GRAPH-LEDGER-001—003` · CONDITIONAL; [graph ledger](../01-functional/graph-extraction-ledger-and-clear-consistency.md) | `REQ-GRAPH-LEDGER-001—005` | graph projection/extraction history | temp SQLite GUI-clear repro DONE; failed extract/rebuild/revision NOT DONE |
| `character.py; history_controller.py` → `CAP-RESET-001—003` · ACTIVE; [history](../01-functional/character-reset-epoch-and-storage-consistency.md) | `REQ-RESET-001—005` | conversation reset lifecycle | 23 tests DONE; cross-store atomicity NOT DONE |
| `memory_manager.py; rag_manager.py` → `CAP-MEM-ID-001/002` · ACTIVE/COND; [memory](../01-functional/memory-purge-embedding-identity-regression.md) | `REQ-MEM-ID-001—004` | scoped memory identity and derived vectors | two temp DB repro DONE; async/cache E2E NOT DONE |
| `character.py; safe_eval.py` → `CAP-CHAR-CUSTOM-001/002` · COND; [formula](../01-functional/character-custom-fields-and-formula-policy.md) | `REQ-CHAR-CUSTOM-001—004` | character custom-stat evaluation | 17 unit tests DONE; UI NOT DONE |
| `rag_service.py; rag_runtime.py; worker_process.py` → `CAP-AI-BOUNDARY-001/002` · COND; [worker](../04-dependencies/ai-worker-python-core-import-boundaries.md) | `REQ-AI-BOUNDARY-001—004` | Python inference worker ABI/interface | static import reachability DONE; launch standalone NOT DONE |
| `telegram_auth_dialogs.py; telegram_auth_service.py` → `CAP-UI-TG-AUTH-001` · COND; [modal](../02-ui/telegram-auth-modal-contracts.md) | `REQ-UI-TG-001—004` | auth challenge/correlated future | static source DONE; Qt/real login NOT DONE |
| `catalog_manifest.py; registry_builder.py; installable_catalog_service.py` → `CAP-INSTALL-CATALOG-001/002` · ACTIVE/COND; [catalog](../01-functional/installable-catalog-lazy-registry-and-status.md) | `REQ-INSTALL-CATALOG-001—004` | catalog metadata/status/readiness | code evidence DONE; probe/factory failure tests NOT DONE |

## Функциональный проход: мир, самосознание, режиссёр сцены, group session

| Source → capability / status | Requirement | Domain responsibility (не Rust module) | Проверка сохранения поведения |
|---|---|---|---|
| `world_character_relations.py`, `world_contexts/*.json`, `model_controller.py` → `CAP-WORLD-001` ACTIVE/COND | `REQ-WORLD-001—002` | Персональный transient lore из мирового snapshot | 7 известных миров, owner/former/visitor, individual context; concurrent characters |
| `character_environment_context.py`, `prompt_controller.py`, `presentation_hub.py` → `CAP-ENV-001` ACTIVE | `REQ-ENV-001` | Публичное для LLM знание о доступности пользовательских функций | installed/connected; voice method/configured/ready; app update |
| `contracts.py`, `prompt_controller.py` → `CAP-ENV-002` ACTIVE/COND | `REQ-ENV-002` | Player-authoring provenance между интерфейсом и игрой | app→game→app, unknown, client connected without authored turn |
| `create_task.py`, `chat_controller.py`, `prompt_controller.py` → `CAP-GM-001` COND | `REQ-GM-001—002` | Обращение к hidden director и доставка structured action/следа сцены | observe/command; present target; no visible text; game output |
| `services/game_master_*`, `schemas/game_master_response.py` → `CAP-GM-002` EXPERIMENTAL/UNRESOLVED | **Не включено** в обязательный parity | Не зарегистрированные candidate rules/lifetime/routing | Сначала доказать production composition или согласовать новую функциональную цель |
| `contracts.py`, `dialogue_runtime_state.py`, `chat_panel_view_model.py`, `dialogue_presentation.py` → `CAP-DIALOGUE-VIEW-001/002` ACTIVE/COND | `REQ-DIALOGUE-VIEW-001—002` | Unity session identity и ephemeral UI projection | actor != character, epoch, present roster, disconnect, group title |
| `dialogue_transcript_service.py`, `game_master_context_builder.py` → `CAP-DIALOGUE-VIEW-003` EXPERIMENTAL/UNRESOLVED | **Не включено** в обязательный parity | Не зарегистрированная групповая стенограмма control plane | Найти реальные `record()` и owner registration до классификации ACTIVE |
| `create_task.py`, `game_state_manager.py`, `model_controller.py`, `prompt_controller.py` → `CAP-WORLD-STATE-001—003` ACTIVE/COND | `REQ-WORLD-STATE-001—003` | Split stable rules/catalog, dynamic action readiness, character-scoped last-known state and one-turn events | partially updated world, disconnected game, disabled intents, tag text, shared mini-game context; [source](../03-runtime/unity-world-state-prompt-projections.md) |

[World/Environment](../01-functional/character-world-and-environment-awareness.md) · [GameMaster](../01-functional/game-master-scene-direction.md) · [Conversation](../03-runtime/conversation-session-projections.md). В этой итерации контроль не направлен на поиск старых дефектов.

## Продолжение 2026-10-31 — функциональные действия и паритет (без разработки Rust архитектуры)

| Source → capability / status | Requirement | Functional owner **candidate** (не структура Rust) | Проверка паритета / what remains |
|---|---|---|---|
| `model_controller.py; structured_response.py; character.py` → `CAP-CHAR-EFFECTS-001—006` ACTIVE/COND | `REQ-CHAR-EFFECTS-01—06` | validated character intents, side-effect coordination | structured/sparse response, effect enabled vs disabled, Unity request vs acknowledged game state; [документ](../01-functional/structured-character-actions-and-side-effects.md) |
| `catalog_manifest.py; installable_catalog_service.py` → `CAP-INSTALL-CARDS-001—003` ACTIVE/COND | `REQ-INSTALL-CARDS-01—03` | installable manifests, readiness and catalog projection | 31 static + dynamic RAG categories; installed / ready / loaded / failed distinction; [документ](../01-functional/installable-catalog-and-runtime-readiness-matrix.md) |
| `remote_voice_repository.py; remote_voice_service.py` → `CAP-VOICE-REMOTE-001—003` COND | `REQ-VOICE-REMOTE-01—03` | character-specific remote voice selection and credential application | preset CRUD, missing auth, preview, character switch; [документ](../01-functional/remote-voice-presets-and-character-routing.md) |
| `asr_models/registry.py; ASR UI builders` → `CAP-UI-ASR-001—004` ACTIVE/COND | `REQ-UI-ASR-01—04` | model discovery/config/readiness UI | five engine families, not installed/installed/active, input state; [документ](../02-ui/asr-model-gallery-and-settings-workflows.md) |
| `voiceover_settings.py; voice_models/*` → `CAP-UI-VOICE-LOCAL-001—004` ACTIVE/COND | `REQ-UI-VOICE-LOCAL-01—04` | voice model choice, settings and compilation UX | model/runtime install, compiler dialog, VC profile, cancel/error; [документ](../02-ui/local-voice-model-management-and-compile-dialogs.md) |
| `api_settings/*; model_parameters_dialog.py` → `CAP-UI-API-001—005` ACTIVE | `REQ-UI-API-01—05` | provider presets, schema-driven parameter settings | create/update/cancel, model schema loading, unsaved changes, inactive provider; [документ](../02-ui/api-presets-and-model-parameter-editor-workflows.md) |
| `rag_preset_view_model.py; embed_provider_view_model.py` → `CAP-UI-RAG-001—004` ACTIVE/COND | `REQ-UI-RAG-01—04` | RAG pipeline selection/config and embedding provider UX | preset/name/edit/apply, install/ready/runtime and provider/key distinctions; [документ](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md) |
| `app_window_base.py:332-387; context_viewer_dialog.py` → `CAP-UI-CONTEXT` ACTIVE | `REQ-UI-CTX-01—03` | request/response diagnostic reader | message-specific vs last-sample fallback; search/copy; usage estimates vs exact; [документ](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `character_settings_logic.py:1512-1523; db_viewer.py` → `CAP-UI-DATABASE` ACTIVE | `REQ-UI-DB-01—03` | data browser and explicit user maintenance | char/global, optional table, search/filter/edit/batch/delete; image description; [документ](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `finetune_collector.py; data_settings.py; export_dialog.py` → `CAP-DATA-FINETUNE` COND | `REQ-DATA-FT-01—05` | sample catalog, rating, retention, filtered export | cap50/unlimited, uuid rating, Raw/ShareGPT, multi-modal loss, off switch; [документ](../01-functional/fine-tuning-data-capture-curation-and-export.md) |
| `hardware_inventory_service.py; ai_engine_controller.py; ai_environment_maintenance_service.py` → `CAP-AI-HARDWARE; CAP-AI-ADMIN` COND/Windows | `REQ-AI-HW-01—02; REQ-AI-ADMIN-01—02` | hardware identity, worker topology, managed-environment maintenance | DXGI/CUDA ordinal+LUID, shared/split, reset states; Windows live E2E pending; [документ](../01-functional/hardware-acceleration-and-ai-engine-administration.md) |
| `rag_utils.py; query_builder.py; utils/__init__.py` → `CAP-LING-RAG-01/02; CAP-LING-SPEECH-01` COND | `REQ-LING-01—03` | keyword/FTS linguistic functions and spoken-text normalization | lexeme vs stem-prefix, OR query, token cap, RU/EN/PTBR numbers, unsupported locale; [документ](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md) |
| `__main__.py; main_controller.py; main_page_registry.py; section_registry.py; catalog_manifest.py` → `CAP-DEPS-DYNAMIC-001` ACTIVE/COND | `REQ-DEPS-DYNAMIC-01—03` | discovery/activation boundary of optional services/installables/GUI pages | dynamic import group live selection, failure caching, static 720-file AST inventory is not complete reachability proof; [документ](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md) |

Не выполнялись аппаратные/GUI/remote integration tests в этой итерации. Валидационные сценарии являются целевой спецификацией проверки, а не утверждением о существующем тестовом покрытии.

## 2026-10-31: catalogue identity и requirements traceability

| Source → capability/status | Requirement ID | Обязательное поведение | Parity validation / открыто |
|---|---|---|---|
| `character_manager.py:41-84`; `characters/__init__.py:28-252` → `CAP-CHAR-CATALOG-001` ACTIVE | `REQ-CHAR-CATALOG-01` | Девять ID, отдельные stable/display/storage/local voice names; alias/локализация не изменяют id | Regenerate golden catalogue, 8 Mitas+GameMaster, voice name alias; [источник](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `character_manager.py:104-163`; `character.py:213-250` → `CAP-CHAR-CATALOG-002` ACTIVE | `REQ-CHAR-CATALOG-02` | Available/loaded/current separate; initial unknown→Crazy; data/history/memory lazy; persisted overrides | Known/unknown initial, first/second select, unloaded stats, saved variables |
| `character_controller.py:52-114`; `character_manager.py:201-227` → `CAP-CHAR-CATALOG-003` ACTIVE | `REQ-CHAR-CATALOG-03` | Select/reload/clear single/all incl unloaded characters | Selection changing/unchanged, reload status, bulk clear with no instance |
| `characters/__init__.py:9-25,232-256`; `services/character_registry.py:49-81` → `CAP-CHAR-CATALOG-004` CONDITIONAL | `REQ-CHAR-CATALOG-04` | GM separate dialogue role, special secret-exposed gate, GUI-only selected-id representation | Secret on 3 allowed chars, not others; gui_only profile no runtime, GM from Unity |
| `requirements.txt:1-90`; `scripts/run.py`; selected `src/**/*.py` → `CAP-DEPS-REQUIREMENTS-001` RESEARCH | `REQ-DEPS-REQUIREMENTS-01` | Каждую зависимость проследить до active functional contract либо оставить UNRESOLVED | 84 manifest items, direct 32 vs 52, loaded distributions/native DLL + workspace tests pending; [ledger](../04-dependencies/full-requirements-runtime-evidence-ledger.md) |


## Source → Capability → Requirement → Validation (продолжение)

| Source → Capability / статус | Requirement | Возможный функциональный владелец (не целевая Rust-структура) | Проверка паритета |
|---|---|---|---|
| `rag_manager.py`, `history_repo.py`, `memory_repo.py`, retrievers → `CAP-RAG-INDEX-001—003` CONDITIONAL | `REQ-RAG-INDEX-001—003` | RAG corpus query, index lifecycle | active/archive scope, eternal_id vs row id, forgotten/islands, per-model missing/all reindex, cancellation; [audit](../01-functional/rag-storage-retrieval-and-indexing-modes.md) |
| Installable specs, FFmpeg/OpenCV/voice/Beat/RAG status → `CAP-INSTALL-PROBE-*` CONDITIONAL | `REQ-INST-PROBE-001—006` | Component catalog and operations | mixed installed/ready/available, voice all vs one, clean/repair/update, remote RAG; [audit](../01-functional/installable-component-probe-and-operation-contracts.md) |
| `asr_models/registry.py`, `speech_recognizer_base.py`, `voice_models/base_model.py` → `CAP-AI-MODEL-*` CONDITIONAL | `REQ-AI-MODEL-001—005` | ASR/TTS managed Python worker + model lifecycle | all 5 ASR IDs, engine/model/voice weights, required backend, init vs installed; [audit](../01-functional/asr-tts-managed-backend-operational-contracts.md) |
| `models_loaded_dialog.py`, `api_settings/test_mixin.py`, `voiceover_controller.py` → `CAP-UI-MODEL/VOICE/DEPS` ACTIVE/COND | `REQ-UI-MODEL-001—003`, `REQ-UI-VOICE-001`, `REQ-UI-DEPS-001`, `REQ-UI-REACH-001` | model discovery UI/voice load progress | no info vs info, query/filter/copy/selection, stale request and hide vs cancel, reachable modal only; [audit](../02-ui/api-model-discovery-and-conditional-dialogs.md) |
| `game_settings.py`, `CharacterRegistry`, `GameLinkService` → `CAP-GAME-UI-001—002` ACTIVE/COND | `REQ-GAME-UI-001—002`, `REQ-BEAT-UI-001` | mini-game launch and Beat cache UX | distinct Unity/Sandbox targets and cancel, three permission gates, cache UI enabled/busy; [audit](../02-ui/game-settings-manual-launch-and-beat-cache.md) |
| `screen_analysis_settings.py`, `image_cleanup.py`, `create_task.py` → `CAP-SCREEN/CAMERA/IMAGE/MITA-CAM` COND | `REQ-IMAGE-UI-001—005` | media acquisition, housekeeping, Unity snapshot | single screen shot vs buffer/periodic, external camera, image provenance, orphan scan/cleanup, Unity event; [audit](../02-ui/screen-camera-image-management-user-contracts.md) |

Пункты Validation — **планы проверок паритета**, а не утверждение об уже пройденных E2E тестах. GUI/Win/CUDA/Unity/network в этом проходе не запускались.

## Дополнение: runtime достижимость внешних интеграций

| Source and capability | Requirement | Owner candidate | Validation |
|---|---|---|---|
| `main_controller.py; model_controller.py; web/server.py; connetors/hoi4` → `CAP-EXT-ROUTE-001—004` COND/UNRESOLVED | `REQ-EXT-ROUTE-001—003` | external integration activation and transport identity | installed Telethon vs logged in; enabled tools vs executed; standalone web server and prototype not counted active; [audit](../01-functional/external-integration-entrypoints-and-reachability.md) |


## Дополнение: RAG retrieval decisions

| Source/capability | Requirement | Scope | Parity validation |
|---|---|---|---|
| `rag_manager.py:821-1102; pipeline/query_builder.py; combiner.py; reranker.py; cross_encoder.py` → `CAP-RAG-RANK-001—003` CONDITIONAL | `REQ-RAG-RANK-001—004` | Query/identity, candidate fusion and rank, optional Python CE | explicit vs auto, union/vector/intersect/two_stage/rrf, actor tags, graph quota, provenance and async access stats; [audit](../01-functional/rag-query-fusion-reranking-and-result-contracts.md) |


## Дополнение: RAG → Prompt

| Source/capability | Requirement | Functional responsibility | Validation |
|---|---|---|---|
| `model_controller.py:1384-1405,1996-2120; prompt_controller.py:1080-1185` → `CAP-RAG-PROMPT-001—003` CONDITIONAL | `REQ-RAG-PROMPT-001—004` | generate-time retrieval eligibility and source render | per-character/special react gate, empty or multi-source, custom template, graph fallback, fresh Unity context placement; [audit](../01-functional/rag-context-injection-and-source-rendering.md) |

### Дополнение: локальный control-plane

| Source/capability | Requirement | Functional responsibility | Validation |
|---|---|---|---|
| `core/runtime_ipc.py; services/runtime_ipc_service.py; main_controller.py:121-127,218,684-686` → `CAP-LOCAL-IPC-001—003` CONDITIONAL | `REQ-LOCAL-IPC-001—003` | runtime external admin command endpoint | settings enable/port without restart, six allowlisted methods, error types, AI service restart; [audit](../01-functional/local-runtime-ipc-external-control-contract.md) |

### Дополнение: first-run consent → Guide

| Source/capability | Requirement | Functional responsibility | Validation |
|---|---|---|---|
| `app_window_base.py:1660-1710; eula_widget.py:166-248; localization/eula_texts.py` → `CAP-UI-ONBOARD-001—003` CONDITIONAL | `REQ-UI-ONBOARD-001—003` | consent state and first-use guidance | first/new launch, localized consent, accept/reject, language restart branch, Guide→Wiki; [audit](../02-ui/first-run-agreement-language-and-guide-flow.md) |

### Дополнение: native Windows/Core boundary

| Source/capability | Requirement | Functional responsibility | Validation |
|---|---|---|---|
| `hardware_inventory_service.py; windows_endpoint_identity.py; unity_process_guard.py; chatgpt_plan_auth.py; native_paths.py` → `CAP-DEPS-NATIVE-001—004` ACTIVE/COND | `REQ-NATIVE-001—004` | Hardware + OS adapters vs Python AI model native runtime | no-driver/multi-GPU identity, endpoint disappearance, Unity process close, credentials secure store, model DLL boundary; [audit](../04-dependencies/native-system-api-and-ai-library-ownership.md) |


## Дополнение: AI Hub и пользовательские статусные проекции

| Capability / status | Source → specification | Requirement | Functional owner candidate | Future validation |
|---|---|---|---|---|
| `CAP-INSTALL-ID-001—003` ACTIVE/COND | `catalog_manifest.py:42-1042`, `installable_catalog_service.py:206-316`; [catalog](../01-functional/installable-catalog-identity-and-coverage.md) | `REQ-INSTALL-ID-001—004` | component catalogue/identity | 31 fixed IDs, custom RAG, aggregate lookup, type/readiness |
| `CAP-INSTALL-OBS-001—003` ACTIVE/COND | `installable_catalog_service.py:616-924`, `ai_hub_view_model.py:300-397`; [observation](../03-runtime/installable-status-observation-and-invalidation.md) | `REQ-INSTALL-OBS-001—004` | readiness observation | pending/stale/timeout, invalidate, late status event |
| `CAP-INSTALL-QUEUE-001—003` ACTIVE/COND | `installable_controller.py:165-275`, `install_gui_controller.py:22-392`; [queue](../03-runtime/install-operation-admission-queue-and-completion.md) | `REQ-INSTALL-QUEUE-001—005` | install command admission & execution | duplicate, FIFO, cancel, quiesce, headless, recheck |
| `CAP-UI-AIHUB-ACTIONS` ACTIVE/COND | `ai_hub_view_model.py:71-542`, `ui/windows/ai_hub/dialog.py`; [UI action map](../02-ui/ai-hub-interaction-traceability-checklist.md) | `REQ-UI-AIHUB-ACTIONS-001—004` | AI Hub presentation | category/filter, progress/logs/dirty guard, async status |
| `CAP-UI-STATUS-001—002` ACTIVE/COND | `status_controller.py:17-205`, `app_window_base.py:1335-1412`, `mita_status_widget.py`; [status](../02-ui/generation-progress-error-and-voice-indicators.md) | `REQ-UI-STATUS-001—004` | dialogue presentation | thinking/compression/tool/voice/error, per-message identity |

## Срез текущего прохода: новые capability → requirement → future validation

| Capability / статус | Source / функциональная спецификация | Requirement | Owner candidate по смыслу, без утверждения архитектуры | Validation (будущий parity fixture) |
|---|---|---|---|---|
| `CAP-CONTENT-001—004` ACTIVE | `src/core/message_content.py:40-258`; [проекции](../01-functional/multimodal-message-content-representations.md) | `REQ-CONTENT-001` | Message content / projection | text+image+unknown type → provider/summary/embedding/DB/UI без потери media |
| `CAP-TV-001—003` CONDITIONAL | `src/core/tv_observation.py:7-78`, `src/managers/conversation_event_writer.py:221-271`; [TV](../01-functional/tv-observation-youtube-frame-and-dialogue-provenance.md) | `REQ-TV-001` | Media observation provenance | YouTube vs player vs in-game image, 8 frames, timestamps, TV-only event |
| `CAP-DATA-WORLD-001—003` ACTIVE | `src/managers/database_manager.py:1515-1850`, `src/ui/dialogs/db_export_dialog.py`; [JSON](../01-functional/world-db-json-export-import-user-workflow.md) | `REQ-WORLD-EXPORT-001` | User data portability | current/all scope, flags, statuses, filter/date, import override, no embeddings |
| `CAP-EMBED-WIRE` CONDITIONAL | `src/handlers/embedding_providers/registry.py`, `gemini_provider.py`, `openai_compat_provider.py`; [embeddings](../01-functional/embedding-provider-wire-and-failure-contracts.md) | `REQ-EMBED-WIRE-001` | Retrieval integration boundary | mock local/cloud batches, id/ordering, query/document and errors |
| `CAP-TELEGRAM-BOT` CONDITIONAL | `src/handlers/telegram_handler.py`; [routing](../01-functional/telegram-bot-protocol-routing-and-session-semantics.md) | `REQ-TELEGRAM-DELIVERY-001` | Voice transport / auth | auth codes, wait/timeout, audio routing Unity vs desktop, offline gate |
| `CAP-INSTALL-OPS` CONDITIONAL | `src/installables/catalog_manifest.py`, `src/services/installable_catalog_service.py`; [families](../01-functional/installable-families-runtime-operations.md) | `REQ-INSTALL-OPS-001` | Installable lifecycle | status/plan/initialize/uninstall matrix for 31 static and dynamic RAG |
| `CAP-UI-KEYBOARD` ACTIVE/CONDITIONAL | `src/ui/windows/app_window_base.py`, `src/ui/dialogs/db_viewer.py`; [interactions](../02-ui/keyboard-clipboard-and-direct-manipulation-contracts.md) | `REQ-UI-KEYBOARD-001` | Presentation actions | Enter/Shift+Enter, paste image, search, hotkeys, cell edit/delete |
| `CAP-UI-DEVICE-BEHAVIOR` CONDITIONAL | `src/core/setting_behaviors.py:6-40`; [voice UI](../02-ui/voice-controls.md) | `REQ-UI-DEVICE-001` | Device-sensitive configuration | CUDA ordinal differences, backend value normalization, UI enabled/disabled |
| `CAP-DIAG-TRACE-001—002` ACTIVE | `src/core/performance_trace.py`, `src/controllers/chat_controller.py`; [traces](../03-runtime/per-request-performance-traces-and-diagnostic-metrics.md) | `REQ-RUNTIME-TRACE-001` | Request observability | queue→stream event/text→TTS/playback, bounded trace summaries, no prompt leaks |
| `CAP-TEST-CORPUS` evidence only | `src/utils/Testing/test_*.py`; [validation corpus](existing-test-corpus-and-functional-parity-gates.md) | `REQ-TEST-PARITY-001` | Validation / parity suite | offline fixture vs Windows/Unity/AI/network external tests |
| CAP-DIALOGUE-IDENTITY-001—004 · ACTIVE/COND | `src/services/dialogue_identity_resolver.py`, `src/managers/conversation_event_writer.py`, `src/domain/conversation_message_ids.py`, `src/services/dialogue_target_resolver.py`; [identity](../01-functional/dialogue-actor-and-message-identity-contracts.md) | REQ-DIALOGUE-IDENTITY-001—002 | identity/provenance of dialogue events | two spawned actors one character, ambiguous target, player provenance, cross-recipient fanout, no duplicate origin |
| CAP-DIALOGUE-IDENTITY-005 · EXP/UNRESOLVED | `src/services/dialogue_transcript_service.py`; [identity](../01-functional/dialogue-actor-and-message-identity-contracts.md) | Не обязательное до подтверждения runtime registration | optional GM short-lived transcript | production composition reachability + scene lifetime |
| CAP-STREAM-001—003 · ACTIVE/COND | `src/services/llm_stream.py`, `src/handlers/llm_providers/streaming.py`, `src/controllers/chat_controller.py`; [stream](../03-runtime/llm-stream-event-and-presentation-lifecycle.md) | REQ-STREAM-001 | request streaming and presentation | start/delta/reasoning/role flush/terminal, cancel/fail, test coalescer batching |


## Pass 11 — explicit source → capability → requirement → validation

| Capability | Source evidence | Requirement family | Behavior owner, не проектный класс | Validation gate |
|---|---|---|---|---|
| `CAP-DSL-EXEC-001…` (ACTIVE/CONDITIONAL) | `src/controllers/prompt_controller.py:400-485; src/DSL/dsl_engine.py:422-1004`; [спецификация](../01-functional/dsl-executable-prompt-contract.md) | `REQ-DSL-EXEC-001…` | prompt building, author DSL, controlled side effects | prompt sample: nested includes, two characters, RAG unavailable, seed state; offline DSL fixtures |
| `CAP-POSTDSL-001…` (ACTIVE/CONDITIONAL) | `src/characters/character.py:409-631; src/DSL/post_dsl_engine.py:43-376`; [спецификация](../01-functional/post-dsl-response-rules-and-debug-state.md) | `REQ-POSTDSL-001…` | post-generation transformation and custom state | text/regex/capture/FIELD ordering, no-postscript, player state, debug display |
| `CAP-MINIGAME-DETAIL-001…` (CONDITIONAL) | `src/managers/game_manager.py:11-173; src/modules/Chess/game_instance.py:143-239; src/modules/SeaBattle/seabattle_instance.py`; [спецификация](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md) | `REQ-MINIGAME-DETAIL-001…` | two rulesets and game-bound character reactions | chess move/engine response; sea-battle turn and hidden knowledge; game exit, manual launch |
| `CAP-ACTION-HISTORY-001…` (CONDITIONAL) | `src/managers/action_memory.py:10-178; src/controllers/history_controller.py:248-302,1325-1355,1822-1830`; [спецификация](../01-functional/structured-action-history-and-compression-bridge.md) | `REQ-ACTION-HISTORY-001…` | retained requested action context across summary | structured segments, summary commit/abort, disabled flag, bounded rolling window |
| `CAP-CORE-TRIGGER-001…` (CONDITIONAL) | `src/managers/core_memory_triggers.py:24-136; src/controllers/model_controller.py:1380-1407`; [спецификация](../01-functional/exact-core-memory-triggers-and-session-activation.md) | `REQ-CORE-TRIGGER-001…` | deterministic story state distinct from access control | exact match, per-character sticky and reset, no authorization; unit tests |
| `CAP-MIC-001…` (CONDITIONAL) | `src/services/microphone_selection.py; src/services/microphone_monitor.py; src/infrastructure/audio/portaudio_catalog.py`; [спецификация](../01-functional/microphone-physical-identity-backends-and-monitoring.md) | `REQ-MIC-001…` | physical microphone selection, monitoring and hotplug | WASAPI/DS/MME dedup and selection, two sampling clocks, hotplug |
| `CAP-SPEECH-ARBITER-001…` (ACTIVE/CONDITIONAL) | `src/controllers/speech_controller.py; src/managers/speaking_window.py; src/game_connections/handlers/actions/speech_state.py`; [спецификация](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md) | `REQ-SPEECH-ARBITER-001…` | microphone gating against local+Unity playback | overlapping leases, disconnect, lost end-of-speech, PTT owner/ack |
| `CAP-EVENT-ROUTE-001…` (ACTIVE/CONDITIONAL) | `src/core/events.py`; [спецификация](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md) | `REQ-EVENT-ROUTE-001…` | event fact/command/progress distinction | command accepted vs effect completed; event order; GUI-only routing |
| `CAP-UNITY-INGRESS-001…` (ACTIVE/CONDITIONAL) | `src/game_connections/server.py; src/controllers/server_controller.py`; [спецификация](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md) | `REQ-UNITY-INGRESS-001…` | seven inbound Unity request families and ownership | handshake, task status, settings, music chunks, speech and PTT |
| `CAP-GUI-ASYNC-001…` (ACTIVE/CONDITIONAL) | `src/controllers/gui/intent_view_model.py:18-387; src/controllers/gui/gallery_page_view_model.py:43-128`; [спецификация](../02-ui/intent-workloads-and-visible-state-consistency.md) | `REQ-GUI-ASYNC-001…` | freshness, exclusive side effects, refresh coalescing | inverted completion order, duplicate submit, refresh burst, close during operation |
| `CAP-HEADLESS-SURFACE-001—005` CONDITIONAL | `src/__main__.py:59-122,317-352`; `src/startup/headless_runtime.py:14-157`; [контракт](../03-runtime/headless-core-functional-surface-and-readiness.md) | `REQ-HEADLESS-SURFACE-001—005` | Game-linked headless runtime | no-GUI boot, server readiness, worker status, bounded run, signal stop, missing Telegram GUI code/2FA, 6 offline unit tests | 
| `CAP-INSTALL-FIXTURE` evidence/validation | `src/installables/catalog_manifest.py:42-1042`; [31-component matrix](installables-component-by-component-parity-matrix.md) | `REQ-INSTALL-FIXTURE-001` | per-component identity/status/ops | each installable actual machine requirements, install/update/uninstall, model init, downloads, recoveries, 0/31 E2E so far |
**Evidentiary boundary:** для `CAP-EVENT-ROUTE-*` [индекс 288 событий](../00-research/event-producer-consumer-callsite-index.md) показывает факты исходного AST, а не автоматическую регистрацию каждого маршрута. Для `CAP-GUI-ASYNC` найдены 52 прямых callsites в 20 view-model modules; один callsite не означает активность без маршрута экрана.


**Негативные свидетельства:** [standalone и непроверенные dynamic calls](../00-research/standalone-and-unproven-runtime-reachability.md) — не source→obligatory requirement, пока нет доказанного active path.

## Pass 12 — новые проверяемые пользовательские ветви

| Capability/status | Source → behavioral contract | Requirement | Functional responsibility candidate (НЕ целевой Rust модуль) | Validation |
|---|---|---|---|---|
| `CAP-UI-DIALOG-001—003` · ACTIVE/COND | `ui/window_manager.py`, `controllers/gui/window_composition_controller.py`, `protocol_pipeline_gui_controller.py`; [достижимость](../02-ui/dialog-class-reachability-and-action-outcomes.md) | `REQ-UI-DIALOG-001—003` | UI window lifecycle, user command admission | Реальный open/close/reopen и pending-changes, headless non-Qt |
| `CAP-UI-NATIVE-001—003` · ACTIVE/COND | 16 file-pickers / 8 short input calls; [matrix](../02-ui/native-dialogs-and-file-input-output-workflows.md) | `REQ-NATIVE-DIALOG-001—004` | пользовательские filesystem inputs и application intents | cancel vs file chosen vs background completion; per-character/all scope |
| `CAP-UI-CONFIRM-001—003` · ACTIVE/COND | 29 `QMessageBox.question` callsites и custom RAG Apply; [matrix](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md) | `REQ-UI-CONFIRM-001—004` | подтверждение опасной операции и переходов состояния | No/Cancel/Yes; save/discard/cancel; late success/failure |
| `CAP-RAG-PRESET-001—003` · ACTIVE/COND | 4 built-ins, user snapshot, separate model status; [presets](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md) | `REQ-RAG-PRESET-001—004` | user retrieval configuration | selected≠applied≠model ready; user snapshot with None; missing models queue |
| `CAP-GRAPH-INGEST-001—003` · COND | `graph_controller.py`, `rag_memory_controller.py`; [graph paths](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md) | `REQ-GRAPH-INGEST-001—004` | source-to-knowledge provenance and retrieval visibility | inline structured/legacy vs realtime vs manual 4 batch modes |
| `CAP-EVENT-RAW-001—002` · ACTIVE/COND | raw name EventBus/UI bridge; [evidence](../00-research/raw-string-event-reachability-and-ui-bridges.md) | `REQ-RAW-EVT-001—004` | history page load, periodic observation, GUI progress | request identity and late async delivery |
| `CAP-SET-RAG-CONSUMER-001` · MIXED | 99 keys and external literal consumers; [index](../00-research/rag-settings-direct-consumer-evidence-index.md) | `REQ-SET-RAG-001—003` | settings-to-feature effects | runtime consumer, key schema, type/default/restart, alias |
| `CAP-UI-SIGNAL-001—002` · STATIC | `ui/**`, `controllers/gui/**` AST `.connect`; [517 callsites](../00-research/gui-signal-registration-callsite-index.md) | `REQ-UI-SIGNAL-001—003` | concrete UI events and action routing | verify downstream handler per active widget; Qt E2E needed |
| `CAP-DEPS-PROCESS-001—003` · COND | `ffmpeg_installer`, `audio_converter`, `archive_utils`, `worker_process`, `hardware_inventory_service`; [boundary](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md) | `REQ-EXE-001—004` | subprocess/media and native platform ops; AI separate | missing external tool, Unicode paths, cancel, independent AI worker |

| `CAP-RAG-READY-001..004` | RAG readiness, warmup and worker generations | `src/managers/rag/readiness.py`, `src/controllers/embedding_controller.py`, `src/managers/rag/pipeline/cross_encoder.py`, `src/controllers/reranker_controller.py` | ACTIVE/CONDITIONAL | `REQ-RAG-READY-001..004` | Unselected; after audit | `test_rag_restart_state.py`, 14 addressed tests across 3 modules |

| `CAP-RAG-GOLDEN-001..002` | RAG retrieval source identity and result shape | `src/managers/rag/pipeline/types.py`, `src/managers/rag/rag_manager.py` | ACTIVE | `REQ-RAG-GOLDEN-001..003` | Unselected; after audit | `test_rag_units_golden.py`, `test_rag_search_golden.py` 18 passed, 8 subtests |

| `CAP-HISTORY-VIEW-001..003` | История: projected role, actor identity, paging | `src/managers/history_ui_projector.py`, `src/controllers/model_controller.py` | ACTIVE | `REQ-HISTORY-VIEW-001..003` | Unselected; after audit | 22 passed across history UI/sender/epoch modules; live GUI pending |

| `CAP-DYNIMPORT-001..009` | Dynamic registries and optional capabilities | `src/managers/provider_manager.py`, `src/handlers/asr_models/registry.py`, `src/managers/tools/tool_manager.py`, `src/installables/registry_builder.py`, `src/ui/pages/main_page_registry.py`, `src/handlers/ai_engine/worker_process.py` | ACTIVE/CONDITIONAL | `REQ-DYNIMPORT-001..004` | No Rust technology selected | registry IDs, lazy/failed optional import, process-scoped AI worker probes; Windows/AI E2E open |
