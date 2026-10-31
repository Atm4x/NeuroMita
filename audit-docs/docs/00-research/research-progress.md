# Прогресс исследования

**Актуальная точка: 2026-10-31, [Pass 13 — сводный каталог и остатки](current-functional-baseline.md).** Полный аудит не объявлен завершённым. Ниже сохранена история исследования; прежние «актуальные» checkpoints, used/remaining, 30-minute timers и планы относятся к своим проходам. Пользовательский ориентир остановки — около 6% remaining пятичасового лимита. Субагенты не используются. Полнота всего аудита не измерена процентом.

## Pass 13 — импорт и продолжение в текущем Windows checkout

Импортированы 181/181 Markdown из присланного ZIP с предварительной копией старых docs. Подтверждены releases HEAD и origin/releases, SHA-256 совпадение 1024 .py и дополнительно 160 non-Python файлов CodeNow.zip. Код, Legacy и Unity не редактировались.

Добавлены RAG mixed-model/provenance, settings consumer semantics, конечный history receiver/fencing, standalone prompt/node authoring, world-db exchange validation; уточнены modal callbacks и component-specific install/initialize/uninstall. Исследованы local wheel parent/native edges и реальные Rust alternatives по первичным источникам. Подготовлен единый каталог 20 функциональных областей с явными остатками; GUI comparison и новая архитектура не проектировались.

**Новые исполнения этой сессии:** пять изолированных функциональных fixture (RAG SQL, node parser/codegen, World DB, history coordinator, legacy inspection/replay), все assertions PASS; read-only METADATA/RECORD и direct/delay PE imports шести существующих binaries. Дополнительно source AST 717 src / 14 scripts / 39 editor modules без parse errors уточнил встроенные языки и import boundaries. Не запускались полный pytest suite, bootstrap, inference, GUI, Unity, внешние credentials/providers или install/remove. Ранее полученные тестовые counts не пересчитываются как новые результаты. Полные условия опытов и один исправленный fixture cleanup failure описаны в тематических документах.

**Следующий остаток:** S-SET / S-UI / S-DATA / S-REACH / V-ENV / T-TRACE в [текущем baseline](current-functional-baseline.md). Счёт PRIMARY 13/20 сохраняет прежние критерии; расширение source evidence не подменяет machine E2E.

**Финализация текущего пакета Pass 13:** 191 Markdown, 10 новых/22 обновлённых относительно ZIP, все 181 исходных пути сохранены. Дополнительно дочитаны reminder inputs, snapshot identity/live state, динамическое меню SQL и AI Hub schema→component save; reverse-parent sweep всех 84 root distributions и source classification implicit langdetect/psutil/NumPy/packaging. Пять изолированных fixture остаются отдельными выполненными проверками; новых полных suite/hardware/network runs нет. Старые source «ещё не исследовано» пометки снабжены актуальными follow-up links; итоговая архитектура не проектировалась.

**Контроль перед остановкой:** 1664 relative MD links проверены, 0 broken; 105 global requirement IDs, 0 duplicates; SHA-256 повторно 1024 .py + 160 non-Python совпали, 0 отличий. Tracked/staged diff и submodule diff отсутствуют. Quota при валидации — 92% used/8% remaining; сохранён checkpoint перед ориентиром пользователя около 6% remaining. Полный аудит не завершён и не сокращён для получения фиктивного завершения; [очередь продолжения](current-functional-baseline.md) содержит source-depth и отдельные runtime validation gates.

## История предыдущих проходов

## Подтверждённая точка

Зафиксированы Python/Unity/submodule revisions и dirty status. В Unity выполнен только fetch origin. Python sources и Unity sources не менялись. Создана только документация в audit-docs/docs.

Прочитан переданный research brief, включая функциональные области, шаблон capabilities, dependency/GUI/architecture research, структуру deliverables и критерии полноты.

Разобран начальный lifecycle: shipped run.py main/ensure_core_ready, local launch.py, src entrypoint, runtime bootstrap, GUI composition/loader, headless host, MainController composition/shutdown, RuntimeFeatureManager. Найдены 12 optional registrations. Созданы CAP-RUN-001—005 и REQ-RUN-001—012.

## Просмотренные источники

Полностью: src/__main__.py, src/__init__.py, launch.py, startup/gui_backend_loader.py, startup/headless_runtime.py, controllers/gui/composition_root.py, core/app_paths.py, services/runtime_features.py (несколькими диапазонами), tests test_headless_runtime/test_shutdown_paths/test_runtime_features.

По ключевым диапазонам: startup/runtime_bootstrap.py, controllers/main_controller.py (constructor, optional registrations, server/attach/shutdown), scripts/run.py (symbol inventory и final orchestration), ui/windows/app_window_base.py (deferred close), controllers/server_controller.py (начало). Прочие файлы, найденные rg, не считать исследованными. Из test_runtime_failure_policy пока прочитаны только имена тестов.

Дополнительно разобран основной dialogue orchestration: ChatController 209—1240 (кроме части normalize/helpers), 1240—конец (retry/delete/regenerate/snapshot); ModelController generate_chat, _generate_chat_serialized, _process_structured_output, _handle_tool_call и _publish_history_commit; ChatModel 158—461; RequestPolicy/CancellationToken/character locks; LLMRequestRunner практически целиком; ProviderManager и protocol adapter registry; streaming.py 1—200; ApiPresetResolver resolve_chain/key rotation (resolve прочитан частично); api_protocols.py predefined catalog.

PromptController.build и _build_system_messages прочитаны, ряд helpers лишь найден. HistoryManager прочитан по constructor, load/save/export/add batch/serialization/delete methods; ConversationEventWriter по recipient resolution, fanout, builders и write_turn. UnityRetryStore по storage/validation/recovery/claim/transitions/delivery methods. DatabaseManager пока только начало до ensure_columns и symbol inventory. AppShellController send/capture/status и message actions view model прочитаны, но не все методы shell и не все UI widgets.

Новые документы: llm-and-generation, prompt-system, history, llm-requests, unity-retry-outbox. Реестр CAP расширен. Важные выводы: per-character generation serialization; mutation/commit/delivery/voice не атомарны; история атомарна per recipient, но не multi-recipient; retries LLM прекращаются после stream body; retry delivery отличается от regeneration; snapshot variables импортируются merge, SQL errors могут теряться на caller boundary.

Далее исследованы: HistoryController основные prepare/compression/layered/epoch/sanitization/maintenance методы; DatabaseManager schema init/upgrade/FTS; CharacterController, CharacterManager, CharacterRegistry, CharacterResourceManager, CharacterScopedService; Character constructor/reload/reset/variables/stats/plain/structured effects (часть plain memory tags требует дочитывания); WorkingStateManager. MemoryManager основные CRUD/islands/seeds/forget/TTL/render/maintenance/purge; ReminderManager и ReminderController; GameManager начало пока без отдельных игр.

RAGManager search, query embeddings, index update/missing reindex начало; RagEmbedder основной proxy/batching; pipeline types/query builder/config/combiner/enrichers/linear reranker; vector/keyword/FTS retrievers по основным ветвям, repositories начала; FAISS cache целиком; rag_utils начало morphology; CrossEncoder proxy начало; rag_client. GraphController realtime/inline/tagging, GraphStore schema/upserts/query/TTL/clear, entity_extractor parser/store, GraphRetriever. Entity GC/retyping и GUI actions лишь найдены, ещё не разобраны.

Новые документы: history-compression, persistence, characters, memory, reminders-and-timers, rag, knowledge-graph, current-problems. Точечный experiment: sqlite3 :memory: подтвердил GLOB predicate mismatch для старых дат; пользовательская DB не открывалась. Остальные тесты не запускались. Исходники не менялись.

Новые значимые gaps: shared memory id vs row id в purge, cross-character TTL UPDATE, поздний graph store без epoch, timer dismiss на bus acceptance, scope/identity и partial outcomes. Нельзя преждевременно утверждать завершённость memory/RAG/GUI аудита.

Известные источники: [source-evidence-index](source-evidence-index.md), подробные source tables внутри новых документов.

AI boundary: AIEngineController _Worker transport/admission/result/deadline/heartbeat/stop, controller deferred calls/switch/activation/recovery/maintenance, worker_process bootstrap/loop/lazy services, GPU scheduler, RuntimeEnvironmentManager types/transaction/composition/promotion изучены. Не все helpers/installer recovery paths закрыты. Созданы ai-ipc и ai-environments. Важно: Queue передаёт Python objects, worker всё ещё импортирует ряд core/audio/game modules; новый самостоятельный Python worker требует явного независимого contract.

Audio: AudioController и AudioHandler полностью; LocalVoiceController activation/public API/restart/synthesize; SpeechController constructor/reconcile/start/stop/shutdown/gate/routing; ASRInputGate целиком, AudioCaptureService/segmenter/helpers целиком; ASRService целиком; asr_handler event bridge и managed start/switch/stop. MicrophoneSelectionService, Windows endpoint identity, PortAudio catalog, legacy selection migration, monitor service/GUI controller полностью. RemoteVoiceService/repository/provider/types полностью. TelegramController/Handler/auth service/credential gate/converter полностью, auth viewmodel и text normalization. Созданы voice-output, speech-input, telegram-voice. Нет реального аудио/моделей/Telegram login/API requests. Найдены ISSUE-007—009; Unity end-to-end audio/ASR пока не проверен.

Installer: InstallableController orchestration, InstallController основной pipeline, InstallGuiController queue/admission/cancel/quiesce/run/enqueue, catalog service metadata/status/probes/settings/plans/preparation, lazy registry/types/compatibility прочитаны. Manifest metadata начало, все id/loader inventory и dynamic RAG tail; не все model-specific планы/settings. PipInstaller entrypoints/uv bootstrap/lock resolver/process runners/PTY/pipes/cancel/deadlines/transient retry прочитаны; progress aggregator/manual uninstall/metadata repair ещё не полностью. AI Hub ViewModel основной файл и settings viewmodel прочитаны, dialog navigation/filter/close/preview/card actions; layout/schema renderer ещё не полностью. Maintenance reset service и environments reset/migration/recovery/remove прочитаны. Созданы installations и 02-ui/ai-hub.

Unity: Python server.py и action registry/create_task/get_settings/get_task_status/hello/asr_ptt_state/speech_state полностью; ServerController lifecycle/settings/delivery/ASR/echo основные paths. Socket send success=drain, application ACK нет; это проверено до Unity consumer. NetworkController transport/context/send/audio loading entry/cleanup, GameConnectionSession/router/TaskOrchestrator/runtime/bootstrap, ASR classes, SpeechStateReporter прочитаны. Workflow tracker/dispatcher/coordinator/admission; ResultProcessor final/version/default/react/presentation (address map construction tail не весь). Auto-dialogue order/roster/continuation/planner/routing/GM/idle/participation и runtime context buffer полностью, PlayerEngagementRuntime. ServerSettings.ApplyFromDictionary/MitaCore.ApplyServerSettings изучены. Python shared_image_transfer полностью, Unity shared transfer основной config/write/reference и settings handler до stats extraction. TaskManager/TaskController Python полностью.

Созданы unity-transport, unity-media-transfer, unity-dialogue-admission, unity-auto-dialogue. Network/Dialogue Application/context buffer одинаковы local HEAD и fetched origin/codex/card-game-portability-audit1e02a70c2; рабочие network/dialogue scripts не изменены. Origin/HEAD=старый main июня, не использовать как выбранный актуальный baseline. Полная целевая Unity revision по-прежнему не установлена.

На checkpoint: 36 содержательных Markdown files, общий размер325242 bytes перед финальной правкой checkpoint; повторная проверка внутренних md links дала0 missing targets. Реестр9 defects/12 risks/2 tradeoffs — накопительные выводы, не оценка всех исходников и не свидетельство ущерба данным пользователя. Только GLOB predicate проверен isolated sqlite3 :memory:, остальные выводы static. Никаких builds/app/Unity/audio/model/network-provider тестов не было. Python git status показывает только прежний src.zip и новый audit-docs; tracked sources без изменений. HEAD повторно сверён с origin/releases:38172493. Unity audited Network/Dialogue scripts также без working-tree diff.

## Продолжение и уточнение приоритета пользователем

Пользователь уточнил: сначала функционал Python; подробный Unity client audit не является блокером переписывания core. Дальнейший проход следует этому приоритету. Уже собранные Unity факты сохраняются, оставшиеся клиентские implementation details отложены; обращаться к ним только для объяснения Python contract.

После возобновления прочитаны structured_response_parser, full/sparse/GameMaster schemas, runtime/structured capabilities и provider schema adapter. Создан structured-response-contract. Изолированный parser experiment без app/bootstrap/DB/network подтвердил немаркированные coercions, invalid intent payload → {}, top-level commands compatibility и сохранение intent после truncation repair. Локальный pydantic2.10.3 отличается от pin2.10.6; это не release integration test. Добавлен RISK-013. GameMasterResponse пока не имеет найденного production orchestration callsite; отдельные class definitions/tests не доказывают active feature.

До уточнения приоритета прочитаны Unity decoder/executor и actor dispatcher/command definitions; inventory implementation лишь частично. Не считать это завершённым аудитом всех игровых действий и не продолжать их по инерции.

В Python закрыт основной функциональный проход изображений: CaptureController, ScreenCapture, CameraCapture, ImageDescriptionHandler, send/staging paths, runtime camera options, storage/read/description restore, drawing artifacts, manual orphan cleanup, history image quality projection и OpenCV managed component. Создан images-and-capture. Автоматическая TTL cleanup по GUI keys не подтверждена; screenshot button bytes conversion дефект виден статически; реальная камера/экран/удаление/API не запускались. Tools manager и четыре builtin tools прочитаны по основному содержимому, но регистрации/context/continuation и оставшиеся tools требуют завершения отдельной ветви. При проверке лимита в этом продолжении использовано16%, оставалось84%.

## Checkpoint после расширенного Python functional pass

Работа продолжалась последовательно, без субагентов и без изменений source. На последней проверке primary used90%, remaining10%; ниже завершаются документация и проверка ссылок, ориентир остановки около6% remaining. Полный аудит не завершён, процент полноты не пересчитывался.

После отметки37% исследованы и описаны:

- navigation/gallery/news/wiki/guide/logs, settings registry и окна: navigation-gallery-and-help;
- Home/game process management, release check/download/cache, archive dispatch, Python overlay/activation/resume и Unity install transaction: launcher-and-updates; native Launcher.exe source/полный handshake не найден и не проверен;
- sandbox/debug/context snapshots, ingress collector, fine-tune collection/rating/filter/export и ContextViewer actions: diagnostics-and-data-export;
- local JSON control IPC, registration/allowlist/lifecycle: local-control-ipc;
- catalogs/live i18n/user translations/preferences: localization-and-preferences;
- API presets/models/protocol settings/key rotation/fallback/check и browser OAuth/accounts/token storage/refresh: provider-configuration и account-authentication; внешние API/login не запускались;
- settings registry/subscriptions/async save/load/shutdown: settings-and-preferences-store;
- DB viewer/filter/search/direct editing/images, JSON exchange, full/missing reindex, manual graph extraction/GC/delete/type backfill/view interactions и memory cosine dedup: data-maintenance;
- character settings scopes/provider/packs/folders/reload: дополнение characters; recovery ZIP/JSON/preview/replay/ledger/archive, local files→SQLite, structured migrations и history identity dedup: compatibility-imports;
- voice model catalog/settings/device schema/admission/compile entrypoints, init/hide/cancel/late completion, remote presets/character overrides/preview и Telegram code/2FA dialogs: voice-controls;
- TaskWorker/GuiTaskSupervisor, TaskSupervisor threads/futures/replacement/watchdog, pools/budgets, EventBus delivery/ordering/SerialDispatcher: background-tasks-and-events.

Дополнены capability inventory, requirements, evidence index и RISK-018—023. Важные новые ограничения: maintenance не единая mutation API; full reindex не сбрасывает FAISS cache; failed graph attempt помечается processed; clear graph оставляет processed ledger; cosine dedup не ограничивает model_id; backup копирует основной DB файл без доказанного согласования WAL; voice UI теряет часть failure/admission outcomes; SerialDispatcher имеет потенциальную accounting race. Это findings для новой спецификации, не указание переносить дефекты.

Не считать прочитанными целиком большие файлы из-за просмотра основных ranges. Конкретные renderer/helper/component-tail gaps сохранены в тематических документах. Никаких real DB/import/delete, installer/update, provider/login, audio/model/game или Unity действий не запускалось. Выполнялись только ранее указанные isolated experiments; текущий проход — static source audit и docs.

Python остаётся releases38172493fa0d1caf1a5225bc1c559f095f18bb7a, равен origin/releases при последней локальной проверке. Git tracked diff пуст, baseline src.zip не тронут. Подробные Unity client internals по решению пользователя отложены.

Проверка документов:55 Markdown files,0 missing relative Markdown targets,0 duplicate requirement IDs после исправления navigation→REQ-NAV-001. В git нет tracked/staged source changes, untracked audit-docs и исходный src.zip; git diff и cached diff exit0. Предупреждение доступа к .pytest_cache существовало ранее; папка не трогалась. Финальная проверка quota: used93%, remaining7%; этот заход остановлен рядом с заданным ориентиром6%, с запасом на итог и checkpoint. Это лимит сессии, не процент завершённости аудита.

Точные точки следующего чтения: src/handlers/llm_providers/gemini_provider.py и message_transforms.py; затем src/handlers/ai_engine/runtime_failure_policy.py и component-specific install plans. Эти файлы сейчас только найдены для продолжения, не считать закрытыми.


## Checkpoint: 2026-10-30, дополнительный последовательный проход (пользователь запросил ZIP)

Исходник: `CodeNow.zip`, внутри предыдущая папка `audit-docs/docs` (55 MD) и Python sources. Выбранный предыдущим агентом `releases` SHA `38172493fa0d1caf1a5225bc1c559f095f18bb7a` сохранён как **заявленный baseline**, но ZIP не содержит самостоятельного git history для повторной проверки SHA. Python/Unity исходники не менялись.

В этом проходе прочитаны `gemini_provider.py` основной request+stream/usage path, `message_transforms.py` целиком по функции и registry, `chatgpt_plan_provider.py` целиком, `chatgpt_plan_protocol.py`, `chatgpt_plan_auth.py` по validate/account/status/revoke path, `http_transport.py` основной client/timeout flow; `runtime_failure_policy.py`, worker_process dispatch/restart и unit test; component install plan ranges для F5/Fish/Omni/EdgeTTSRVC/FFmpeg/OpenCV. Это **не** означает, что полностью исследованы все helper tails/ASR/Beat/RAG component plans или провайдерские удалённые сервисы.

Добавлены четыре содержательных документа: `03-runtime/provider-wire-contracts.md`, `01-functional/message-transforms.md`, `03-runtime/cuda-fatal-worker-recovery.md`, `01-functional/installer-component-plans.md`. Уточнены README, inventory, requirements и этот progress checkpoint. Никаких Python/Unity/model builds, тестов, login/API requests, загрузок, инсталляций, удалений не выполнялось.

Новые findings: Gemini не только переносит system instructions для Gemma, но и переименовывает trailing non-user роль в user; transform `system_to_user_prefix` может мутировать вложенный content через shallow copy, `trace.changed` сравнивает лишь сводки; ChatGPT Plan запрещает redirect и nontrusted endpoint, требует wire-stream; CUDA poison приводит к немедленному `os._exit(70)` без queue response; разные TTS variants имеют разные RVC/Triton/compiler/patch обязательства. Всё это факты статического кода/обоснованные риски, не динамически воспроизведённые дефекты.

Дальше: ASR/Beat/RAG component-specific планы и uninstall/repair; HTTP Responses adapter detailed stream/error tests, full request cancellation; prompt editor actions/effects; remaining config/packaging; проверка import reachability и dependency matrix. Unity detailed implementation отложен по пользовательскому решению; GUI framework comparison и окончательный Rust architecture design исключены из текущего аудита. Полный процент покрытия **не пересчитывался**, потому что denominator capabilities ещё не зафиксирован; прежняя пользовательская оценка 65–70% не верифицирована.

## Актуальный следующий последовательный проход

1. Завершить provider HTTP/SSE/adapters/transforms, прежде всего Gemini и все protocol-specific serialization/cancellation/error paths. Не повторять уже описанные presets/auth GUI.
2. Installer component-specific plans/settings/download/compile/licenses, progress parsers/repair/manual removal; закрыть фактический состав устанавливаемых AI environments. Inference остаётся Python, исследуем host obligations и contract.
3. Оставшиеся functional gaps персонажей/effects/local voice profiles и GUI actions; layout/painter читать только когда он несёт неописанную функцию. prompt_editor имеет отдельный entrypoint, его полная node graph реализация пока не закрыта.
4. Runtime failure policy/services/executor daemon tails, settings/config/secrets/paths/build/packaging и native launcher/update helper gaps. Основные jobs/events уже описаны, оставшиеся consumers и late-result policies нужны отдельно.
5. Свести обнаруженные requirements и capability scenarios, явно решить ACTIVE/CONDITIONAL/LEGACY/EXPERIMENTAL/UNRESOLVED и полноту discovery. Unity обращаться только для Python boundary; detailed client implementation не блокирует.
6. Затем доказательная dependency classification/import reachability, минимум две реальные альтернативы ключевых core возможностей с первичными источниками, лицензиями/native dependencies/health; Rust GUI comparison и новая Python vs новая Rust architecture. Rust stack ещё не выбран. Ответ «в requirements нет незаменимого core» пока нельзя выдавать как доказанный итог.

Архивная последовательность ниже описывает прежнюю точку и не является заданием повторного просмотра уже закрытых основных paths.

## Предыдущий план при used37% (история)

Текущая точка после изменения приоритета: созданы images-and-capture, tools-and-web, music-beats, prompt-language-and-packs, desktop-mini-games, standalone-web-surface. Описаны все6 builtin tools и native/schema continuation, Python BeatService/cache/batch/worker и settings, runtime DSL/PostDSL/packs/download, обе зарегистрированные desktop игры и отдельный web/VTT/mock entry. Основные сценарии пройдены до implementation; конкретные непроверенные helper ranges/GUI/installer tails указаны в каждом документе. В source checkout shipped prompts лежат extra/Prompts, root Prompts отсутствует; build default copy mapping проверен. prompt_editor запускается отдельно через PySide6 и использует собственные engines, production core launch reference не найден. Никаких app/network/audio/model/game тестов не запускалось. При последней проверке primary used37%, remaining63%; cutoff6% remaining сохраняется.

Сейчас начат GUI functional navigation: main_page_registry содержит home/news/gallery/sandbox/settings/wiki/logs; settings section registry и WindowCompositionController прочитаны по основной регистрации. Далее последовательно пройти действия страниц и непокрытые settings, не возвращаться к Unity animation/client implementation. Tools/DSL/beat/games основные ветви уже не требуют повторного discovery; оставшиеся gaps — в их документах.

1. Python tools: все builtin operations, activation/settings/character scope, structured/native/plain call paths, continuation и результаты. Затем DSL/templates/assets и prompt editor reachability.
2. Python beat feature: action/service/worker/client/cache и настройки; inference implementation классифицировать отдельно. Unity BeatSync/presentation и game image producers отложены.
3. Закрыть dialogue gaps: providers/auth/HTTP/SSE, оставшиеся effect implementations и GUI reachability. History/RAG/graph maintenance/reindex, exports/migrations и identity semantics имеют отмеченные пробелы.
4. Изображения: media editing GUI/renderer и оставшиеся prompt paths в составе GUI/истории; virtual camera client internals не блокируют core.
5. Закрыть installer/audio tails: component plans/settings/downloads/licenses/compile, progress parser/repair/manual removal, auth dialogs, voice model profiles/UI. Inference остаётся Python.
6. Полная GUI navigation/screens/settings/localization/window lifecycle, prompt_editor; modules/games/chess/web/integrations — доказать reachability, не исключать по имени.
7. Updates/recovery/Launcher/build/packaging, config/secrets/path inventory, failure policy/events/services/executors/supervisors и оставшиеся persistence операции.
8. После полного discovery — dependency research первичными источниками, core vs inference/transitive/unused classification, Rust GUI candidates (Slint preference не решение), licenses/native dependencies/health, новая Python vs новая Rust architecture и итоговые deliverables. Сейчас **не обоснован** вывод о незаменимости/отсутствии Rust-аналогов всех core dependencies.

Порядок допускает возврат к найденной зависимости, но не поверхностный параллельный просмотр всего проекта. Неразобранные ветви остаются в inventory.

## Checkpoint: 2026-10-30 — bounded Python functional audit (лимит 30 минут wall-clock)

**Исходные материалы:** `CodeNow.zip` с Python source snapshot и 55 более ранними MD; предшествующий ZIP `NeuroMita_audit_docs_continuation_2026-10-30.zip` с 59 MD. Итог данного продолжения: **70 Markdown-документов в `audit-docs/docs/`**; одиннадцать новых документов, дополнения существующих README/requirements/inventory/source-index/risks/open-questions и этот checkpoint. Архив ZIP не содержит `.git`; прежний заявленный `releases` SHA `38172493fa0d1caf1a5225bc1c559f095f18bb7a` **не верифицирован** по git objects в текущей поставке. Unity исходники здесь не исследовались, согласно текущему пользовательскому scope.

### Закрытые за проход исходные ветви

1. **OpenAI Chat Completions / Responses:** protocol-specific request/response/history/SSE/tool continuation/reasoning serialization, terminal/error/schema downgrade cases. `src/handlers/llm_providers/protocols/{chat_completions,responses}/`, adapters в `handlers/llm_providers/`. Новый [openai-protocol-state-machines](../03-runtime/openai-protocol-state-machines.md); ранее созданный Gemini/ChatGPT Plan документ не повторяется.
2. **ASR/RAG/Beat installables:** модельные планы и readiness/stop/install/uninstall, пять ASR recognizers, RAG local embeddings/rerankers и Beat. `src/handlers/asr_models/*`, `src/managers/rag/install_spec.py`, `src/game_connections/services/beat_install.py`. Новый [asr-rag-beat-install-plans](../01-functional/asr-rag-beat-install-plans.md).
3. **Голосовые asset packs:** manifest/extract/download/staging/per-file promotion/delete и результаты. `src/installables/voice_assets.py`, `src/utils/voice_assets_installer.py`. Новый [voice-asset-distribution](../01-functional/voice-asset-distribution.md).
4. **Installer faults и rollback:** `src/controllers/install_controller.py` task/cancel/clean/uninstall, `src/utils/pip_installer.py` manual RECORD cleanup/deferred DLL, `src/core/runtime_environments.py` managed revision/promotion. Новый [installer-recovery-and-uninstall](../03-runtime/installer-recovery-and-uninstall.md).
5. **Build/distribution/native launcher:** `build.py`, `scripts/launcher.c`, `scripts/run.bat`, `scripts/run.py`, `src/release_contract.py`, `scripts/validate_release_contract.py`. Зафиксировано различие build recipe и обязательного full archive contract. Новый [build-and-release-distribution](../03-runtime/build-and-release-distribution.md).
6. **Core vs AI dependencies:** `requirements.txt`, AST inventory 720 Python files и selected import/call sites. Новая [предварительная матрица](../04-dependencies/python-import-reachability.md); число 720 — разобранная выборка import scan, **не** весь reachable runtime/100% coverage.
7. **Token/pricing:** `src/managers/{context_counter,model_pricing_manager}.py`, `src/controllers/model_controller.py` и UI usage. Новый [token-budget-and-pricing](../01-functional/token-budget-and-pricing.md).
8. **HOI4:** standalone `src/connetors/hoi4/*.py` и игровые mod assets, проверен поиск регистраций вне package. По найденным Core source references интеграция **не доказана активной**; standalone прототип подробно зафиксирован [здесь](../01-functional/hoi4-standalone-prototype.md). Не добавлять в active parity без подтверждения.
9. **Path semantics:** `src/core/app_paths.py`, managed environment path, RAG helpers, GigaAM/Silero native loaders, logging. Новый [filesystem-paths-and-native-loaders](../03-runtime/filesystem-paths-and-native-loaders.md).

10. **HTTP clients/network classification:** `src/core/networking/{http_clients,errors}.py`, `handlers/llm_providers/http_transport.py`; service handle ownership/reference count/stream/error phase/secret URL mask/timeout policy. [network-client-ownership-and-errors](../03-runtime/network-client-ownership-and-errors.md).

### Функциональные discoveries и риски

- Chat Completions и Responses нельзя объединять до безымянной `messages` serialisation: Responses хранит протокольный контекст/reasoning и tool IDs, имеет свой SSE state machine и downgrade policy.
- RAG «uninstall» в обнаруженных model install plans фактически no-op; GigaAM ONNX installed readiness не обязательно гарантирует наличие весов; clean reinstall более разрушителен, чем обычный revision/staging rollback.
- Voice asset promotion пофайлово; отдельный uninstall path может игнорировать failure return; release build не равен validated self-contained release. Доказательство — статические branches, не empirical failure reproduction.
- Цена `protocol_id/model` без endpoint/account в cache: вероятный cross-mirror pricing risk, но реальные billings не проверялись. Last usage и оценка token budget имеют разные области состояния.
- В разнесённых RAG helpers различается правило path resolution для relative `NEUROMITA_CHECKPOINTS_DIR`; модель может быть не найдена при разном запускающем окружении. У GigaAM/Silero есть реальная adapter-зависимость от Win32 8.3 ASCII path. Runtime behavior не испытывался.
- HOI4 `on_declare_war/on_focus_complete` в моде имеют пустые event hooks; bridge использует `dummy_ai_logic`, ни одного активного штатного импортёра в основном Python Core найдено не было.

### Консолидация функционального паритета

Добавлена [feature-traceability](../06-design-input/feature-traceability.md) с неполной, но проверяемой матрицей основных capability families → source/docs → requirements → candidates functional ownership → будущие validation fixtures. Она **не** заменяет granular per-action inventory, но сокращает риск утраты функций при независимом архитектурном ревью. Отсутствующим / experimental сценариям не приписывается обязательный Rust parity.

### Контроль качества и границы уверенности

Проверены синтаксические цели локальных Markdown ссылок (0 отсутствующих) и уникальность `REQ-*` строк в `functional-requirements.md` (0 повторов). **Исходники не редактировались**. Не исполнялись Python Core, модели, CUDA, игровые скрипты, provider/API calls, установщики, обновления, Win32 launcher, Unity или destructive database operations. Исходники просматривались статически; тесты и platform behavior не объявлять подтверждёнными.

**Процент завершённости не пересчитан.** Список активных capabilities не закрыт исчерпывающим discovery, поэтому выдумывать прирост от 65–70% нельзя. Матрица зависимостей предварительная: imports не равны reachable execution и не доказывают поддерживаемость Rust-аналога.

### Приоритет следующего прохода

1. Оставшиеся handler/provider adapters и settings key-level GUI actions; найти скрытые dynamic imports в registry и реальные producer/consumer event contract, не возвращаться к прочитанным OpenAI protocol bodies.
2. Prompt editor: исходники submodule отсутствуют в snapshot, поэтому требуется отдельно предоставить его содержимое либо проверить фактическую availability; не объявлять его core functionality автоматически. GUI framework Slint/Qt comparison по решению пользователя **вне аудита**.
3. Secret/config migration/storage, пользовательские пути, platform permissions и file locking; в частности весь hard-coded path inventory за пределами осмотренных helpers.
4. Полная model/component readiness matrix, installer cancellation/retry and repair fixtures, release offline integrity checks; distinguishing partially installed vs healthy and rollback behavior.
5. Сводная capability→requirement→validation coverage checklist, статус каждой ветки `ACTIVE/CONDITIONAL/LEGACY/EXPERIMENTAL/UNRESOLVED`, завершить evidence-to-requirement traceability.
6. После **фактического** закрытия функционального аудита — исследование Rust dependency candidates с первичными источниками, native DLL и licensing; архитектуру Rust с нуля проектировать только после отдельного ревью. Детальная Unity-client implementation отложена пользователем.

## Checkpoint: 2026-10-30 — продолжение после `pass30`, глубокий GUI/settings/graph проход

**Источники:** локальный extracted snapshot `CodeNow.zip` (Python source, `.git`-objects нет) и MD из `NeuroMita_audit_docs_2026-10-30_pass30.zip` (начальная база: **70** файлов). **Scope:** только static audit активного Python Core/GUI и его локальных consumer contracts. Не модифицированы ни Python-файлы, ни Unity source, ни AI inference. Нет сетевых provider/API calls, Qt GUI E2E, CUDA/Win32 tests или DB destructive runs.

### Результат этого прохода: 16 новых Markdown-документов

1. [Settings storage, migration, secrets and schema](../01-functional/settings-storage-and-migrations.md): async saves, DPAPI vs plaintext presets, update contour migration, schema compatibility. `settings_manager`, `settings_registry`, `update_contour`, `api_presets_controller`, `model_settings/*`.
2. [Typed service ownership and settings observers](../03-runtime/typed-services-and-settings-observers.md): Services registry, owner handles, observer delivery. `EventBus.emit(sync=True)` определяет порядок/очередь, **не** гарантирует synchronous consumer execution.
3. [Settings sections/lazy pages](../02-ui/settings-navigation-and-lazy-pages.md): 12 registered sections, feature gates, conditional loading, deep-links.
4. [Settings key → consumer evidence](../02-ui/settings-key-consumer-evidence.md): sampled **83 literal keys** в пяти registered builders, статические `CORE_LITERAL/SERVICE_LITERAL/GUI_LITERAL/DYNAMIC_CORE_KEY/NO_OTHER_LITERAL` — не definitive reachability и не все keys.
5. [Graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md): GC/merge/TTL/retype/full clear; защита, конкуренция, sequential partial apply, per-character vs all.
6. [Graph viewer interactions](../02-ui/graph-viewer-interactions.md): filtering, geometry/selection, search, aliases, manual type operations, cancellation limitations.
7. [Sandbox page](../02-ui/sandbox-page-functional-contract.md): readout, model/character/time/settings, AI control panels, game mute flow.
8. [Chat composer and attachments](../02-ui/chat-composer-and-attachments.md): per-batch file limit, clipboard and capture, dual ownership UI bytes/temp files, ASR lease and sending.
9. [Chat history/stream and message actions](../02-ui/chat-stream-history-and-message-actions.md): character-scoped reconciler, 256 bounded caches, persistence ack, delete/retry/regen/finetune/context snapshot provenance.
10. [Gallery lifecycle/viewer](../02-ui/gallery-lifecycle-and-photo-viewer.md): scan/source path, watcher debounce 250ms, <=12 thumbnail jobs/batch, <=160 cached images, per-viewer snapshot, decode/navigation.
11. [Structured AI panels](../02-ui/structured-ai-results-presentation.md): brief/JSON/off, target splitting, read-only data; diverging predicate for `role=structured` when mode=`Выкл` (risk requiring E2E).
12. [Character library and maintenance actions](../02-ui/character-library-and-maintenance-actions.md): selected-for-settings ≠ active-chat character, bulk action separation, migrations and multi-character destructive flows.
13. [News and logs granular state](../02-ui/news-and-logs-live-ui-contracts.md): release repo from contour; Home release focus; 64 KiB/500 lines 2s active-only log polling; stale result/error bounds.
14. [Home launcher/update UI](../02-ui/home-launcher-update-and-game-state.md): primary action state machine, selected Python/Unity updates, tester code, `python_applied` pending restart even if Unity later fails/cancelled.
15. [Wiki navigation, localized Markdown and Unicode anchors](../02-ui/wiki-navigation-localization-and-anchors.md): path confinement, app links/locale/history, ASCII-only slug potentially loses/misaligns Russian headers. `wiki_page.py:160-220,601-857`; GuideDialog wrapper; GuideWidget deep still partial.
16. [Auditable 20-domain progress ledger](audit-coverage-ledger.md): measurable primary runtime-path categories **12/20**, partial **8/20**; **не** оценка полной доли проекта и не attempt inflated percent.

Обновлены `README`, `active-feature-inventory`, `source-evidence-index`, `open-questions`, `functional-requirements`, `feature-traceability`, `current-problems`, этот checkpoint. Содержательные требования в новых документах привязаны к source path/lines и новой валидации (все тесты future backlog).

### Конкретные source-grounded открытия

- Предустановленные API presets/ключи и ChatGPT Plan DPAPI accounts имеют разную persistence/security boundary. Не обещать одинаковую secret protection.
- Graph GC и bulk character purge не имеют очевидного единообразного all-or-nothing commit; часть counters и success banners — результат попытки/action plan, не всегда число изменённых rows. Cancel dialog может не останавливать native/worker action.
- Sandbox отключает game requests вместе с максимальным `GAME_BLOCK_LEVEL`, а re-enable не сбрасывает block-level. Ожидаемую пользовательскую политику надо зафиксировать отдельно.
- При удалении отдельной вложенной mini-preview UI bytes меняются, но temp staging в `ChatController` не получает per-photo delete; реальный send идёт из UI bytes. Нужны явный ownership, cleanup, content MIME, batch-limit tests.
- Chat live/history/stream renderer использует revision/tombstones/message ID и bounded caches до 256; удаление/regen — intents, не гарантии уже выполненной записи в БД. Context snapshot имеет exact-ID lookup и fallback на last-request для некоторых других форматов.
- Structured `role=structured` truthiness predicate отличается от embedded/stream strict mode check, создавая reachable-if-event risk при режиме off.
- Галерея использует stat-based image identity и snapshot списка viewer; `ensure_directory` без `parents=True`, фото не редактируются из UI.
- Home multi-component update может оставить **Python already applied** при Unity fail/cancel; требование перезапуска Python в таком случае сохраняется, batch не следует считать атомарным.

### Контрольный список с устойчивым denominator

| Coverage state | Областей | Интерпретация |
|---|---:|---|
| `PRIMARY` | **12/20** | главный runtime path задокументирован, но edge cases/E2E могут оставаться |
| `PARTIAL` | **8/20** | остаются подтверждённые незакрытые шаги/действия/пограничные ветви |
| `UNRESOLVED` | 0/20 | все 20 high-level областей хотя бы начально обнаружены |

**12/20 не равно «60% всего аудита завершено»**. Не исчерпаны registered actions и dynamic callgraph; могут быть новые workstreams. Прежние приблизительные 65–70% не использовать как проверенное измерение. Новые 18 документов углубили workstreams `5/6/7/13/14/20` и сопутствующие, но не закрыли автоматически `PARTIAL` области.

### Точка следующего прохода, без повторного чтения закрытых веток

1. **GUI tail:** оставшиеся wiki/help контракты, dialogs lifecycle, UI errors/notifications, settings остальные builders, full `page action → intent → state/effect` traceability. Home/News/Logs/Gallery/Sandbox/Character/Graph/Chat/Wiki основные interactions уже глубоко разобраны — к ним возвращаться только по выявленному cross-boundary вопросу.
2. **Graph/RAG and history identity:** transactional tests/reader proofs для batch GC/retype, merge aliases, reindex/full rebuild, per-character identity, delayed action after switch, stale revisions; не объявлять partial operations атомарными.
3. **Services/settings:** all runtime dynamic consumers and migration, key defaults; проверить `NO_OTHER_LITERAL` неиспользуемые? только после path tracing; `SettingsRegistry` callbacks/resubscribe and shutdown.
4. **Install readiness/repair matrix:** один реестр всех component status probes и `installed/ready/running/healthy/uninstall/repair`, native DLL inventory and Windows runtime.
5. **External reachability:** Telegram, games/helpers, standalone modules, dynamic plugins/imports; отличать `ACTIVE` от `CONDITIONAL`/`EXPERIMENTAL` по фактической регистрации.
6. **Full evidence coverage:** каждая active action и consumer → capability → requirement → fixture, close unverified `UNRESOLVED` evidence; dependency research потом, архитектура Rust и Slint vs Qt GUI benchmark **отложены пользователем на отдельный этап**.

## Integrity / audit test caveat

Вторичная проверка Markdown path links, ZIP isolation и source path references должна выполняться перед упаковкой. **Исходные Python/Unity файлы не были изменены.** SHA releases остаётся историческим указанием предыдущего агента, независимая проверка невозможна без `.git` в snapshot.

### Дополнение: самостоятельный GuideWidget

Проверен `src/ui/widgets/guide_widget.py` и `src/ui/windows/guide_dialog.py`: 13 реально зарегистрированных страниц (3/5/13 для basic/advanced/full), persistent GUIDE_LEVEL, независимая локаль, текстовые step links→focus region на скриншоте, zoom/crop/scroll, Help→Wiki callback. Старые page classes, отсутствующие в `_init_pages`, не внесены в ACTIVE. Создан [02-ui/guide-walkthrough-and-image-focus.md](../02-ui/guide-walkthrough-and-image-focus.md).

### Дополнение: подтверждённые UI dialogs и их lifecycle

Проверены `BackgroundTaskDialog`, `MessageProcessingDialog`, `ExportDialog`, `DbExportDialog` и `StyledMessageDialog` вместе с фактическими caller/controller paths. Принципиальное различие: hide/esc/X не отменяет задачу, `stopRequested` — лишь cooperative interruption request; pipeline Apply/Reset/Cancel разделены; экспорт JSONL fine-tuning не совпадает с выгрузкой SQLite world.db. Документ: [02-ui/dialog-interaction-and-background-task-contracts.md](../02-ui/dialog-interaction-and-background-task-contracts.md). Остальные QDialog остаются PARTIAL.

## Следующий проход: history/memory/graph, Telegram, AI import boundary, installer catalog (2026-10-30)

**Источник:** локальные исходники `CodeNow.zip`, сохранённая база `pass45` из 88 MD; commit SHA исходников отсутствует. **Изменения:** только `audit-docs/docs/`; Python/Unity/runtime-проект не менялись. Никакой целевой Rust-архитектуры не утверждено.

**Новые source-backed документы:**

1. `01-functional/graph-extraction-ledger-and-clear-consistency.md` — разделённые `graph_processed_messages` и graph data, `clear_for_character` против GUI clear, skip-existing и failed extract mark.
2. `01-functional/character-reset-epoch-and-storage-consistency.md` — последовательные, но не атомарные reset paths и history_epoch guards.
3. `01-functional/character-custom-fields-and-formula-policy.md` — custom fields, ordered clamp, AST evaluator и consumer contracts.
4. `01-functional/memory-purge-embedding-identity-regression.md` — воспроизведённый `eternal_id` против SQLite id mismatch при purge, orphan/stale joining.
5. `04-dependencies/ai-worker-python-core-import-boundaries.md` — фактические Python-side imports RAG AI worker into former core modules и необходимость выделить контракт без переписывания inference.
6. `02-ui/telegram-auth-modal-contracts.md` — код/2FA UI dialogs, correlated futures, timeout/invalid/close.
7. `01-functional/installable-catalog-lazy-registry-and-status.md` — две стадии catalogue, group loader, cached failed imports, service probe and revision.

**Выполненные тесты:** 23 history/epoch, 17 custom field/safe-eval, 18 memory positive unit tests — всего 58 успешных. `test_character_history_clear.py` не исполнялся из-за отсутствия PyQt6; это не падение теста. Временные SQLite DB runs с реальными `GraphStore`/`DatabaseManager` и `MemoryManager` подтвердили два конкретных дефекта (содержимое/методика в документах). Миграции пользовательских баз **не выполнялись**. Сетевые, GPU, полный Qt E2E и multi-process tests НЕ выполнялись.

**Checkpoint для следующего исполнителя:** сначала проверить `memory id → embeddings` весь life cycle (insert/update/soft delete/purge/reindex/async), graph extraction processed journal (fail/skip/clear/rebuild/concurrent), then complete installer readiness/repair matrix and Telegram integration tests. После — остатки Settings GUI, dynamic import/native DLL dependency reachability и матрица one-action-per-requirement. Работа по user decision исключает Slint/QML comparison, финальную Rust архитектуру и подробности Unity animation/render code.

**Прогресс:** `PRIMARY 12/20; PARTIAL 8/20` прежнего фиксированного denominator, пока без повышения: выявленные дефекты расширяют глубину двух partial направлений, но не закрывают всех edge paths. См. [контрольный список](audit-coverage-ledger.md).

## Checkpoint: функционально-ориентированное продолжение (после `pass_next`)

**Уточнение пользователя:** приоритет — **содержание реализации** (что делает система, user cases, сообщения, состояния и жизненный цикл), а не поиск/исправление ошибок старого Python. Любой случайно замеченный дефект фиксировать коротко, не уходить в расследования. Полную Rust-архитектуру и сравнение GUI не проектировать до завершения функционального аудита.

**База:** `CodeNow.zip` Python snapshot; MD из `NeuroMita_audit_docs_2026-10-30_pass_next.zip` (**95 файлов**), полностью сохранены в `audit-docs/docs`. Наличие git SHA нельзя самостоятельно перепроверить по исходному ZIP. Unity client deep internals не читались. Python/Unity исходники не менялись.

**Новые три source-backed документа:**

1. [Character world and environment awareness](../01-functional/character-world-and-environment-awareness.md): семь JSON world resources, канонизация ID, индивидуальный owner/former/visitor lore, per-request integration; программа сама объясняет персонажу наличие Unity, источник ввода Player, голосовой backend/readiness и доступное обновление.
2. [GameMaster scene direction](../01-functional/game-master-scene-direction.md): **действующий** observe/command Unity task → structured intent → скрытая директива для следующей реплики; отделена новая структурированная система scene rules/lifetime/transcript, **не найденная в production registrations**.
3. [Conversation session projections](../03-runtime/conversation-session-projections.md): Unity-owned actor/character/conversation identity, ephemeral view snapshot, EventBus/ChatPanel updates, disconnect behavior и независимость player message transport.

**Источники основного чтения:** `src/domain/world_character_relations.py`, JSON из `src/domain/world_contexts/`, `src/services/character_environment_context.py`, `src/services/contracts.py`, `src/services/dialogue_runtime_state.py`, `src/services/dialogue_transcript_service.py`, `src/services/game_master_*.py`, `src/schemas/game_master_response.py`, actual callers: `model_controller.py`, `prompt_controller.py`, `chat_controller.py`, `game_connections/handlers/actions/create_task.py`, `server_controller.py`, `main_controller.py`, `controllers/gui/chat_panel_view_model.py`, `ui/widgets/chat_panel.py`, `ui/chat/dialogue_presentation.py`, `controllers/gui/presentation_hub.py`, `ui/windows/app_window_base.py`. Чтение выборочное по обозначенным source ranges; не считать полным аудитом всего содержимого этих крупных классов.

**Обновлены:** `README`, `active-feature-inventory`, `source-evidence-index`, `audit-coverage-ledger`, `functional-requirements`, `feature-traceability`, `open-questions` и этот checkpoint. Новые `REQ-WORLD-*`, `REQ-ENV-*`, `REQ-GM-*`, `REQ-DIALOGUE-VIEW-*` описывают *функции*, а не обязательство воспроизводить дефекты.

**Статус:** PRIMARY **12/20**, PARTIAL **8/20**. Добавленная глубина в областях 07/10/14/17/20 не даёт оснований повышать статус частично пройденных областей. Не объявлять 60% фактической полноты всего аудита. Тесты/сетевые/GPU/GUI запуски в новом проходе не выполнялись, временные БД и исходники не изменялись.

**Куда идти дальше:**

1. Ветвь `07` — характерные gameplay effects, локальные profile/custom content flows и реально действующие потребители состояний персонажа. Не повторять исследование custom formula и сброса history.
2. Ветвь `14` — ещё непройденные GUI intents/notifications/Settings dynamic consumers; приоритизировать **сценарии** UI, а не подробности Qt layout.
3. Ветвь `17` — реальные routes внешних интеграций и event/voice deliveries; различать ACTIVE/CONDITIONAL/standalone.
4. Ветвь `16` — функциональные состояния install/readiness/repair для каждого компонента, без новых баг-воспроизведений.
5. Ветви `19/20` — core-vs-AI import/install/native dependency matrix и полная трассировка живых actions → capabilities → requirements → future parity tests. Rust alternative research только после фактического завершения discovery; GUI comparison и architecture design — отдельный этап.

**Не повторять:** общее создание сервисов, основные LLM provider protocol, историю/графовые баги, уже разобранную основную GUI, Unity animation/render; вместо этого закрывать оставшиеся capability paths.

**Позднее дополнение этого же функционального прохода:** создан [Unity world state prompt projections](../03-runtime/unity-world-state-prompt-projections.md) — четвёртый новый документ. Рассмотрены `SET_GAME_DATA` character-local snapshot, отличия last-known state от `runtime_events`/`tv_observation`, stable rules/static catalog vs dynamic executable capabilities, disconnected gate, разные provenance для state/data/GM instructions. Это функциональная декомпозиция, не исследование дефектов. Добавлены `CAP-WORLD-STATE-001—003` / `REQ-WORLD-STATE-001—003` и traceability.

## Checkpoint 2026-10-31: 30-minute full functional pass (от 99 Markdown до 113)

**Цель прохода:** восстановить прежде недостаточно описанные user-facing и runtime возможности Python без расследования дефектов и без проектирования Rust architecture. Основной источник `CodeNow.zip`, распакован в рабочую копию `audit_pass4`; прежняя документация 99 MD в `audit_pass6/audit-docs/docs`. Все правки ограничены `audit-docs/docs`. Исходники/AI/Unity не редактировались; SHA архивом не подтверждается.

### Создано 14 новых Markdown-документов

1. `01-functional/structured-character-actions-and-side-effects.md` — от схемы ordered segment и request capabilities до runtime local effects, mini-games, memory, reminders, Unity request, persisted/task projections и action-memory requested history.
2. `01-functional/installable-catalog-and-runtime-readiness-matrix.md` — static 31 installable cards + dynamic RAG; declared/imported/installed/ready/loaded/executed различия и lifecycle.
3. `01-functional/remote-voice-presets-and-character-routing.md` — авторизованные удалённые голосовые профили и назначения персонажам.
4. `02-ui/asr-model-gallery-and-settings-workflows.md` — пять ASR моделей, chooser/installer/diagnostic сценарии.
5. `02-ui/local-voice-model-management-and-compile-dialogs.md` — local TTS/VC presets, модели и compile UX.
6. `02-ui/api-presets-and-model-parameter-editor-workflows.md` — API preset CRUD, parameter schema, validation/actions.
7. `04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md` — AST survey 720 source files, real 7 main pages/12 settings sections/12 optional services/31 static installable entries with 11 loader groups, 4 LLM provider adapter classes, 5 ASR.
8. `02-ui/rag-pipeline-and-embedding-provider-user-workflows.md` — конфигурация пользовательского RAG pipeline/embedding provider отдельно от readiness и AI inference.
9. `02-ui/context-and-sqlite-data-inspection-workflows.md` — просмотр context/history/usage и GUI SQLite editor, включая manual descriptions.
10. `01-functional/fine-tuning-data-capture-curation-and-export.md` — sample UUID/rating, retention, filters, Raw JSONL/ShareGPT, separate debug collection.
11. `01-functional/hardware-acceleration-and-ai-engine-administration.md` — Windows DXGI+CUDA identity, AI worker shared/split lifecycle and reinstall/reset state machine.
12. `01-functional/language-normalization-rag-morphology-and-speech-numerals.md` — раздельные RU RAG lemma/FTS, numeric multilingual speech normalization.
13. `04-dependencies/full-requirements-runtime-evidence-ledger.md` — **все 84 записи** `requirements.txt`, 32 с direct AST import, 52 без прямого import, с явным запретом считать последние ненужными без wheel closure.
14. `01-functional/registered-character-catalog-and-identity-contracts.md` — точный реестр 9 characters, lazy creation, persistence, special secret and GameMaster behavior, selection/reload/GUI-only mode.

### Факты и пересмотр progress

**Область 07 `Characters/settings/effects` переведена `PARTIAL → PRIMARY`**: по `managers/character_manager.py:27-227`, `characters/__init__.py:9-256`, `characters/character.py:80-259,462-635`, `controllers/character_controller.py:11-114`, `schemas/structured_response.py:260-474`, `controllers/model_controller.py:2251-2477` доказаны основной character lifecycle, per-character effects, scene-directed requests и специальная роль GM. Это не означает exhaustive edge coverage.

**Актуально: PRIMARY `13/20` (65% выбранных workstreams), PARTIAL `7/20`.** **Не процент завершения всего аудита.** Исчерпывающее registry/data mapping по всем user functions ещё не построено. Runtime live Windows/Qt/GPU/Telegram/Unity E2E в проходе НЕ выполнялись. Тестовый прогон в этот проход не заявлен.

Обновлены `README.md`, `00-research/active-feature-inventory.md`, `source-evidence-index.md`, `open-questions.md`, `audit-coverage-ledger.md`, `06-design-input/functional-requirements.md` и `feature-traceability.md`.

### Следующая source-based точка продолжения

1. **GUI (`14 PARTIAL`):** найти ещё не зарегистрированные в реестре описаний actions/notifications, загрузить остаток dialogs и составить per-callback action→state→side effect→validation, не описывать виджеты ради самих виджетов.
2. **Install/readiness (`16 PARTIAL`):** dynamic RAG/custom installable и component-specific probe; добиться end-to-end state matrix without rewriting installer.
3. **External (`17 PARTIAL`):** все реально зарегистрированные network/Telegram/game player paths; проверить conditional status, не путать с standalone прототипами.
4. **Dependencies (`19 PARTIAL`):** замкнуть 52 `STATIC-NOT-FOUND` через wheel `Requires-Dist`, bootstrap scripts и native DLL. Отдельно выявить нужные Python AI worker helper imports и исключить transitive optional package confusion.
5. **History/RAG (`05/06 PARTIAL`):** только ещё не описанные *функциональные возможности* dedup/search/index/import/maintenance; уже известные дефекты не исследовать повторно.
6. **Traceability (`20 PARTIAL`):** полное сопоставление зарегистрированных GUI/in-game actions и требования паритета с fixtures. Не выбирать технологию Rust/GUI прежде фактического завершения аудита.

**Области, умышленно отложенные:** Slint vs QML/Qt comparison, выбор Rust crates, окончательный domain/ownership design, перенос Python inference, глубокий Unity render/animation audit. `CodeNow.zip` остаётся замороженной ревизией; изменения origin/new HEAD требуют явного повторного fetch/snapshot.


## Checkpoint: 2026-10-31, следующий functional pass (113 → 122 Markdown)

**Источник:** прежний комплект 113 Markdown из `NeuroMita_audit_docs_functional30_2026-10-31.zip` + локальный `CodeNow.zip` Python snapshot, без достоверного `.git/HEAD`. Это продолжение функционального discovery с приоритетом требований и пользовательских сценариев, **не баг-охоты и не разработки новой Rust-архитектуры**. Не менялись Python/Unity source, inference models, Legacy/Obsolete; кроссплатформенные E2E не проводились.

### Документы созданы в этом проходе

1. [RAG storage/retrieval/indexing](../01-functional/rag-storage-retrieval-and-indexing-modes.md): history `id`/`message_id`, memory `eternal_id`, active/archive, forgotten/island, vector/FTS/keyword/graph/sentence; on-write, missing и full index как разные lifecycle.
2. [Installable probes/actions](../01-functional/installable-component-probe-and-operation-contracts.md): identity ресурса, installed/ready/backend, status/progress/clean/update/uninstall отдельных компонентов.
3. [ASR/TTS managed model lifecycle](../01-functional/asr-tts-managed-backend-operational-contracts.md): пять registered recognizers, model weights, backend requirements, Python worker activation.
4. [API model catalogue and dialogs](../02-ui/api-model-discovery-and-conditional-dialogs.md): test/get models, metadata, сортировка/поиск/copy/selection, голосовой modal hide/cancel; неподтверждённые UI classes оставлены `UNRESOLVED`.
5. [Manual mini-games / Beat UI](../02-ui/game-settings-manual-launch-and-beat-cache.md): явный Unity/Sandbox target, разрешения и live кнопки, Beat backend/cache lifecycle.
6. [Screen/camera/image management](../02-ui/screen-camera-image-management-user-contracts.md): самостоятельные desktop/webcam/Unity camera pathways, image description provenance, orphan cleanup, snapshot event consumer.

**Обновлены** `README`, `active-feature-inventory`, `source-evidence-index`, `audit-coverage-ledger`, `functional-requirements`, `feature-traceability`, этот checkpoint. Обязательные требования и validation fixtures каталогизированы; данные о `ProtocolPipelineDialog`/`NewPresetDialog` классифицированы `UNRESOLVED` до подтверждения использования.

### Coverage и что исследовать дальше

**PRIMARY 13/20, PARTIAL 7/20** — доля основных контрактов 65%, это **не процент завершённости аудита**. Выросла глубина доменов 05/06/09/11/12/14/16/19/20, но не закрыто ни одного из 7 оставшихся workstreams целиком до PRIMARY.

1. **GUI:** закончить remaining action→service matrix (screen/image consumers, callbacks/events, users requiring data migrations); отличать реально вызываемый UI от неиспользуемых определений.
2. **History/RAG/graph:** завершить функциональный traversal от старых сообщений и graph entity до итогового LLM контекста, с provenance/dedup/ranking/cancellation. Не переключаться на поиск дефектов.
3. **Installables:** захватить оставшиеся конкретные installer profiles, статусы и реальные переходы model installed→initialized→available; отдельно требовать Windows/AI worker E2E позднее.
4. **External:** Telegram auth delivery, Web integrations, updates, отдельные standalone modules; dynamic service registration evidence.
5. **Dependencies/Traceability:** разрешить 52 requirements без прямого import на уровне wheel transitives/native/optional, не объявлять ненужными без evidence; exhaustive per-action requirements/validation ledger.

GUI framework comparison, окончательное проектирование Rust Core и подробный старый Unity animation/rendering internals исключены. Следующему проходу следует продолжить с этой точки, не пересоздавать предыдущие документы.

**Позднее дополнение текущего прохода:** седьмой документ [external integration entrypoints and reachability](../01-functional/external-integration-entrypoints-and-reachability.md) про production Telegram, optional LLM tools, remote voice vs standalone FastAPI VTT и экспериментальный HoI4. `REQ-EXT-ROUTE-001—003` добавлены в требования и трассировку. Итого на текущем срезе 120 Markdown. Статус **13 PRIMARY / 7 PARTIAL** не повышен: external network/service E2E не делались.


**Второе дополнение:** восьмой новый документ [RAG query/fusion/rerank/result](../01-functional/rag-query-fusion-reranking-and-result-contracts.md) восстанавливает путь `QueryBuilder → retrievers → combine → enrich → linear score → optional cross encoder → top/graph quota → public result` и различие explicit/automatic RAG. `REQ-RAG-RANK-001—004` добавлены в требования и traceability. **Итог: 121 Markdown**, PRIMARY **13/20**, PARTIAL **7/20**; нет основания объявлять весь RAG домен завершённым без проверок реальных источников и prompt injection.


**Третье дополнение:** девятый source-backed документ [RAG → Prompt](../01-functional/rag-context-injection-and-source-rendering.md) закрывает чтение реального `ModelController.process_rag` и `PromptController` на уровне условий, source rendering и порядка системных сообщений. **122 Markdown**, 13 PRIMARY / 7 PARTIAL по неизменному базовому знаменателю. Новые требования `REQ-RAG-PROMPT-001—004` включены в traceability.

**Следующий functional discovery: локальный IPC.** Добавлен десятый документ [external runtime IPC](../01-functional/local-runtime-ipc-external-control-contract.md), подтверждающий отдельный settings-controlled TCP/JSON control-plane, шесть register-allowed методов, диагностические и admin операции. Production registration `main_controller.py:121-127,218,684-686`, реальные методы из `runtime_ipc_service.py:46-70` + `ai_engine_controller.py:1973-2011`. Добавлены `REQ-LOCAL-IPC-001—003` в requirements/traceability. **123 Markdown**, всё ещё **13/20 PRIMARY, 7/20 PARTIAL**.

**Дополнение GUI/onboarding.** Новая [спецификация первого запуска](../02-ui/first-run-agreement-language-and-guide-flow.md) (одиннадцатый документ этого прохода) охватывает persisted `EULA_ACCEPTED`, языки EULA и особый restart case, reject/close, автооткрытие Guide и Wiki. В реестр/requirements/traceability добавлены `CAP-UI-ONBOARD-001—003`, `REQ-UI-ONBOARD-001—003`. **124 Markdown**, **13/20 PRIMARY**, **7/20 PARTIAL**.

**Уточнение зависимостей без роста знаменателя:** `04-dependencies/full-requirements-runtime-evidence-ledger.md` дополнен доказанными **строковыми package requirements** внутри установочных планов (`google-api-core` F5; `platformdirs/requests/certifi/...` Beat), а также отличием имени модели `mistralai/...` от реального Python SDK import. Счётчик direct AST imports `32/84` и `STATIC-NOT-FOUND 52/84` не изменён. Это не выполнение транзитивной проверки wheel metadata.

**Продолжение native dependency audit.** Двенадцатый новый source-backed документ [Native Windows/Core vs Python AI](../04-dependencies/native-system-api-and-ai-library-ownership.md) описывает реальные ОС/драйверные функции и границу Core/инференса с файлом-происхождением, а не просто сопоставлением названий Python пакетов. Добавлены `REQ-NATIVE-001—004` в требования/traceability. Теперь **125 Markdown**, **13 PRIMARY / 7 PARTIAL** (полнота native DLL/requirements всё ещё PARTIAL).


## Checkpoint: функциональное продолжение — inventory / AI Hub / статусные UI-проекции (2026-10-31)

**Основа:** `CodeNow.zip` (локальный Python snapshot, `.git` нет), `NeuroMita_audit_docs_functional_continuation_2026-10-31.zip` (**125 Markdown** до текущего прохода). Исходники Python/Unity/AI не изменялись. Новые изменения — только `audit-docs/docs` (5 новых документов + обновлённые индексы/требования). Сравнение Slint/Qt, проектирование Rust и inference-porting **не выполнялись**. Без network/GPU/Windows/Qt integration runs.

**Разобраны новые capability slices:**

1. [Полная статическая номенклатура компонентов](../01-functional/installable-catalog-identity-and-coverage.md): **31 статическая** не-RAG карточка (3 backend, 12 TTS, 5 ASR, 1 Beat, 2 dependencies, 8 voice including aggregate) и dynamic RAG presets/custom; checkpoint ID отличается от aggregate lookup.
2. [Catalog status lifecycle](../03-runtime/installable-status-observation-and-invalidation.md): metadata-only first pass, context fingerprint/revision, статус cache/inflight, pending/timeout/stale, позднее событие `COMPONENT_STATUS`, partial category recheck.
3. [Install operation admission and queue](../03-runtime/install-operation-admission-queue-and-completion.md): preview/backend confirmation → accepted/duplicate/rejected → FIFO worker → cooperative cancel → finished/failed → отдельно readiness probe. Headless/GUI и quiesce разных видов.
4. [AI Hub action traceability](../02-ui/ai-hub-interaction-traceability-checklist.md): 17 user actions с intent/status/evidence; dirty settings guard, component settings, cache and log actions.
5. [Generation/voice/error presentation](../02-ui/generation-progress-error-and-voice-indicators.md): model/compression/tool/error events, global activity count, per-message voice/failure markers и независимые Game/Voice/RAG/ASR/Screen/Camera status chips.

**Coverage denominator не менялся:** PRIMARY **13/20**, PARTIAL **7/20**. Этот проход закрывает *конкретные ранее не прослеженные подпути* областей 14/16/20, но не проверяет все UI actions, все компонентные backend execution paths и все транзитивные AI зависимости. Отсутствие повышения — осмысленное, а не отсутствие выполненной работы.

**Следующая точка:** пройти оставшиеся GUI page actions/keyboard shortcuts и typed notifications; провести consumer-by-consumer mapping settings; затем проверять all component `status()`/`initialize()` paths на уровне исходников без реальных downloads; разметить dependency closure по runtime environment и AI subprocess (включая native wheels и DLL). History/RAG index/full reindex паритет всё ещё PARTIAL, изучать функциональную семантику без отдельного defect hunt. В каждом проходе добавлять source-backed строки в traceability, а не считать MD-файлы процентами готовности.

Прогресс по newly defined exit gates за этот проход: `16/Installers 3/5`, `14/GUI 3/5` — см. [audit-coverage-ledger](audit-coverage-ledger.md). Эти gate counts не смешивать с overall PRIMARY 13/20.

## Checkpoint: 30-minute wall-clock continuation — functional contracts (2026-10-30/31)

**Контроль времени:** начало `2026-10-30 22:42:47 UTC`, заданный срок `2026-10-30 23:12:47 UTC`. Фактический конец и итоговую длительность записать только после достижения отметки; преждевременное завершение не считать выполнением лимита.

**Базис:** предыдущий архив `NeuroMita_audit_docs_functional_pass9_2026-10-31.zip`, **130 Markdown**. Исследуемый Python snapshot — `CodeNow.zip` без `.git` (не выдавать исторический SHA за перепроверенный). Unity baseline и новая Rust architecture не менялись/не проектировались; исходники не модифицированы. В рабочем docs срезе **147 Markdown**, то есть **17 новых** (на данный момент) и 9 обновлённых существующих документов. Все 130 старых документов сохранены.

### Новые документы этого прохода

| Документ | Основная функциональная область |
|---|---|
| [installer operations](../01-functional/installable-families-runtime-operations.md) | 31 статическая AI Hub ID по семействам + dynamic RAG; distinct status/install/remove/initialize |
| [external HTTP sources](../01-functional/external-http-sources-and-user-actions.md) | Web search/read, Google, remote endpoints; production vs standalone |
| [history & memory user lifecycle](../01-functional/history-memory-lifecycle-and-user-operations.md) | active/archive/facts/islands/summary/derived indexes, UI maintenance |
| [settings live actions](../02-ui/settings-functional-actions-and-live-effects.md) | 12 sections Settings и distinction store/change/apply effect |
| [implicit dependencies](../04-dependencies/implicit-optional-and-installer-owned-packages.md) | HTTP/2 implicit optional `h2`, installer-owned dependencies F5/Beat и Core/AI разделение |
| [keyboard/clipboard](../02-ui/keyboard-clipboard-and-direct-manipulation-contracts.md) | Actions without toolbar buttons, event handlers and scopes |
| [Telegram session](../01-functional/telegram-bot-protocol-routing-and-session-semantics.md) | Auth/queue/remote voice/result routing/Unity or desktop |
| [main-page reachability](../02-ui/main-pages-action-reachability-matrix.md) | Seven registered pages and actions→consumer mapping |
| [embedding provider wire](../01-functional/embedding-provider-wire-and-failure-contracts.md) | OpenAI/Gemini/local providers, query/document, batching |
| [structured capability gating](../03-runtime/runtime-effect-availability-and-structured-schema-policy.md) | Request-dependent JSON schema fields, permission to request versus execution |
| [test corpus & parity](../06-design-input/existing-test-corpus-and-functional-parity-gates.md) | 250 `test_*.py`, 2177 syntactic `test_*` definitions, offline evidence without claiming universal pass |
| [multimodal message content](../01-functional/multimodal-message-content-representations.md) | Content representations for LLM/history/embedding/UI |
| [performance traces](../03-runtime/per-request-performance-traces-and-diagnostic-metrics.md) | Request phases, bounded trace buffer, diagnostic semantics |
| [TV observation](../01-functional/tv-observation-youtube-frame-and-dialogue-provenance.md) | Unity TV/YouTube frame and subtitle provenance |
| [World DB export/import](../01-functional/world-db-json-export-import-user-workflow.md) | UI filters, character scope, portable JSON, derived embeddings excluded |
| [process topology](../03-runtime/functional-process-topology-and-ownership-boundaries.md) | Main Core/GUI, Python inference workers, Unity/TG/other independent consumers |
| [dialogue actor and message IDs](../01-functional/dialogue-actor-and-message-identity-contracts.md) | Identity/provenance of physical actor, character, speaker, origin and turn |

### Верификация и наблюдения

- Покрытие фиксированных областей: **13 PRIMARY / 7 PARTIAL (65% только primary contracts)**, не 65% завершённости всего аудита. Незакрытые 05 history, 06 RAG/graph, 14 GUI, 16 installables, 17 external, 19 dependencies, 20 traceability.
- Поддержан `audit-coverage-ledger.md`: указано, что реально исследовано в каждом оставшемся workstream и что мешает exit-gate. Увеличение числа документов не переводит область автоматически в `PRIMARY`.
- Актуальные offline tests: `test_message_content_codec` + `test_performance_trace` — **14 passed**; при добавлении `test_mini_game_public_context` — **18 passed, 1 failed** (и 2 subtests passed); отдельно четырёх модулей speaker identity/conversation writer/target — **16 passed, 2 failed**, оба fail относятся к отсутствующему `ModelController._canonicalize_structured_targets`. `test_performance_trace_integration` collection заблокирован `pygame`. Следует пользоваться `existing-test-corpus...md` для точного сопоставления — эти результаты **не** являются общим test suite report.
- Никаких GPU, Unity, voice hardware, Qt/Windows, Telegram/API/network/install E2E не выполнялось. Все находки проверяются чтением source, кроме явно указанных offline unit тестов. Ошибки старого Python в этом проходе не исследовались целенаправленно и не исправлялись.

### Следующая точка: конкретные непроверенные функциональные маршруты

1. История / память: полностью каталогизировать редкие UI actions восстановления/миграций, разные форматы import/export; проверить соответствие primary ID и derivations (без борьбы с Python defects).
2. RAG/Graph: завершить список advanced query options, graph extraction user-flow, условные model/dependency branches; сверить model-specific embedding contracts.
3. GUI: action-to-handler ledger для остальных dialogs, conditional menus, state transitions, shortcuts и error UX; live GUI проверки остаются отдельным exit gate.
4. Installables: все component-specific status/plan/initialize/remove, ремонт managed environments и backend readiness; без установки weights/download в данном окружении.
5. Внешние интеграции: пройти optional Telegram / website / Unity consumer boundary, отделить standalone из экспериментов; дополнительные клиентские Unity internals не становились первоочередной задачей.
6. Dependencies: прояснить wheel transitives, Windows DLL closure, extras и неявные импорты. Python-only inference crates/libraries в Core не переносятся автоматически.
7. Трассировка: довести coverage всех действующих actions/flags из исходников, связать requirement→validation; архив и 250 тестовых файлов не заменяют active reachability.

**Ограничение постановки:** новый Rust Core проектируется после functional audit; не переносить Python manager structure. Ошибки текущего кода фиксировать кратко, не тратить проходы на их устранение.

**Дополнение в текущем 30-minute pass:** обнаружен отдельный source-backed контракт [`LLMStreamEvent → TextDeltaCoalescer → GUI`](../03-runtime/llm-stream-event-and-presentation-lifecycle.md), 18-й новый документ (**148 Markdown всего**, 130 исходных сохранены); для презентационного coalescer выполнены **4 targeted tests passed** (`test_llm_http_transport.py`, 34 deselected). События reason/content/tool/usage и обновления UI, terminal/cancel разграничены. Не меняет headline coverage `13/20 PRIMARY` и не подтверждает внешнее provider/Qt E2E.

**Source preservation verification (this pass):** 987 Python `.py` files under extracted `CodeNow.zip/src` compared to original `CodeNow.zip` by uncompressed CRC32: **987/987 match, 0 modified, 0 missing**. This establishes no Python source edits in the working snapshot; it does not validate source correctness. Previous Markdown preservation independently checked: 130/130 paths retained; no duplicate `REQ-*` explicit labels were found in the newly appended requirement section.

**Фактическое окончание 30-минутного wall-clock прохода (UTC):** `2026-10-30 23:13:06 UTC`; начало `2026-10-30 22:42:47 UTC`; фактически **30 мин 19 с** к моменту итоговой отметки. После неё выполнена контрольная упаковка. **148 Markdown (18 новых), 130/130 прежних файлов, 13 PRIMARY / 7 PARTIAL**. Исходники и Legacy не редактировались; GUI/Unity/network/device E2E не проводились.

---

## Pass 11 — продолжаемый функциональный аудит (`2026-10-30`, start 23:22:43 UTC)

**Основание:** `CodeNow.zip` как исходный рабочий снимок, 148 Markdown из pass10 (все сохраняются); fallback исторической ревизии не должен выдаваться за локально подтверждённый Git SHA. **Контрольная цель 30 min wall-clock:** 23:52:43 UTC. **Фактическая отметка окончания:** `2026-10-30 23:53:01 UTC`. **Код и Legacy:** не редактировать.

### Работы по подтверждённой функциональности

1. [Исполняемые prompt packs и переменные](../01-functional/dsl-executable-prompt-contract.md): local path resolver, SET persistent/local, SEED RAG/memory/graph, nested script, static/volatile prompts.
2. [Post-DSL](../01-functional/post-dsl-response-rules-and-debug-state.md): упорядоченные text/regex/field rules, возврат текста и изменение персонажных параметров.
3. [Шахматы и морской бой](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md): реальное состояние игры, child process queues и character reaction request; различение LLM requested action/gameplay confirmation.
4. [Сохранение requested actions через сжатие истории](../01-functional/structured-action-history-and-compression-bridge.md), [детерминированные сюжетные triggers](../01-functional/exact-core-memory-triggers-and-session-activation.md) без смешения с security.
5. [Микрофон: физическая идентичность/бэкенды/мониторинг](../01-functional/microphone-physical-identity-backends-and-monitoring.md), [локальная+игровая речь и ASR gate](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
6. [EventBus факты и команды](event-producer-consumer-callsite-index.md), [срок жизни подписок](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md); 288 объявленных имён, 202 literal direct callsites, 117 dual-sided emit+subscribe **статически**, не runtime E2E.
7. [Семь типов Unity ingress](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md), [headless Core readiness](../03-runtime/headless-core-functional-surface-and-readiness.md) и ограничение интерактивной Telegram auth без GUI.
8. [GUI async behavior](../02-ui/intent-workloads-and-visible-state-consistency.md), [индекс 52 вызовов в 20 ViewModels](gui-async-operation-callsite-index.md) с явным разделением `latest`, `exclusive`, `coalesced`.
9. [Неактивная/standalone часть](standalone-and-unproven-runtime-reachability.md): `CommandParser` self-demo, remote DSL resolver, новые GameMaster services, web/VTT и test inprocess AI классифицированы отдельно.
10. [Все 31 static installable ID](../06-design-input/installables-component-by-component-parity-matrix.md) и отдельный dynamic denominator RAG; **0/31 реальных install/device E2E**, не повышать статус готовности по наличию матрицы.

### Валидация и ограничения

- Offline targeted tests: **308 passed, 3 failed, 2 passed subtests**, четыре отдельно заблокированных модуля при сборе (PyQt6, `chess`, `qtawesome`); [точные наборы](pass11-functional-audit-handoff.md). Не считать полным suite pass.
- 987 source `.py` сравнили с original `CodeNow.zip` по CRC32: **987 совпадений, 0 отклонений**. Старые скрипты/Legacy не меняли.
- Полнота остаётся **13 PRIMARY / 7 PARTIAL** по [фиксированному ledger](audit-coverage-ledger.md), не процентом всего проекта. Новые документы углубляют сложные частичные контракты.
- Отдельное GUI/Unity/Windows/device/Internet/weights/AI Engine E2E не выполнялось. Пояснения о возможных регрессиях и тестовых fixtures не означают, что старый код проверяли на всех машинах.

### Следующая точка

Продолжить семь `PARTIAL`: 05 History, 06 RAG/Graph, 14 GUI registration/action reachability, 16 per-machine installable status (если среда поддерживает), 17 optional integrations, 19 Python Core/AI native dependency closure, 20 end-to-end source→capability→requirement→validation. **Прежде всего исследовать функциональные маршруты, а не дефекты**. Проектирование Rust-архитектуры и GUI stack выбор после аудита.

---

## Pass 12 — функциональное исследование, 30-minute wall clock

**Начало (UTC):** `2026-10-30 23:59:24`. **Плановая отметка:** `2026-10-31 00:29:24`. **Фактическая отметка финальной фиксации (UTC):** `2026-10-31 00:29:44 UTC`; **wall-clock:** `30 мин 20 сек`.

Вход: 164 docs Pass 11 + источник `CodeNow.zip`. Выполнена source-grounded инвентаризация RAG/Graph, Settings/GUI/dynamic UI, модели готовности, роль/identity истории, per-component status tests, статический индекс 250 тестовых файлов. **16 source-grounded документов плюс handoff** (полный перечень и ссылки: [Pass 12 handoff](pass12-functional-audit-handoff.md)). Дополнены реестр способностей, source evidence, требования и traceability.

**Offline addressed validation:** 8 отдельных запусков pytest, **157 passed + 14 subtests; 4 failed in IPC/TV run**, но не полный suite/Qt/Windows/Unity/CUDA/online test. Статическое исследование: 99 уникальных RAG/Memory settings key; 517 `.connect` callsites в 75 GUI файлах; 20 dialogs, 16 file pickers, 8 input dialogs, 29 confirmations; AST 250 `test_*.py` в `utils/Testing` и 2177 определений тестовых функций; всё это **source evidence**, не доказательство runtime invocation.

**Прогресс:** `13/20 PRIMARY, 7/20 PARTIAL` (65% только первичных контрактов), без искусственного повышения. Открыты: History/Memory consistency, RAG/Graph real inference + provenance, GUI action→handler→effect, component installs + readiness E2E, optional external integrations, wheel/native dependency closure, full source→CAP→REQ→Validation. Дефекты Python не расследованы отдельно. Rust architecture/GUI framework choice откладываются до конца functional audit.

**Следующий pass:** использовать [handoff](pass12-functional-audit-handoff.md), искать *новые* active/conditional маршруты по точке входа и доказательствам, не повторять исходный анализ, не проектировать Rust Core и не исправлять старые скрипты.

**Pass 12 дополнительная попытка локальных интеграционных проверок:** `test_runtime_ipc.py` + `test_tv_observation.py` → **13 passed, 4 failed** (из них три Qt/qtawesome environment unavailable и один incomplete test fixture на restart), `test_telegram_credentials_gate.py` и `test_remote_voice_delivery.py` не собраны из-за отсутствующих `telethon` и `pygame`. Эти случаи не расследовали; Core/AI/network E2E не подтверждены. Итого в Pass 12 **157 passed, 14 subtests, 4 failed**, плюс два заблокированных collection modules.

**Дополнительная source-верификация Pass 12:** [динамические import-регистры](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md); 19 новых успешных тестов lazy tools / AI contour / declarative profiles. В текущем проходе **157 passed, 14 subtests, 4 failed** и 2 blocked collection modules.

**Source integrity check Pass 12:** все **1 024** `.py` из исходного `CodeNow.zip` проверены по CRC32 против рабочего снимка, 1 024 совпали, 0 изменены/не найдены; из них 987 внутри `src`. Никакие Legacy/Obsolete файлы не редактировались.

**Pass 12 static import inspection:** AST of production `.py` shows **24 dynamic import/native loader callsites in 18 files** ([индекс](production-dynamic-import-callsite-index.md)); these are syntactic candidates only, not proof each optional feature is used.

**ИТОГ Pass 12:** UTC начало `2026-10-30 23:59:24`; финальная отметка `2026-10-31 00:29:44 UTC`; wall-clock **30 мин 20 сек**, контрольные 30 минут пройдены. Итог **181 Markdown**, новых относительно Pass11 — **17**, сохранено **164/164** прежних. 157 addressed tests passed, 14 subtests passed, 4 failed, 2 modules blocked on collection. Источники не менялись; окончательный ZIP содержит только `audit-docs/docs`.
