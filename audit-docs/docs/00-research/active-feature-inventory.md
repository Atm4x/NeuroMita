# Реестр функциональной поверхности

**Актуальный объединённый каталог — [Pass 13](current-functional-baseline.md).** Ниже сохраняется накопительный реестр: ранние пометки «дальше/не завершено» уточняются последующими дополнениями и текущим срезом. Это рабочий реестр, не финальная сертификация паритета. «Регистрация подтверждена» означает найденный runtime-путь до создания/планирования компонента; не означает, что все его возможности исследованы.

Pass 13 уточняет [RAG recall/model space](../01-functional/rag-mixed-model-recall-and-provenance.md), [settings semantics](../02-ui/memory-rag-settings-consumer-semantics.md), [history receiver](../02-ui/history-page-fencing-and-live-replay.md), [обмен World DB](../01-functional/world-db-exchange-isolated-validation.md), [authoring/node editor](../02-ui/prompt-editor-authoring-and-node-workflow.md), [installable family outcomes](../06-design-input/installables-component-by-component-parity-matrix.md) и [core alternatives](../04-dependencies/core-niche-alternatives-and-parity-gates.md). Эти уточнения не добавляют дублирующие capabilities к знаменателю.

| ID / область | Статус | Доказательство | Глубина |
|---|---|---|---|
| CAP-RUN-001 режимы | ACTIVE | E-001, E-003 | Спецификация в startup-and-shutdown |
| CAP-RUN-002 shell-first запуск | ACTIVE | E-002, E-007, E-013 | Основной путь и гонки; UI states дальше |
| CAP-RUN-003 headless | CONDITIONAL | E-008 | Host разобран; ограничения отдельных функций дальше |
| CAP-RUN-004 shutdown | ACTIVE | E-011, E-017 | Порядок разобран; внутренние supervisors дальше |
| CAP-RUN-005 availability lifecycle | ACTIVE | E-010, E-012 | Реестр/DAG/retention/late completion разобраны |
| CAP-LLM-001 dialogue turn | ACTIVE | ChatController → ModelController → ChatModel/runner | Основной orchestration, policies и delivery описаны; providers/tools не завершены |
| CAP-LLM-002 structured effects/tool continuation | CONDITIONAL | ModelController structured branch | Orchestration описан; parser/effect implementations не завершены |
| CAP-LLM-003 retry/fallback/deadlines | ACTIVE | LLMRequestRunner, ApiPresetResolver | Основной путь описан; transport/cancel details дальше |
| CAP-PROMPT-001 context composition | ACTIVE | PromptController.build | Основной builder описан; DSL/assets не завершены |
| CAP-PROMPT-002—006 packs/DSL/Post-DSL | ACTIVE/CONDITIONAL | DslInterpreter/PostDslInterpreter/catalogue/downloader | Runtime execution и основные content operations описаны; packs выборочно, editor отдельный и частично исследован |
| CAP-HIST-001 history fanout | ACTIVE | ConversationEventWriter/HistoryManager | Per-recipient batch, partial failures описаны |
| CAP-HIST-002 delete/edit | ACTIVE | Chat message intents → event bus → ChatController | Основной mutation path; concurrent consistency дальше |
| CAP-HIST-003 regenerate | ACTIVE | ChatController handlers | Основные ветвления; UX и state semantics дальше |
| CAP-HIST-004 snapshots/system insertion | ACTIVE | AppShellController → ChatController/HistoryManager | Export/import merge semantics описаны |
| CAP-DELIVERY-001 retry outbox | CONDITIONAL | ChatController/UnityRetryStore | Persistence/retry/recovery описаны; server acknowledgement дальше |
| CAP-API-001—005 presets/protocol configuration | ACTIVE/CONDITIONAL | ApiPresetsController/resolver/model settings/GUI | Основные CRUD/select/test/catalog/parameters/storage paths описаны; migrations/Gemini/transforms/editor tails дальше |
| CAP-AUTH-PLAN-001 accounts | EXPERIMENTAL/CONDITIONAL | ChatGPTPlanAuth/provider/provider_settings/API GUI | Login/PKCE/token/DPAPI/refresh/accounts/exit описаны; remote availability не проверялась |
| CAP-CHAR-001 персонажи/state/reset | ACTIVE | CharacterManager/Registry/Character | Основные lifecycle и state effects описаны; GUI/custom content дальше |
| CAP-HIST-005 context/compression | ACTIVE | HistoryController | Window, layered/rollup, epochs, maintenance описаны |
| CAP-MEM-001 memory CRUD/lifecycle | ACTIVE | MemoryManager | Identity, islands, seeds, forgetting/TTL/purge описаны |
| CAP-RAG-001 retrieval/indexing | CONDITIONAL | RAGManager/pipelines/retrievers | Основной search и ranking; full reindex/GUI ещё не закрыты |
| CAP-GRAPH-001 extraction/query | CONDITIONAL | GraphController/GraphStore | Основные extraction/store/query; GC/retyping/GUI дальше |
| CAP-REM-001 reminders/timers | CONDITIONAL | ReminderManager/Controller | Persistence/scheduler/delivery описаны |
| CAP-AI-001 IPC/supervision | ACTIVE | AIEngineController/worker_process | Основные transport/deadline/recovery разобраны |
| CAP-AI-002 environments | ACTIVE/CONDITIONAL | RuntimeEnvironmentManager/AIEngineController | Composition/switch/transaction разобраны; installer операции дальше |
| CAP-VOICE-001 synthesis/delivery | CONDITIONAL | AudioController/LocalVoiceController/RemoteVoiceService | Основной Local/API/playback; Telegram и UI не завершены |
| CAP-SPEECH-001 voice input | CONDITIONAL | SpeechController/ASRInputGate/AudioCaptureService | Lifecycle/segmentation/routing описаны; endpoint/monitor/UI дальше |
| CAP-TG-001 Telegram voice/auth | CONDITIONAL | TelegramController/Handler/AuthService | Основной subsystem описан; auth dialogs и внешняя актуальность дальше |
| CAP-IMAGE-001—006 изображения/экран/камера | CONDITIONAL | CaptureController/handlers/AppShell/HistoryManager/image_cleanup | Python acquisition/staging/description/storage/manual cleanup описаны; game producers отложены; TTL settings без найденного runtime consumer |
| CAP-TASK-001 tasks | ACTIVE | TaskManager/TaskController | In-memory snapshots/revisions/status merge прочитаны; все consumers ещё проверить |
| CAP-INSTALL-001 catalog/queue/plans | CONDITIONAL | InstallableController/InstallController/Catalog | Основной pipeline описан; component plans/progress/manual removal дальше |
| CAP-UI-AIHUB-001 | ACTIVE | AIHub viewmodels/dialog/cards | Основные actions/states/settings описаны; layout/renderer/runtime QA дальше |
| CAP-UI-NAV-001 / CAP-GALLERY-001 / CAP-NEWS-001 / CAP-HELP-001—002 / CAP-LOGS-001 | ACTIVE/CONDITIONAL | MainPageRegistry/coordinator/settings registry/page viewmodels | Основные navigation/gallery/news/wiki/guide/log functions описаны; home/sandbox и оставшиеся dialogs дальше |
| CAP-UNITY-001 transport/delivery | ACTIVE | Python server/controller + Unity Network | Оба конца основного TCP transport описаны, application ACK отсутствует |
| CAP-UNITY-002 media/settings | CONDITIONAL | shared_image_transfer / SharedImageTransfer / SettingsUpdateHandler | Основной contract, file cleanup и projection описаны; producers дальше |
| CAP-UNITY-003 admission/auto dialogue | ACTIVE/CONDITIONAL | DialogueTurnCoordinator/SpeakerOrder/Idle/ASR | Основные policies описаны; executor/presentation/identity construction дальше |
| CAP-LAUNCH-001 / CAP-UPDATE-001—004 | ACTIVE/CONDITIONAL | Home/controller/updater/transaction/activation/process guards | Основные check/install/resume/restart/process flows описаны; external extractors/release helpers/settings/native launcher tails дальше |
| CAP-DIAG-001—003 / CAP-DATA-001—003 | ACTIVE/CONDITIONAL | Sandbox/ContextViewer/ChatModel/collectors/export | Основные selectors/debug/request snapshots/dataset/rating/filters/export описаны; DB viewer и rendering tails дальше |
| CAP-IPC-CTRL-001 | CONDITIONAL | RuntimeIPCService/IPCRegistry/decorated methods | Loopback controls, JSON protocol, allowlist/lifecycle описаны; не AI transport |
| CAP-I18N-001—002 / CAP-UI-PREF-001 | ACTIVE | localization/live/schema/language/general settings | Catalogs/live labels/user locales/presentation preferences описаны; all-strings/runtime QA не было |
| Prompt editor submodule | CONDITIONAL, отдельная программа | main.py/PySide6/menu/preview, core references не найдены | Entry/preview/functions подтверждены; full editor/node audit не завершён; обязательная core зависимость не доказана |
| CAP-GAME-001—004 desktop mini-games | CONDITIONAL | available_games/GameManager/ChessGame/SeaBattleGame/manual launch | Две регистрации и основные gameplay/UI/LLM/engine/lifecycle paths подтверждены; helper/installer edge cases дальше |
| CAP-WEB-001/002 VTT/mock API | standalone/EXPERIMENTAL | web/server.py/router/service, normal startup callsites не найдены | Функции прочитаны; не считать core HTTP service без отдельного требования |
| Остальные GUI/tools/integrations | UNRESOLVED | Требуется полный discovery | Не исследованы |
| CAP-TOOLS-001—006 | CONDITIONAL | ToolManager/ModelController/builtin/native_tool_calls | Шесть операций, activation, native/schema, continuation и scope описаны; внешние API не запускались |
| CAP-BEAT-001—004 | CONDITIONAL | GetMusicBeatsAction/BeatService/worker/BeatSettings | Python analysis/cache/batch/settings описаны; client animations отложены; component install tails дальше |

## Дополнение текущего Python-прохода

| ID / область | Статус | Доказательство / покрытие |
|---|---|---|
| CAP-CONFIG-001 settings store | ACTIVE | SettingsManager/Registry/Service: read/load/async save/subscriptions/shutdown; [разбор](../03-runtime/settings-and-preferences-store.md) |
| CAP-CHAR-005 character settings | ACTIVE | Выбор конфигурируемого character отдельно от active, provider/pack/reload/folders; [разбор](../01-functional/characters.md) |
| CAP-DATA-004—005 DB viewer/exchange | ACTIVE | Прямой Qt SQL editor, images metadata, selected/all import/export; [разбор](../01-functional/data-maintenance.md) |
| CAP-RAG-002 reindex | CONDITIONAL | Missing/full/current/all, batch commits/cancel, различия tail/cache; [разбор](../01-functional/data-maintenance.md) |
| CAP-GRAPH-002—004 maintenance/view | CONDITIONAL | Manual extraction/processed ledger/GC/delete/type backfill/graph interactions; painter и rule tables частично; [разбор](../01-functional/data-maintenance.md) |
| CAP-MEM-002 semantic dedup | CONDITIONAL | Preview/cosine/canonical/apply through merge; model space scope не ограничен; [разбор](../01-functional/data-maintenance.md) |
| CAP-DATA-006—009 compatibility | CONDITIONAL | Recovery ZIP/JSON/preview/ledger, local JSON→DB, structured migrations, identity history dedup; [разбор](../01-functional/compatibility-imports.md) |
| CAP-VOICE-002—005 / CAP-TG-002 controls | CONDITIONAL | Local catalog/settings/admission/init/cancel, remote profiles/preview/character overrides, Telegram dialogs; [разбор](../02-ui/voice-controls.md) |
| CAP-JOB-001—003 / CAP-EVENT-001 | ACTIVE | GUI task ownership/resources, thread/future supervision/deadlines, pools/backpressure, bus delivery/ordering; [разбор](../03-runtime/background-tasks-and-events.md) |

Эти строки уточняют глубину старых broad rows, а не добавляют повторные независимые функции. Предыдущие пометки «GUI/reindex/GC дальше» закрыты в основных перечисленных paths; оставшиеся границы указаны в linked documents. Полнота не вычислена: полный знаменатель capabilities пока неизвестен.

## Дополнение: проход provider + component + failure policy (2026-10-30)

| ID / область | Статус | Доказательство / пределы |
|---|---|---|
| CAP-API-006 message transforms | CONDITIONAL | `message_transforms.py:41-445`; каталог пяти шагов и их поведение, ранее незакрытый gap [разобран](../01-functional/message-transforms.md); caller snapshots требуют fixture test |
| CAP-API-007 Gemini wire adaptation | CONDITIONAL | `gemini_provider.py:27-581`; request/stream/usage/schema/error flow [разобран](../03-runtime/provider-wire-contracts.md); remote semantics не проверена |
| CAP-AUTH-PLAN-002 direct transport | EXPERIMENTAL/CONDITIONAL | `chatgpt_plan_provider.py:19-191`, `chatgpt_plan_protocol.py`; strict endpoint/OAuth/SSE/tool gate [разобраны](../03-runtime/provider-wire-contracts.md); remote usage not verified |
| CAP-AI-003 fatal CUDA worker recycle | CONDITIONAL | `runtime_failure_policy.py` и worker dispatch/restart; [разбор](../03-runtime/cuda-fatal-worker-recovery.md); parent death-recovery tails не закрыты |
| CAP-INSTALL-002 component voice/media plans | CONDITIONAL | F5/Fish/Omni/EdgeRVC/FFmpeg/OpenCV main `build_install_plan`; [первичный разбор](../01-functional/installer-component-plans.md); ASR/Beat/RAG/voice assets остаются |

## Дополнение: Python protocol / install / release (2026-10-30, следующий проход)

| Capability | Статус | Подтверждённый путь и область | Результат / предел |
|---|---|---|---|
| CAP-PROTOCOL-CHAT-001 / CAP-PROTOCOL-RESPONSES-001 | CONDITIONAL | `src/handlers/llm_providers/protocols/{chat_completions,responses}/`, `openai_http_base.py`, `responses_provider.py` | [Состояния протоколов](../03-runtime/openai-protocol-state-machines.md): wire serialization/reasoning/tool IDs/stream terminal/schema fallback; реальные API calls не выполнялись |
| CAP-INSTALL-ASR-001 | CONDITIONAL | `src/handlers/asr_models/*`, `src/installables/catalog_manifest.py:489-616`, backend environment | [ASR планы](../01-functional/asr-rag-beat-install-plans.md): пять recognizers, readiness отличается от наличия весов; dependency activation отдельно |
| CAP-INSTALL-RAG-001 | CONDITIONAL | `src/managers/rag/install_spec.py`, installables | [RAG планы](../01-functional/asr-rag-beat-install-plans.md): install per settings/per model; uninstall noop и file readiness требует проверки |
| CAP-INSTALL-BEAT-001 | CONDITIONAL | `src/game_connections/services/beat_install.py`, backend service | [Beat install plan](../01-functional/asr-rag-beat-install-plans.md), cache/analysis ранее в music-beats |
| CAP-VOICE-ASSETS-001 | CONDITIONAL | `src/installables/voice_assets.py`, `src/utils/voice_assets_installer.py` | [Voice bundle lifecycle](../01-functional/voice-asset-distribution.md): model manifest/asset extraction, uninstall false-result divergence |
| CAP-INSTALL-LIFECYCLE / CAP-INSTALL-CANCEL / CAP-INSTALL-UNINSTALL / CAP-INSTALL-REPAIR | ACTIVE / CONDITIONAL | `src/controllers/install_controller.py:476-1501`, `src/utils/pip_installer.py:830-1173`, `src/core/runtime_environments.py:453-670,1244-1308` | [Installer recovery](../03-runtime/installer-recovery-and-uninstall.md), static only; clean reinstall — отдельная семантика |
| CAP-DIST-001—004 / CAP-RELEASE-VALIDATE-001 | CONDITIONAL | `build.py`, `scripts/launcher.c`, `run.bat`, `run.py`, `src/release_contract.py` | [Build/distribution](../03-runtime/build-and-release-distribution.md); native launcher post-exit activation подтверждена в C source, release pipeline полностью не собран |
| Rust Core dependencies / Python AI boundary | RESEARCH / частично | `requirements.txt`, 720 parsed Python AST files, `scripts/run.py`, feature import sites | [Предварительная dependency matrix](../04-dependencies/python-import-reachability.md); не доказан полный динамический callgraph |

Суммарный процент полноты по этой таблице **не вычисляется**, так как реестр ещё не является исчерпывающей capability universe. Эти строки расширяют функциональный охват, не заменяют предыдущие source paths.

### Отдельная пользовательская функция: токены и pricing

| Capability | Статус | Источники | Сценарии/границы |
|---|---|---|---|
| CAP-TOKEN-001 / CAP-PRICE-001—002 | ACTIVE / CONDITIONAL | `src/managers/{context_counter,model_pricing_manager}.py`, `src/controllers/model_controller.py:992-1154`, GUI | [Token estimate/pricing](../01-functional/token-budget-and-pricing.md): UI metric ≠ provider usage, async metadata cache and host-dependent prices; real API не вызывался |

### Статус внешнего standalone-прототипа

| Capability | Статус | Источники | Результат |
|---|---|---|---|
| CAP-HOI4-EXPERIMENTAL-001—002 | EXPERIMENTAL / UNRESOLVED | `src/connetors/hoi4/{hoi4_server,hoi4_connector,hoi4_cheats}.py`, Mod assets | [Проверка reachability и контракта](../01-functional/hoi4-standalone-prototype.md): основной runtime importer не найден; отдельный bridge с `dummy_ai_logic`, неполные mod hooks; не считать обязательным active паритетом без уточнения |

### Файловые границы и native loader

| Capability | Статус | Источники | Контракт |
|---|---|---|---|
| CAP-PATH-001—004 | ACTIVE / CONDITIONAL | `src/core/app_paths.py`, `src/core/runtime_environments.py`, RAG/ASR native loaders, `src/main_logger.py` | [Path/Unicode/log semantics](../03-runtime/filesystem-paths-and-native-loaders.md); различающиеся default для RAG checkpoint и native ASCII 8.3 bridge, только статическая проверка |

### HTTP ownership и ошибки

| Capability | Статус | Источники | Контракт |
|---|---|---|---|
| CAP-NETWORK-001—003 | ACTIVE / CONDITIONAL | `src/core/networking/{http_clients,errors}.py`, `handlers/llm_providers/http_transport.py` | [HTTP lifecycle/error classification](../03-runtime/network-client-ownership-and-errors.md): service-bound reference counts, masked diagnostics, разная retryability/timeout phase, tests read only |

## Продолжение: settings, service ownership и UI (2026-10-30, следующий проход)

| Capability | Статус | Доказательство / предел |
|---|---|---|
| CAP-SET-001—006 | ACTIVE/CONDITIONAL | `settings_manager.py`, `settings_registry.py`, `update_contour.py`, `api_presets_controller.py`, `model_settings/{schema,repository,service,migration}.py`, `chatgpt_plan_auth.py`; [settings/migrations](../01-functional/settings-storage-and-migrations.md). Не все ключи/consumer effects изучены. |
| CAP-SERVICE-001 / CAP-SET-OBSERVER-001 | ACTIVE | `core/services.py:85-227`, `core/settings_registry.py:45-347`; [typed services](../03-runtime/typed-services-and-settings-observers.md); cross-thread tests не запускались. |
| CAP-SET-GUI-BRIDGE-001 / CAP-UI-SET-001—003 | CONDITIONAL/ACTIVE | `ui/settings/settings_binding.py`, `ui/pages/settings/{section_registry,section_access,settings_page_widget}.py`; [settings UI](../02-ui/settings-navigation-and-lazy-pages.md). 12 registered sections, 83 literal keys в части builders; dynamic controls/all callbacks не закрыты. |

Контроль покрытия отдельным [ledger](audit-coverage-ledger.md) — `PRIMARY` означает исследование главного пути, а **не** полностью завершённый аудит. Прежние приблизительные 65–70% не используются как фактическая метрика.

## Новое покрытие source-to-capability: GUI, graph maintenance, character operations

| Capability | Статус, подтверждение | Документ |
|---|---|---|
| `CAP-UI-SET-004` | ACTIVE/CONDITIONAL: 83 literal keys, 5 зарегистрированных settings builders; не полный settings inventory | [Key consumer evidence](../02-ui/settings-key-consumer-evidence.md) |
| `CAP-GRAPH-MAINT-001—003` | CONDITIONAL: EntityGC, graph retype, merge/clear; не гарантируется atomic batch | [Graph lifecycle](../01-functional/graph-maintenance-and-entity-lifecycle.md) |
| `CAP-UI-GRAPH-001—003` | CONDITIONAL: filtered graph viewer/actions, UI cancel не означает atomic cancel | [Viewer](../02-ui/graph-viewer-interactions.md) |
| `CAP-UI-SANDBOX-001—003` | ACTIVE: sandbox viewmodel/tab controls/chat/game flags, remaining editors follow-up | [Sandbox](../02-ui/sandbox-page-functional-contract.md) |
| `CAP-UI-CHAT-001—005` | ACTIVE/CONDITIONAL: attachment capture, stream replay, message actions, structured visual projection | [Composer](../02-ui/chat-composer-and-attachments.md), [replay/actions](../02-ui/chat-stream-history-and-message-actions.md), [structured](../02-ui/structured-ai-results-presentation.md) |
| `CAP-UI-GALLERY-001` | ACTIVE: local Gallery source, watcher, bounded thumbnail cache, image viewer | [Gallery](../02-ui/gallery-lifecycle-and-photo-viewer.md) |
| `CAP-UI-CHAR-001—003` | ACTIVE/CONDITIONAL: selected vs active character, per-character/all operations, event/worker boundaries | [Character library](../02-ui/character-library-and-maintenance-actions.md) |

`GUI` и `RAG/graph` в [coverage ledger](audit-coverage-ledger.md) остаются `PARTIAL`: дополнительные подтверждённые пути **не** доказывают исчерпывающего списка действий, а `CAP` группы не являются счётчиком общего прогресса.

### Новости и логи: более глубокая проверка

| Capability | Статус и evidence | Документ |
|---|---|---|
| `CAP-UI-NEWS-DETAIL-001` | ACTIVE/CONDITIONAL, refresh/feed focused release id, repository selection | [News](../02-ui/news-and-logs-live-ui-contracts.md) |
| `CAP-UI-LOGS-DETAIL-001` | ACTIVE, bounded 64 KiB/500 lines file-tail и 2s active-only polling | [Logs](../02-ui/news-and-logs-live-ui-contracts.md) |

### Home update/UI: новая граница

| Capability | Статус / evidence | Документ |
|---|---|---|
| `CAP-UI-HOME-001—003` | ACTIVE/CONDITIONAL, launch/stop/restart, selective Python/Unity update, tester admission, partial component result | [Home launcher](../02-ui/home-launcher-update-and-game-state.md) |

### Wiki+Guide navigation evidence

| Capability | Статус | Evidence |
|---|---|---|
| `CAP-UI-WIKI-001—003` | ACTIVE local docs, CONDITIONAL external app/browser URLs | [Wiki](../02-ui/wiki-navigation-localization-and-anchors.md); bounded paths, localized files, history and generated anchors |
| `CAP-UI-GUIDE-001—006` | ACTIVE/CONDITIONAL, 13 registered steps, 3/5/13 levels, image step focus, Wiki callback; remaining GUI runtime tests PARTIAL | [Guide details](../02-ui/guide-walkthrough-and-image-focus.md) |

### Dialog callbacks / lifecycle

| Capability | Статус | Evidence |
|---|---|---|
| `CAP-UI-DIALOG-001—005` | ACTIVE/CONDITIONAL, background task hide/stop, pipeline apply, fine-tuning/DB export, styled alerts | [Dialogs source-to-behavior](../02-ui/dialog-interaction-and-background-task-contracts.md), `src/ui/dialogs/` callers |

### Текущий проход: уточнённая функциональная поверхность

| ID | Статус | Операция / наблюдаемое поведение | Source-backed документ |
|---|---|---|---|
| CAP-GRAPH-LEDGER-001—003 | CONDITIONAL | Graph processed-message skip, mark, clear: UI clear и per-character clear различаются | [Graph extraction ledger](../01-functional/graph-extraction-ledger-and-clear-consistency.md) |
| CAP-RESET-001—003 | ACTIVE/CONDITIONAL | Clear history epoch guard, sequential history/memory/graph changes | [History reset](../01-functional/character-reset-epoch-and-storage-consistency.md) |
| CAP-MEM-ID-001/002 | ACTIVE/CONDITIONAL | Memory ID/purge/embedding identity: воспроизведённый orphan и stale reassociation | [Memory ID purge](../01-functional/memory-purge-embedding-identity-regression.md) |
| CAP-CHAR-CUSTOM-001/002 | CONDITIONAL | Кастомные параметры и формулы с ограниченным evaluator | [Custom fields](../01-functional/character-custom-fields-and-formula-policy.md) |
| CAP-AI-BOUNDARY-001/002 | CONDITIONAL | Python RAG worker импортирует части прежнего Python Core; boundary not independent | [Import boundary](../04-dependencies/ai-worker-python-core-import-boundaries.md) |
| CAP-UI-TG-AUTH-001 | CONDITIONAL | Код/2FA модальные сценарии Telegram auth и ответ через future | [Telegram UI auth](../02-ui/telegram-auth-modal-contracts.md) |
| CAP-INSTALL-CATALOG-001/002 | ACTIVE/CONDITIONAL | Lazy loaded installable components, manifest, status and per-group errors | [Installable catalog](../01-functional/installable-catalog-lazy-registry-and-status.md) |

`ACTIVE/CONDITIONAL` означает, что основной код используется при соответствующем действии/установленном компоненте. Это не означает проверку Windows/Qt/Telegram/AI Engine в реальном окружении.

## Итерация с приоритетом *самого функционала*, а не ошибок прежней реализации

| Capability | Статус runtime | Что делает / граница | Evidence |
|---|---|---|---|
| `CAP-WORLD-001` | ACTIVE/CONDITIONAL (Unity world context) | Для конкретного персонажа определяет отношение к семи поставляемым мирам и формирует transient lore на текущий LLM turn | [Лор и context](../01-functional/character-world-and-environment-awareness.md); `src/domain/world_character_relations.py`, `src/domain/world_contexts/*.json`, `model_controller.py` |
| `CAP-ENV-001` | ACTIVE | Описывает персонажу доступность мира, voice pipeline (local/API/Telegram), приложение/игру и известный update status | [Environment awareness](../01-functional/character-world-and-environment-awareness.md); `services/character_environment_context.py`, `prompt_controller.py` |
| `CAP-ENV-002` | ACTIVE/CONDITIONAL | Передаёт модели переход достоверного происхождения Player message между приложением и игрой | [Player transport](../01-functional/character-world-and-environment-awareness.md); `prompt_controller.py:286-312` |
| `CAP-GM-001` | CONDITIONAL | Реальный Unity task → скрытая генерация GM → `dialogue.send_system_message` или другой structured intent → событие для следующего хода; GM не очередной NPC | [Scene direction](../01-functional/game-master-scene-direction.md); `create_task.py:542-588`, `chat_controller.py:784-928`, `prompt_controller.py:848-925,1218-1257` |
| `CAP-GM-002` | EXPERIMENTAL / UNRESOLVED registration | Новый structured `GameMasterResponse`, in-memory rules, lifetime/priority, scheduler, transcript; импорт из production composition не найден | [Неактивированная версия](../01-functional/game-master-scene-direction.md); `services/game_master_*`, `schemas/game_master_response.py` |
| `CAP-DIALOGUE-VIEW-001/002` | ACTIVE/CONDITIONAL | Typed Unity conversation + epistemically separate ephemeral UI snapshot, event updates, group title, disconnect reset | [Conversation projection](../03-runtime/conversation-session-projections.md); `services/contracts.py`, `services/dialogue_runtime_state.py`, `ui/chat/dialogue_presentation.py` |
| `CAP-DIALOGUE-VIEW-003` | EXPERIMENTAL / UNRESOLVED registration | Bounded in-memory group transcript из новой control plane, не доказанный production feature | [Conversation projection](../03-runtime/conversation-session-projections.md); `services/dialogue_transcript_service.py` |
| `CAP-WORLD-STATE-001—003` | ACTIVE/CONDITIONAL (Unity connected) | Character-scoped last-known world snapshot, runtime rules/static catalog, актуальная executable capability, turn-only events/TV и отдельная маркировка data-vs-control | [Unity world state projection](../03-runtime/unity-world-state-prompt-projections.md); `src/game_connections/handlers/actions/create_task.py:344-393`, `src/controllers/model_controller.py:306-329`, `src/controllers/prompt_controller.py:654-834,1026-1079` |

Этот список описывает **пользовательские и runtime-возможности**, а не места для правки багов. Потенциально незавершённые классы не автоматически включаются в обязательный Rust functional parity.

## Функциональный проход 2026-10-31: runtime-возможности (не аудит дефектов)

| ID / capability | Runtime status | Смысл / основное доказательство |
|---|---|---|
| `CAP-CHAR-EFFECTS-001—006` | ACTIVE/CONDITIONAL | [Structured character actions](../01-functional/structured-character-actions-and-side-effects.md) — структурированный ответ → изменения персонажа/памяти/таймера/мини-игры/Unity; различать requested vs observed effect |
| `CAP-INSTALL-CARDS-001—003` | ACTIVE/CONDITIONAL | [31 статических установочных карточки + динамические RAG](../01-functional/installable-catalog-and-runtime-readiness-matrix.md); catalog/installed/ready/runtime loaded различаются |
| `CAP-VOICE-REMOTE-001—003` | CONDITIONAL | [Привязка FishAudio к персонажам](../01-functional/remote-voice-presets-and-character-routing.md), credentials, preset, selection, preview |
| `CAP-UI-ASR-001—004` | ACTIVE/CONDITIONAL | [Галерея ASR](../02-ui/asr-model-gallery-and-settings-workflows.md), пять движков, install/readiness/settings |
| `CAP-UI-VOICE-LOCAL-001—004` | ACTIVE/CONDITIONAL | [Локальные голосовые модели](../02-ui/local-voice-model-management-and-compile-dialogs.md), выбор/конфигурация и compile dialogs |
| `CAP-UI-API-001—005` | ACTIVE/CONDITIONAL | [API preset editor](../02-ui/api-presets-and-model-parameter-editor-workflows.md), schema fields/validation/save, provider overrides |
| `CAP-UI-RAG-001—004` | ACTIVE/CONDITIONAL | [RAG pipeline/embedding provider workflows](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md), установка и загрузка — отдельные состояния |
| `CAP-UI-CONTEXT` | ACTIVE | [Контекст LLM](../02-ui/context-and-sqlite-data-inspection-workflows.md), request/response/usage, search/copy, fallback last sample |
| `CAP-UI-DATABASE` | ACTIVE | [SQLite viewer](../02-ui/context-and-sqlite-data-inspection-workflows.md), scoped/global, inspection and direct editing, ручное описание изображений |
| `CAP-DATA-FINETUNE` | CONDITIONAL | [Fine-tuning data](../01-functional/fine-tuning-data-capture-curation-and-export.md), capture, рейтинг, retention, export, debug ingress |
| `CAP-AI-HARDWARE` | CONDITIONAL/Windows | [GPU inventory](../01-functional/hardware-acceleration-and-ai-engine-administration.md): DXGI, CUDA Driver API, ordinal/LUID |
| `CAP-AI-ADMIN` | CONDITIONAL | [Engine administration](../01-functional/hardware-acceleration-and-ai-engine-administration.md): shared/split switch and environment maintenance lifecycle |
| `CAP-LING-RAG-01/02` | CONDITIONAL | [RAG linguistics](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md): keyword lemmatization, FTS form expansion/stem-prefix |
| `CAP-LING-SPEECH-01` | ACTIVE/CONDITIONAL | [TTS speech text prep](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md): language detection, numeric words, cleanup |
| `CAP-DEPS-DYNAMIC-001` | ACTIVE/CONDITIONAL | [Dynamic loader inventory](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md): lazy settings/pages/installable groups and optional core services |

`ACTIVE` здесь означает обнаруженный рабочий путь от зарегистрированного UI/сервиса, а не автоматическое подтверждение тестом. Статус конкретного installed voice/ASR provider обычно `CONDITIONAL`. Участие AI inference — только через отдельную Python AI subsystem, перенос моделей на Rust не требуется.

## Реестр персонажей и полная манифестная инвентаризация

| Capability ID | Статус | Что делает | Evidence |
|---|---|---|---|
| `CAP-CHAR-CATALOG-001` | ACTIVE | Перечисляет 9 доступных `char_id`, хранит display/storage/local voice identity и локализованную метку | [Catalog](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `CAP-CHAR-CATALOG-002` | ACTIVE | Загружает runtime выбранного персонажа on-demand, читает persisted values для ещё не созданного instance | [Lazy runtime](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `CAP-CHAR-CATALOG-003` | ACTIVE/CONDITIONAL | Применяет выбранный character, reset/reload и пакетные операции включая unloaded | [Lifecycle](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `CAP-CHAR-CATALOG-004` | ACTIVE/CONDITIONAL | Выделяет GameMaster и `secret_exposed`-capable персонажей, GUI-only не подменяет реальный runtime | [Special cases](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `CAP-DEPS-REQUIREMENTS-001` | RESEARCH | 84 requirements и прямые/nondirect imports, отдельные Core/GUI/AI/installer/standalone кандидаты; это inventory, **не** самостоятельная user capability | [Full dependency ledger](../04-dependencies/full-requirements-runtime-evidence-ledger.md) |


## Функциональное углубление: retrieval, установка, media и UI

| Capability | Статус | Назначение и source-backed документ |
|---|---|---|
| `CAP-RAG-INDEX-001—003` | CONDITIONAL | [RAG corpora/search + index modes](../01-functional/rag-storage-retrieval-and-indexing-modes.md): active/archive history, memory, FTS/vector/sentence, reindex |
| `CAP-INSTALL-PROBE-001—002`, `CAP-INSTALL-ACTIONS-001` | ACTIVE/CONDITIONAL | [Installer operation/status](../01-functional/installable-component-probe-and-operation-contracts.md): backend, media dependencies, voices, Beat, dynamic RAG |
| `CAP-AI-MODEL-001—003` | CONDITIONAL | [ASR/TTS installed/runtime](../01-functional/asr-tts-managed-backend-operational-contracts.md): per-model artifacts, selection, initialization, Python worker boundary |
| `CAP-UI-MODEL-001`, `CAP-UI-VOICE-001`, `CAP-UI-DEPS-001` | ACTIVE/CONDITIONAL | [API model/voice/modal actions](../02-ui/api-model-discovery-and-conditional-dialogs.md): test and catalog, hide vs cancel, FFmpeg info |
| `CAP-GAME-UI-001—002` | ACTIVE/CONDITIONAL | [Manual mini-games and Beat cache](../02-ui/game-settings-manual-launch-and-beat-cache.md): select Unity/Sandbox actor, gated buttons, reindex |
| `CAP-SCREEN-UI-001`, `CAP-CAMERA-UI-001`, `CAP-IMAGE-DESCR-001`, `CAP-IMAGE-MAINT-001`, `CAP-MITA-CAM-001` | CONDITIONAL | [Screen, cameras, storage](../02-ui/screen-camera-image-management-user-contracts.md): capture modes, description and image retention, Unity camera event |

**Не считать ACTIVE без live producer:** отдельные `ProtocolPipelineDialog`/`NewPresetDialog` присутствуют как определения, но direct runtime caller не доказан в этом snapshot. Исключены из обязательного parity до подтверждения.

## Дополнение: интеграции, требующие разделения production и standalone

| Capability ID | Статус | Evidence |
|---|---|---|
| `CAP-EXT-ROUTE-001—004` | CONDITIONAL / STANDALONE / UNRESOLVED | [External entrypoints](../01-functional/external-integration-entrypoints-and-reachability.md): Telegram user-client и external tools vs remote providers vs отдельные VTT/HoI4 prototypes |


## Дополнение: RAG ранжирование и итоговая выдача

| Capability | Статус | Evidence |
|---|---|---|
| `CAP-RAG-RANK-001—003` | CONDITIONAL | [Query context/fusion/CE graph quota](../01-functional/rag-query-fusion-reranking-and-result-contracts.md), в том числе explicit tool search и async access tracking |


## Дополнение: RAG → Prompt boundaries

| Capability | Статус | Evidence |
|---|---|---|
| `CAP-RAG-PROMPT-001—003` | CONDITIONAL | [RAG eligibility, formatting, system message order](../01-functional/rag-context-injection-and-source-rendering.md) |

| CAP-LOCAL-IPC-001—003 локальный control-plane | CONDITIONAL | `main_controller.py:121-127,218,684-686`, `core/runtime_ipc.py`, `services/runtime_ipc_service.py` | Settings-driven JSON TCP, six confirmed methods, AI worker admin; [audit](../01-functional/local-runtime-ipc-external-control-contract.md) |

| CAP-UI-ONBOARD-001—003 первый GUI запуск | CONDITIONAL | `ui/windows/app_window_base.py:1660-1709`, `ui/widgets/eula_widget.py:166-248`, `localization/eula_texts.py` | Persistent consent, localized EULA, optional language restart, guide/Wiki; [audit](../02-ui/first-run-agreement-language-and-guide-flow.md) |

| CAP-DEPS-NATIVE-001—004 нативные функциональные границы | ACTIVE/CONDITIONAL | `services/hardware_inventory_service.py`, `infrastructure/audio/windows_endpoint_identity.py`, `services/unity_process_guard.py`, `handlers/llm_providers/chatgpt_plan_auth.py` | OS SDK, driver, device, external process and AI-runtime distinction; [audit](../04-dependencies/native-system-api-and-ai-library-ownership.md) |


## Дополнительные подтверждённые capability slices

| ID | Статус | Пользовательская функция и источник |
|---|---|---|
| `CAP-INSTALL-ID-001—003` | ACTIVE/CONDITIONAL | [Статический/динамический каталог](../01-functional/installable-catalog-identity-and-coverage.md): 31 + RAG, types, metadata и readiness |
| `CAP-INSTALL-OBS-001—003` | ACTIVE/CONDITIONAL | [Late component status](../03-runtime/installable-status-observation-and-invalidation.md): transient/ready, cache generations, UI delivery |
| `CAP-INSTALL-QUEUE-001—003` | ACTIVE/CONDITIONAL | [Install command lifecycle](../03-runtime/install-operation-admission-queue-and-completion.md): preview, admission, FIFO, cancel, E2E readiness |
| `CAP-UI-STATUS-001—002` | ACTIVE/CONDITIONAL | [Chat status presentation](../02-ui/generation-progress-error-and-voice-indicators.md): model/tool/compression/error/voice и chips |


## Dialogue identities: actor versus character versus message

| Capability | Статус | Source-backed документ |
|---|---|---|
| CAP-DIALOGUE-IDENTITY-001—004 | ACTIVE/CONDITIONAL | [Стабильная личность, игровой актор, отправитель, reply и turn IDs](../01-functional/dialogue-actor-and-message-identity-contracts.md) — `DialogueIdentityResolver`, `ConversationEventWriter`, `ConversationMessageIds` |
| CAP-DIALOGUE-IDENTITY-005 | EXPERIMENTAL/UNRESOLVED | [Краткая стенограмма GM](../01-functional/dialogue-actor-and-message-identity-contracts.md) — не подтверждена как production-composed |
| `CAP-STREAM-001—003` | ACTIVE/CONDITIONAL | [Stream events → UI coalescer](../03-runtime/llm-stream-event-and-presentation-lifecycle.md): typed terminal, think/text separate, 25 мс batching |


## Pass 11 — новые уточнённые функции и runtime contracts

| CAP family | Статус | Подтверждённый маршрут |
|---|---|---|
| `CAP-DSL-EXEC-001…` | ACTIVE/CONDITIONAL | [prompt building, author DSL, controlled side effects](../01-functional/dsl-executable-prompt-contract.md); `src/controllers/prompt_controller.py:400-485; src/DSL/dsl_engine.py:422-1004` |
| `CAP-POSTDSL-001…` | ACTIVE/CONDITIONAL | [post-generation transformation and custom state](../01-functional/post-dsl-response-rules-and-debug-state.md); `src/characters/character.py:409-631; src/DSL/post_dsl_engine.py:43-376` |
| `CAP-MINIGAME-DETAIL-001…` | CONDITIONAL | [two rulesets and game-bound character reactions](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md); `src/managers/game_manager.py:11-173; src/modules/Chess/game_instance.py:143-239; src/modules/SeaBattle/seabattle_instance.py` |
| `CAP-ACTION-HISTORY-001…` | CONDITIONAL | [retained requested action context across summary](../01-functional/structured-action-history-and-compression-bridge.md); `src/managers/action_memory.py:10-178; src/controllers/history_controller.py:248-302,1325-1355,1822-1830` |
| `CAP-CORE-TRIGGER-001…` | CONDITIONAL | [deterministic story state distinct from access control](../01-functional/exact-core-memory-triggers-and-session-activation.md); `src/managers/core_memory_triggers.py:24-136; src/controllers/model_controller.py:1380-1407` |
| `CAP-MIC-001…` | CONDITIONAL | [physical microphone selection, monitoring and hotplug](../01-functional/microphone-physical-identity-backends-and-monitoring.md); `src/services/microphone_selection.py; src/services/microphone_monitor.py; src/infrastructure/audio/portaudio_catalog.py` |
| `CAP-SPEECH-ARBITER-001…` | ACTIVE/CONDITIONAL | [microphone gating against local+Unity playback](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md); `src/controllers/speech_controller.py; src/managers/speaking_window.py; src/game_connections/handlers/actions/speech_state.py` |
| `CAP-EVENT-ROUTE-001…` | ACTIVE/CONDITIONAL | [event fact/command/progress distinction](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md); `src/core/events.py` |
| `CAP-UNITY-INGRESS-001…` | ACTIVE/CONDITIONAL | [seven inbound Unity request families and ownership](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md); `src/game_connections/server.py; src/controllers/server_controller.py` |
| `CAP-GUI-ASYNC-001…` | ACTIVE/CONDITIONAL | [freshness, exclusive side effects, refresh coalescing](../02-ui/intent-workloads-and-visible-state-consistency.md); `src/controllers/gui/intent_view_model.py:18-387; src/controllers/gui/gallery_page_view_model.py:43-128` |
| `CAP-HEADLESS-SURFACE-001—005` | CONDITIONAL | [Работа Core без GUI: standalone process readiness, Telegram auth и остановка](../03-runtime/headless-core-functional-surface-and-readiness.md) |
| `CAP-INSTALL-FIXTURE` evidence | CONDITIONAL/source-only | [31 статических ID + RAG dynamic fixtures](../06-design-input/installables-component-by-component-parity-matrix.md) — физические install tests не запускались |

**Граница reachability:** [кандидаты standalone/UNRESOLVED](standalone-and-unproven-runtime-reachability.md) отделены от подтверждённых функций; static [GUI callsites](gui-async-operation-callsite-index.md) не доказывают все зарегистрированные действия.

## Pass 12: подтверждённые функциональные срезы, без пересчёта primary 13/20

| Capability | Статус | Обнаруженное поведение и источник |
|---|---|---|
| `CAP-UI-DIALOG-001—003` | ACTIVE/COND, часть UNRESOLVED | 20 потенциальных именованных QDialog-классов, 17 прямых конструкторных callsites; 6 + 1 зарегистрированных window IDs; [достижимость](../02-ui/dialog-class-reachability-and-action-outcomes.md) |
| `CAP-EVENT-RAW-001—002` | ACTIVE/COND | Восемь raw-string событий имеют прямые emit/subscribe paths, в том числе history paging, periodic image request и GUI loading bridge; [реестр](raw-string-event-reachability-and-ui-bridges.md) |
| `CAP-GRAPH-INGEST-001—003` | CONDITIONAL | Inline structured/legacy, realtime utility, manual batch c source-tagging и RAG visibility; [контракт](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md) |
| `CAP-UI-NATIVE-001—003` | ACTIVE/COND | Системный выбор файла/папки, сохранение JSONL/JSON/logs, tester code и выбор character target; [сценарии](../02-ui/native-dialogs-and-file-input-output-workflows.md) |
| `CAP-UI-CONFIRM-001—003` | ACTIVE/COND | Yes/No перед destructive/storage, Save/Discard/Cancel для dirty preset, выбор загрузки отсутствующих RAG моделей; [матрица](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md) |
| `CAP-RAG-PRESET-001—003` | ACTIVE/COND | Четыре встроенных RAG pipeline presets, user snapshots, отдельный Apply и model-readiness/installer; [сценарии](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md) |
| `CAP-SET-RAG-CONSUMER-001` | ACTIVE/COND/UNRESOLVED per key | 100 registered descriptors, 99 unique keys, source-literal consumer index; [source index](rag-settings-direct-consumer-evidence-index.md) |
| `CAP-UI-SIGNAL-001—002` | STATIC reachability, not E2E | 517 зарегистрированных `.connect()` calls в 75 GUI source-файлах, определены группы сигналов и конкретные функции; [индекс](gui-signal-registration-callsite-index.md) |
| `CAP-DEPS-PROCESS-001—003` | CONDITIONAL | FFmpeg/7z, subprocess/download/optional Python AI, Windows native loader; [контур](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md) |

- `CAP-RAG-READY-001..004` — отдельный статус нужных embedding/reranker моделей, фоновый прогрев, событие рестарта worker и согласование результатов с поколением процесса: [контракт](../01-functional/rag-model-runtime-readiness-and-worker-generation.md); ACTIVE/CONDITIONAL.
- `CAP-RAG-GOLDEN-001..002` — воспроизводимый result contract vector/keyword RAG с fake embedding fixtures: [контракт](../01-functional/rag-deterministic-golden-surface-and-result-types.md); ACTIVE offline-confirmed, not ML quality E2E.

- `CAP-HISTORY-VIEW-001..003` — storage role/actor identity → GUI message role, TV observation, per-character paging: [контракт](../01-functional/history-ui-projection-actor-identity-and-paging.md); ACTIVE.

- `CAP-DYNIMPORT-001..009` — обязательное различие registry identity / conditional module available / instantiated capability для LLM, ASR, tools, installables, GUI, Python AI worker: [контракт](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md).
