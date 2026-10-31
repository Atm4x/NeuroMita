# Выявленные функциональные требования

Статус: частичный набор по исследованным областям. Не является полной спецификацией Core 2.0. «Сохранить» относится к пользовательскому результату; конкретный Python-механизм не обязателен. Проверки в таблицах — acceptance scenarios; полное исполнение этих наборов не подтверждено. Фактически выполненные узкие fixtures и ранее полученные tests описаны отдельно в тематических документах и checkpoint, без подмены полной проверки требований. Приоритет продолжения уточнён пользователем: сначала функции Python core; Unity client internals не блокируют этот проход.

## Pass 13: уточнённые требования и границы

Validation здесь — acceptance scenario; выполненные отдельно fixture имеют более узкую область, указанную в ссылках. Исходная архитектура не задаёт решение новой системы.

| ID | Требование | Доказательство | Проверка паритета |
|---|---|---|---|
| REQ-RAG-SPACE-001 | У source vectors, query и derived cache определены model space/identity, scope и последствия смены модели | [Mixed models](../01-functional/rag-mixed-model-recall-and-provenance.md) | Same/different dimension models, shared model ID на другом endpoint, old/new embeddings, memory eternal_id |
| REQ-RAG-RECALL-001 | Результат поиска различает source identity/provenance и применённые recall/fusion ограничения; отсутствие vector не лишает lexical hit без явной policy | [Recall](../01-functional/rag-mixed-model-recall-and-provenance.md) | FTS без selected-model vector, legacy BLOB, vector_only/two_stage/intersection, graph model mismatch |
| REQ-SET-SEMANTICS-001 | Для настройки определены effect, scope, момент применения, validation и разные источники defaults | [Consumers](../02-ui/memory-rag-settings-consumer-semantics.md) | Missing persisted key vs UI default vs Reset; live/restart/reindex; malformed saved value |
| REQ-SET-SEMANTICS-002 | Archive history, forget memory и delete graph дают разные явно описанные data outcomes | [TTL](../02-ui/memory-rag-settings-consumer-semantics.md) | Multiple characters, priorities, islands, protected graph rows, each TTL mode |
| REQ-SET-SEMANTICS-003 | Изменения нормализации/model/search policy имеют определённый cache/reindex effect | [Cached helpers](../02-ui/memory-rag-settings-consumer-semantics.md) | Toggle normalization после первого поиска; switch model; refresh index |
| REQ-HIST-PAGING-001 | Initial/older history имеют identity/generation и отсекают чужие/устаревшие ответы и удалённые сообщения | [Paging](../02-ui/history-page-fencing-and-live-replay.md) | A→B→A, reload того же character, late older page, empty identity, concurrent delete |
| REQ-HIST-PAGING-002 | Refresh сохраняет новые live messages без дубликатов и повторных effects, timeout сохраняет live view | [Replay](../02-ui/history-page-fencing-and-live-replay.md) | Snapshot перед/после persisted ack, stream active, slow DB, bounded retention |
| REQ-DATA-EXCHANGE-001 | Semantic JSON transfer отличим от full backup; scope, ID remap и судьба derivations явны | [DB exchange](../01-functional/world-db-exchange-isolated-validation.md) | A/B→export A→import C; artifacts/index absent, unknown columns/version |
| REQ-DATA-EXCHANGE-002 | Повторный import, duplicate policy, rollback/partial outcome и отмена определены отдельно | [Transaction fixture](../01-functional/world-db-exchange-isolated-validation.md) | Repeat, different uniqueness schemas, memory constraint failure, IO/cancel |
| REQ-EDIT-NODE-001 | Authoring/preview показывает поддержанный язык и diagnostics; graph conversion не теряет неподдержанный текст молча | [Node workflow](../02-ui/prompt-editor-authoring-and-node-workflow.md) | Runtime DSL с RUN/seed vs node subset; partial parse; text→graph→text |
| REQ-EDIT-NODE-002 | Preview state/logs/trace и layout metadata отличимы от production state и сохранённого script content | [Editor](../02-ui/prompt-editor-authoring-and-node-workflow.md) | Run buffer без Save, Apply/Save As, metadata clear, variables sources |
| REQ-DIALOG-OUTCOME-001 | Accepted/Apply/Close/Skip имеют определённый downstream outcome; draft update не равен durable save или выполнению системной команды | [Modal callbacks](../02-ui/dialog-class-reachability-and-action-outcomes.md) | Pipeline draft→preset Save; invalid model schema; compile Skip; VCR missing producer |
| REQ-INSTALL-OUTCOME-001 | Для installable операции перечислены реально поддержанные effects, ready predicates и ownership удаления | [Per-family matrix](installables-component-by-component-parity-matrix.md) | Package/model/shared backend, no-op uninstall, clean vs initialize, ready без inference |
| REQ-DEP-PROVENANCE-001 | Dependency decision основан на используемой функции, reachability, native/assets/transitives и конкретной source/license provenance | [Metadata/PE](../04-dependencies/installed-wheel-metadata-and-native-evidence.md), [niche](../04-dependencies/core-niche-alternatives-and-parity-gates.md) | Python wrapper vs native API, stale license metadata, dictionary/weights licenses |
| REQ-DEP-PROVENANCE-002 | Наличие alternative не считается доказанным functional parity или поддержкой всех языков/protocols | [Common options](../04-dependencies/core-library-alternatives-and-native-costs.md), [niche options](../04-dependencies/core-niche-alternatives-and-parity-gates.md) | RU morphology/numerals corpus, MTProto user auth, tokenizer vocabulary, malformed JSON/effects |
| REQ-SCHEDULE-INPUT-001 | Tool natural-language due, structured ISO due и numeric timer имеют разные validation/error/timezone contracts | [Reminder routes](../01-functional/reminders-and-timers.md) | List/add/delete/timer, malformed/aware dates, disabled scheduler, busy character и failed downstream admission |
| REQ-HUB-SETTINGS-001 | Draft/validation/storage save/model application различимы, ошибка не теряет edited values | [Schema→service](../02-ui/ai-hub.md) | Strings/types, invalid device, per-field/global errors, durable failure и re-open |
| REQ-HUB-SETTINGS-002 | Load/migration, Reset to saved, dirty refresh и component/category switch имеют явные outcomes | [AI Hub settings](../02-ui/ai-hub.md) | Load, который мигрирует storage; empty schema vs error; delayed response; missing selected component |
| REQ-INSTALL-TARGET-001 | Python versions/specifiers/extras/markers проверяются для определённой target среды, не подменяются SemVer | [Packaging source + alternatives](../04-dependencies/core-library-alternatives-and-native-costs.md) | Name aliases, pre/dev/post/epoch/+cu, marker-false, разные host/worker Python, metadata vs importable package |
| REQ-NUMERIC-CORE-001 | Не-AI vector/audio алгоритмы имеют определённые float/layout/normalization/buffering и tolerance contracts | [Numeric/DSP boundary](../04-dependencies/core-library-alternatives-and-native-costs.md) | Empty/zero/nonfinite/dimension mismatch, top-k ties, exact vs ANN recall, FIFO underrun/overflow и resampling continuity |
| REQ-PROCESS-IDENTITY-001 | Launcher/update/worker cleanup различают owned process identity, graceful stop, timeout, forced stop и отказ доступа | [psutil consumers](../04-dependencies/core-library-alternatives-and-native-costs.md) | PID reuse, wrong executable/create_time, respawn, stale marker, mapped cache и живой/отсутствующий parent |
| REQ-IMPORT-SNAPSHOT-001 | Snapshot scope, identity matching, variables merge/replace, derivations и live-state refresh определены отдельно от полного rollback приложения | [Snapshot source follow-up](../01-functional/history.md) | Insert-before-explicit-ID, duplicate refs, foreign/deleted/archive row, absent variable, concurrent generation и failed save |

## Изображения, инструменты, контент и desktop функции

Дополнение обслуживания/config/runtime (также будущие проверки, не выполненные тесты):

| ID | Требование/решение для спецификации | Доказательство | Будущая проверка |
|---|---|---|---|
| REQ-DATA-001 | Import/export имеет формат/version, scope, перенос referenced artifacts и понятную полноту | data-maintenance, compatibility-imports | Повторный import, existing identities, partial JSON, файлы изображений |
| REQ-DATA-002 | Source mutation обновляет revision и инвалидирует производные данные по единой policy | data-maintenance | DB edit/import/delete, reindex прежнего count, late graph/summary result |
| REQ-DATA-003 | Recovery сохраняет provenance/оригинал, preview, проверенный backup и ledger retry | compatibility-imports | WAL/concurrent writer, повтор одного item отдельно/в ZIP, collision target IDs |
| REQ-DATA-004 | Maintenance различает preview/apply, attempts/success и partial commits | data-maintenance | Graph failure→retry, skip-existing после clear, cancel после batch commit |
| REQ-CONFIG-001 | Settings memory acceptance и durable save различимы; schema/default/secret/migration policies явны | settings-and-preferences-store, provider-configuration | Write failure/shutdown race, load без уведомления, mutable nested value |
| REQ-VOICE-002 | Installed/loaded/selected/initialized/playing имеют независимые outcomes и operation identities | voice-controls | Cancel/hide/late same-model finish, admission failure, settings write error |
| REQ-JOB-001 | Jobs имеют owner, budgets, cancellation propagation и судьбу поздних effects | background-tasks-and-events | Close owner, deadline blocked I/O, postcommit cancellation, replacement overlap |
| REQ-EVENT-001 | Bus acceptance не выдаётся за предметный ACK; ordering/backpressure/drain scope определён | background-tasks-and-events | Нет подписчика, overload, flush best-effort, subscriber failure |
| REQ-UPDATE-001 | Update/install/restart/recovery различают verified/staged/activated, preserve policy и rollback | launcher-and-updates | Locked zipapp, interrupted overlay, Unity rollback, restart activation |
| REQ-API-001 | Preset/protocol/model/parameters/accounts имеют устойчивые IDs и проверяемое fallback поведение | provider-configuration, account-authentication | Смена preset во время check, key rotation, auth refresh/revoke/error |

| ID | Требование/решение для спецификации | Доказательство | Будущая проверка |
|---|---|---|---|
| REQ-IMAGE-001 | Manual attach, one-shot, background history и scheduled image turn имеют самостоятельную доступность | images-and-capture | Кнопка snapshot при выключенных auto/background, image-only send |
| REQ-IMAGE-002 | Frame несёт source/time/format/dimensions; acquisition/staging/request budgets определены отдельно | images-and-capture | PNG attachment, смена камеры, несколько staging операций, stale frame |
| REQ-IMAGE-003 | Original/projection/description/drawing/gallery имеют явные разные lifecycles и cleanup outcomes | images-and-capture, navigation-gallery-and-help | DB недоступна при orphan scan, file delete во время history write/read |
| REQ-TOOLS-001 | Каталог tools отражает enabled/usable и причины отказа; arguments валидируются при исполнении | tools-and-web | Lazy import failure/recovery, malformed arguments, disabled native/schema call |
| REQ-TOOLS-002 | Tool получает immutable character/request scope; side effect outcome и retry/idempotency явны | tools-and-web | Два simultaneous character calls, cancellation после создания reminder |
| REQ-TOOLS-003 | Search provider, web extraction, ограничение результата и budget являются самостоятельными policies | tools-and-web | Нет DDGS/service, timeout, oversized page, empty results |
| REQ-CONTENT-001 | Author packs поддерживают композицию/условия/state/знания с проверяемой runtime-preview семантикой | prompt-language-and-packs | Nested include/RUN, invalid expression, локальные scopes, diagnostics |
| REQ-CONTENT-002 | Разделить чистую prompt projection и durable SET/seed/link effects; определить reload/version contract | prompt-language-and-packs | Повторный build, pack switch/reset, ошибка после seed |
| REQ-CONTENT-003 | Pack update фиксирует source revision, проверяет архив, сохраняет recovery и читательскую согласованность | prompt-language-and-packs | Cancel/replace failure/concurrent build, malformed archive |
| REQ-BEAT-001 | Timeline analysis/cache/batch/status различимы; method и fallback provenance наблюдаемы | music-beats | Cache hit после смены backend/threshold, no beats, batch partial failures |
| REQ-GAME-001 | Desktop game имеет owner/match/revision и валидирует команды против актуального состояния | desktop-mini-games | Новый match во время engine/LLM think, переключение current character |
| REQ-GAME-002 | Сохранить явные сценарии chess rules/UCI/GUI/reactions и Sea Battle placement/turn/hit без зависимости от Unity client | desktop-mini-games | Legal move/promotion/close, hit сохраняет ход, hidden opponent board |
| REQ-NAV-001 | Навигация/локальная справка/галерея/новости/логи имеют loading/empty/failure и независимые availability gates | navigation-gallery-and-help | Backend loading, offline feed, смена языка, исчезнувший файл, close during read |
| REQ-WEB-001 | Отдельно решить необходимость standalone VTT/mock API; не добавлять их deps к обязательному core автоматически | standalone-web-surface | Документированное решение scope и отдельный entry/inference contract |

| ID | Требование | Источник | Проверка будущей реализации |
|---|---|---|---|
| REQ-RUN-001 | Поддерживать полный GUI, оболочку без основного backend и работу без GUI | CAP-RUN-001/003 | Запуск каждого режима, проверка состава доступных действий |
| REQ-RUN-002 | GUI показывает состояния запуска/ошибки backend и сохраняет доступные shell actions | CAP-RUN-002 | Успех, медленный старт, отказ и закрытие во время старта |
| REQ-RUN-003 | Внешние запросы не обрабатываются до готовности обязательных сервисов | CAP-RUN-002 | Подключение клиента на каждом этапе bootstrap |
| REQ-RUN-004 | Optional capability имеет наблюдаемую доступность и причину отказа | CAP-RUN-005 | Disabled/missing/installing/failed/ready сценарии |
| REQ-RUN-005 | Одновременные запросы загрузки одной capability не создают конкурирующие instances | CAP-RUN-005 | Конкурентный запрос во время старта |
| REQ-RUN-006 | Поздний startup result после disable/shutdown не публикуется | CAP-RUN-002/005 | Управляемая задержка factory и смена состояния |
| REQ-RUN-007 | Зависимые ресурсы прекращают использование dependencies до их уничтожения | CAP-RUN-004/005 | Обратный dependency order и отказ cleanup |
| REQ-RUN-008 | Повторный shutdown безопасен, ошибка одного шага не пропускает остальные cleanup steps | CAP-RUN-004 | Повторная и конкурентная остановка, инъекция ошибок |
| REQ-RUN-009 | После закрытия UI фоновые результаты не обращаются к уничтоженным представлениям | CAP-RUN-004 | Shutdown при активных workers/subscriptions |
| REQ-RUN-010 | Headless принимает внешний stop и возвращает различимые успех/ошибку запуска | CAP-RUN-003 | Signal, duration, server bind failure |
| REQ-RUN-011 | AI runtime не требуется для доступности core/shell; inference остаётся отдельным Python-компонентом | Scope + bootstrap separation | Старт с отсутствующими AI environments; уточнить все реальные imports |
| REQ-RUN-012 | Пути данных определены относительно installation/configured roots, а не случайного cwd | E-015/016 | Запуск из другого cwd; полный аудит путей ещё нужен |

Нуждаются в уточнении: допустимый общий shutdown deadline, критерий degraded readiness, поддерживаемый публичный CLI, необходимая совместимость launcher exit codes. Это design inputs, не принятые API.

## Диалог, история и производные данные

| ID | Требование/решение, которое надо специфицировать | Доказательство | Будущая проверка |
|---|---|---|---|
| REQ-TURN-001 | Request фиксирует speaker/recipient/participants/source/policy независимо от последующего переключения GUI | llm-and-generation, characters | Смена current character во время очереди/stream/TTS |
| REQ-TURN-002 | Определить admission/serialized turn/cancellation и terminal outcome на каждый request | llm-requests, llm-and-generation | Overload, cancel до/после headers/первого chunk/commit |
| REQ-TURN-003 | Stream correlation сохраняется до final persisted message id; partial output различим с committed reply | llm-and-generation | Partial stream error, malformed structured final, повтор |
| REQ-TURN-004 | LLM retry/fallback зависит от фактического начала ответа; не дублировать уже принятые effects | llm-requests, current-problems RISK-001 | Timeout до headers и после body, tools с побочными эффектами |
| REQ-TURN-005 | Разделить generation effects/history commit/delivery/voice; определить partial failure policy | llm-and-generation, history, voice-output | History write failure после stat change, второй recipient failure |
| REQ-HIST-001 | Редактирование/удаление/регенерация/snapshot import имеют явный scope и результат persistence | history | Import error, merge vs replace variables, media preservation |
| REQ-HIST-002 | Original message/DB row/attempt/task/delivery ids имеют различные роли | history, memory, unity-retry-outbox | Identity collision, retry сохранённого result и regeneration |
| REQ-DERIVED-001 | Derived summaries/index/graph публикуются только для актуальной source revision | history-compression, rag, knowledge-graph | Edit/delete/reset во время background LLM/index build |
| REQ-DERIVED-002 | Compression budget/coverage/quality и lossy fallback наблюдаемы; исходник recoverable | history-compression | Oversized history, failed summarizer, partial fallback coverage |
| REQ-MEM-001 | Character scope входит в logical memory identity и каждую mutation/cleanup/index lookup | memory, current-problems ISSUE-001/006 | Два character с одинаковым eternal id, TTL и purge |
| REQ-MEM-002 | CRUD/islands/seeds/forget/delete/TTL/capacity представлены отдельными policies | memory | Protected islands, full capacity, repeated seed, read without insert |
| REQ-RAG-001 | Search source filters/model identity/index revision согласованы при edit и model switch | rag | Single embedding update без count change, archived/deleted sources |
| REQ-REM-001 | Reminder/timer сохраняется с различимым durable outcome, timezone/deadline semantics и delivery acknowledgement | reminders-and-timers | Restart, disk failure, late generation rejection, aware datetime |

## Python inference boundary и управление компонентами

| ID | Требование/решение | Доказательство | Будущая проверка |
|---|---|---|---|
| REQ-AI-001 | Самостоятельный Python worker имеет versioned language-neutral contract, request ids и typed failures | ai-ipc | Handshake mismatch, unknown method, malformed/late response |
| REQ-AI-002 | Worker alive/endpoint ready/environment installed/model loaded различимы | ai-ipc, ai-environments | Lazy endpoint без модели, failed probe, runtime replay |
| REQ-AI-003 | Logical cancel, native completion и forced recovery различимы и ограничены ресурсно | ai-ipc | Hung native call, full queues/control starvation, repeated recovery |
| REQ-INSTALL-001 | Metadata/probes/compatibility/settings/admission/install/initialize — отдельные состояния и операции | installations | Slow status при доступном catalog, settings validation error |
| REQ-INSTALL-002 | Общая serialized install queue доступна GUI/headless независимо от окна | installations | Headless enqueue, dedup, shutdown/maintenance при running job |
| REQ-INSTALL-003 | Обычная replacement сохраняет previous state до validation/commit; clean rebuild имеет отдельный contract | installations, ai-environments | Failure каждого staging/commit/activation шага, crash recovery |
| REQ-INSTALL-004 | Cancel завершает queued/inflight outcome, не запускает незапрошенный повтор installer | installations | Cancel PTY, pipes fallback, child process и blocked sync action |
| REQ-UI-001 | Dirty settings survive background refresh; navigation/close не теряют values молча | AI Hub GUI | Status refresh при edit, native hide/close, failed save |

## Голос и игровой consumer

| ID | Требование/решение | Доказательство | Будущая проверка |
|---|---|---|---|
| REQ-VOICE-001 | Synthesis artifact/delivery/playback outcomes и ownership файла независимы | voice-output, telegram-voice, unity-media-transfer | Empty TG response, conversion failure, audio load/playback error |
| REQ-SPEECH-001 | Устойчивая identity устройства с обнаружением исчезновения/неоднозначности/backend failure | speech-input | Hotplug, index reuse, одинаковые names, endpoint identity unavailable |
| REQ-SPEECH-002 | Capture/recognition/routing/draft/submission раздельны, release сохраняет результат, cancel отсекает late result | speech-input, unity-dialogue-admission | Lease expiry, cancel при transcribe, stale capture revision |
| REQ-SPEECH-003 | Единственный owner реплики фиксируется с session/capture identity; fallback не создаёт двойной ход | unity-transport, speech-input | Reconnect/new game owner между capture и delivery |
| REQ-UNITY-001 | Выбрать и проверить гарантию result acceptance с ACK/idempotency/reconnect | unity-transport, unity-retry-outbox | Socket write success + Unity reject/crash до presentation |
| REQ-MEDIA-001 | Для shared artifacts нужны format/count/size/expiry и retry-safe ownership | unity-media-transfer | Oversized manifest/file, orphan on blocked turn, already deleted WAV |
| REQ-UNITY-002 | Settings projection version/session-fenced и отделена от user settings source | unity-media-transfer | Out-of-order parse, reconnect revision reset, stats persistence |
| REQ-UNITY-003 | Coalescing player/events, auto quotas/continuation/idle budget имеют явный product contract | unity-auto-dialogue, unity-dialogue-admission | New queued player answer, reaction merge, failure после budget reservation |

Эти строки не утверждают, что нынешние случайные ограничения/дефекты надо сохранить. Для policies с потерей событий/данных сначала зафиксировать желаемое поведение. Числовые defaults текущего кода не считаются окончательными параметрами новой системы.

## Дополнительные контракты из позднего Python provider/installer pass (2026-10-30)

| ID | Необходимый контракт | Источник / проверка |
|---|---|---|
| REQ-PROVIDER-006 | Typed ordered message transforms и диагностируемая wire projection, включая multimodal/system/unknown steps | `message_transforms.py:41-445`; golden fixtures |
| REQ-PROVIDER-007 | Transforms не должны мутировать сохранённую историю или исходный request snapshot; сравнивать полные payloads, а не только сводку | `message_transforms.py:133-180,421-445`; isolation regression |
| REQ-PROVIDER-008 | Отделять native schema, prompt structured, URL rewrite, wire stream, usage/reasoning и HTTP vs stream failure для Gemini и Responses | `gemini_provider.py:56-581`; provider fixture/negative tests |
| REQ-AI-FAIL-001 | Poisoned CUDA worker recycling с потерянным in-flight outcome, а не обработка в том же процессе | `runtime_failure_policy.py`, `worker_process.py:410-446`; fault injection |
| REQ-AI-FAIL-002 | Distinct OOM/ordinary failure/cancellation vs fatal context failure | `runtime_failure_policy.py:10-76`; GPU-mocked tests |
| REQ-AI-FAIL-003 | Re-initialize/validate worker state и resolve outstanding correlations после fatal exit | `worker_process.py:410-446`; supervisor/integration test |
| REQ-INSTALL-005 | Per-component artifact/compile/patch/verification requirements, differentiated variants and cancellation/error states | F5/Fish/Omni/EdgeRVC/FFmpeg/OpenCV plans; fixtures + sandboxed installs |

## Дополнение: installer recovery, provider parity, зависимости и дистрибутив (2026-10-30)

Ниже новые требования из документов текущего прохода, не отдельное утверждение о готовности architecture phase.

| ID / диапазон | Контракт | Доказательство | Приёмка новой реализации |
|---|---|---|---|
| REQ-PROTO-001—005 | Два wire dialect (`Chat Completions`, `Responses`) сохраняют tool IDs, protocol replay, terminal stream, cancellation и bounded schema downgrade | [openai-protocol-state-machines](../03-runtime/openai-protocol-state-machines.md) | Golden fixtures stream/nonstream, refusal, mixed multimodal history, duplicate tool IDs, retry |
| REQ-ASR-INSTALL-001—003 | ASR installs имеют category/backend/weights readiness и идентифицируемый компонент | [asr-rag-beat-install-plans](../01-functional/asr-rag-beat-install-plans.md) | Install missing weights, requirements present, device selection, cancel |
| REQ-RAG-INSTALL-001—003 | Привязать embeddings, RAG модели и readiness к наблюдаемым ownership/cleanup | [asr-rag-beat-install-plans](../01-functional/asr-rag-beat-install-plans.md) | Model downloaded partial, unmanaged cleanup, reinitialize |
| REQ-BEAT-INSTALL-001—002 | Сохранить backend-specific Beat dependency/install/UI workflow | [asr-rag-beat-install-plans](../01-functional/asr-rag-beat-install-plans.md) | Backend disabled/unavailable, model switching, reinstall |
| REQ-ASSET-001—005 | Character voice bundles: manifest/version, staged extraction, character identity, removal outcomes | [voice-asset-distribution](../01-functional/voice-asset-distribution.md) | Corrupt ZIP, partial copy, mismatched manifest, failed removal |
| REQ-INSTALL-LIFE-001—006 | Task lifecycle, cancellation, staging/commit, clean override, deferred delete, repair boundaries | [installer-recovery-and-uninstall](../03-runtime/installer-recovery-and-uninstall.md) | Process cancel, power-loss, Windows DLL lock, partial HTTP, metadata repair |
| REQ-DIST-001—005 | Native launcher/update/bootstrap/self-contained distribution + release channel and archive contracts | [build-and-release-distribution](../03-runtime/build-and-release-distribution.md) | Release contract ZIP, missing embedded runtime, pending update, restart, preserving user data |
| DEPENDENCY-RESEARCH (без REQ-ID) | Не считать все imports из Python Core обязательными в Rust; оценивать реальные contracts/Core vs Python AI | [python-import-reachability](../04-dependencies/python-import-reachability.md) | Call-graph closure, native DLL inventory, licensing и external alternatives |

Исторические требования остаются в предыдущих разделах. Не перенимать случайный Python default или обнаруженный риск как обязательное пользовательское требование без решения владельца проекта.

### Дополнение: token pricing

| ID | Контракт | Доказательство | Приёмка |
|---|---|---|---|
| REQ-TOKEN-001—002 / REQ-PRICE-001—003 | Token estimate, model metadata, actual usage/currency, provenance и cache identity должны иметь различные контракты | [token budget and pricing](../01-functional/token-budget-and-pricing.md) | Same model on two hosts; user override; stale prices; image-only; switch character; absent cost не становится нулём |


## Новые прослеживаемые требования: файловая система и compatibility

| ID | Требование | Источники | Validation / неизвестное |
|---|---|---|---|
| REQ-PATH-001 | Settings, user packs, models, logs и AI environments различаются ownership, lifecycle и delete/recovery policy | CAP-PATH-001, filesystem-paths-and-native-loaders | clean install/update, backup and restore, external data roots |
| REQ-PATH-002 | Поддерживать перенос пользовательских Prompts и нормализацию alias `Prompts/` при настроенном внешнем каталоге | CAP-PATH-001, `app_paths.prompt_path` | тест legacy/current absolute/relative aliases |
| REQ-PATH-003 | Canonical checkpoints directory согласован между installer и AI worker, включая relative override | CAP-PATH-002, RAG helpers | запуск из независимого cwd и под embedded Python |
| REQ-PATH-004 | Загрузка native AI models диагностирует Unicode path limitations, а не сводит их к generic "model missing" | CAP-PATH-003, `native_paths.py` | non-ASCII home, 8.3 disabled, UNC/long-path fixtures |
| REQ-PATH-005 | Логи crash-prone AI subprocess и core имеют correlation, ограничение размера, явные гарантии flush | CAP-PATH-004, `main_logger.py` | normal shutdown vs CUDA `os._exit(70)` |

**HOI4:** `CAP-HOI4-EXPERIMENTAL-001—002` — **не** является подтверждённой обязательной функциональностью. До решения о поддержке standalone bridge отдельного `REQ-HOI4-*` не вводить: отсутствие active reachability не позволяет выдавать эксперимент за parity constraint. Сохранить discovery evidence в [HOI4](../01-functional/hoi4-standalone-prototype.md).


## HTTP transport / ошибок (новая область)

| ID | Требование | Источник | Validation |
|---|---|---|---|
| REQ-NET-001 | Явные owners HTTP pools/handles/streams; согласованная client config identity и безопасный close in flight | CAP-NETWORK-001 | Repeated-acquire-with-different-options, close while stream reading |
| REQ-NET-002 | Типизированная классификация сетевых отказов и безопасный error payload без утечки URL credentials | CAP-NETWORK-002 | DNS/TLS/status/timeout/error detail sanitization fixtures |
| REQ-NET-003 | Retry только при подтверждённой семантике конкретной операции, независимо от transport retryable flag | CAP-NETWORK-002, CAP-LLM-003 | Read timeout after server side effect, 429 Retry-After, cancelled POST |
| REQ-NET-004 | Разделять connect/write/read/pool/attempt timeout и turn cancellation, освобождать streaming responses | CAP-NETWORK-003 | Large payload, loopback vs remote, stream cancel & shutdown |

## Извлечённые контракты: settings, secrets, owned services, GUI

| Requirement | Функциональный смысл | Source / future validation |
|---|---|---|
| REQ-SET-001—002 | Отделить user preferences, distribution marker и protected account records; deterministic update-contour migration | [settings/migrations](../01-functional/settings-storage-and-migrations.md); initial/explicit/legacy marker fixtures |
| REQ-SET-003 | API preset identity/order/fallback/model-specific params сохраняются при импорте, миграциях и экспорте | [settings/migrations](../01-functional/settings-storage-and-migrations.md); import/export golden fixtures |
| REQ-SET-004—005 | Mutation revision, observer delivery и durable write — разные outcomes; nested settings updates наблюдаемы | [settings/observers](../03-runtime/typed-services-and-settings-observers.md); injection writer failure, mutated nested values |
| REQ-SET-006—007 | Strict per-dialect model schema и explicit secret export policy, masking ≠ encryption | [settings/migrations](../01-functional/settings-storage-and-migrations.md); schema downgrade, credentials export safety |
| REQ-SERVICE-001—002 | Поздний close owner не удаляет replacement service; explicit missing-service/readiness contracts | [typed services](../03-runtime/typed-services-and-settings-observers.md); owner replacement/load/unload |
| REQ-OBSERVER-001 | Subscription/replay/cleanup и revision-aware state, независимый GUI mirror | [typed services](../03-runtime/typed-services-and-settings-observers.md); stale queue/replay/Qt close |
| REQ-UISET-001—005 | 12 registered settings sections, visibility/deeplink, lazy readiness/error, typed binding и full key→consumer coverage | [settings GUI](../02-ui/settings-navigation-and-lazy-pages.md); per-page GUI behavioral tests |

Требования формулируют желаемые гарантии; обнаруженные незащищённые экспорты, гонки и отсутствие ACK **не** объявлены нормой новой реализации.

## Дополнительные требования из углублённого GUI / RAG / maintenance pass

Семейства `REQ-*` перечислены по range; точная формулировка требований, evidence и открытые вопросы — в каждом соответствующем документе.

| IDs | Функциональный контракт | Primary evidence | Предлагаемая валидация (НЕ выполнена) |
|---|---|---|---|
| `REQ-SET-KEY-001—003` | Key/consumer coverage, dynamic settings, side effects и неизвестная reachability | [key consumer matrix](../02-ui/settings-key-consumer-evidence.md) | All registered builders, change propagation, alias, dead control review |
| `REQ-GRAPH-MAINT-001—007` | Entity GC/merge/type/TTL/clear с явными partial outcomes, scoped identity и безопасным восстановлением | [graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md) | concurrent merge and GC, dedupe, cancellation, LLM retype, partial failure |
| `REQ-UI-GRAPH-001—004` | Visual graph state/actions с selection, filter, edit state и truthful cancel | [graph viewer](../02-ui/graph-viewer-interactions.md) | 1000+ entities, async close, graph sort, read-only vs mutating action |
| `REQ-UI-SANDBOX-001—005` | Sandbox UI/readiness/session/game request and setting projections | [sandbox](../02-ui/sandbox-page-functional-contract.md) | game request disable/re-enable, concurrent operations, switch character |
| `REQ-UI-CHAT-001—005` | Composer attachments/media bytes ownership, chat send/cancel and lease state | [composer](../02-ui/chat-composer-and-attachments.md) | deleted preview/temp cleanup, MIME, multi-batch attachment caps, ASR capture |
| `REQ-UI-CHAT-006—010` | Stable message identity, history+stream reconciliation, actions, finetune/context provenance | [chat presentation](../02-ui/chat-stream-history-and-message-actions.md) | 256+ pending, character switch, persisted ack, exact/fallback ctx, delete/regenerate |
| `REQ-UI-STRUCT-001—004` | Stable structured visibility modes, read-only rich result and typed handling | [structured presentation](../02-ui/structured-ai-results-presentation.md) | off mode with role=structured, malformed values, multi-target stream |
| `REQ-UI-GALLERY-001—004` | File collection/date sorting, stale-safe bounded thumbnails, viewer/OS open | [gallery](../02-ui/gallery-lifecycle-and-photo-viewer.md) | missing/corrupt photo, watcher/new folder, 160+ photos, concurrent navigation |
| `REQ-UI-CHAR-001—004` | Selected config vs active chat, one/all scope, truthful maintenance outcomes | [character UI](../02-ui/character-library-and-maintenance-actions.md) | active mismatch, failed purge partial, bulk index cancel, reload pending |

Не переносить выявленные неустойчивые поведения (Qt-only internals, локализованные control IDs, partial success as success) как обязательный баг-паритет. Архитектурные решения на Rust **не приняты**.

### Новости и логи: granular UX

`REQ-UI-NEWS-001—002` — source/repository generation fencing, release focus, Home projection, remote/cached state; `REQ-UI-LOGS-001—002` — bounded readable file-tail, active-only polling, log folder/diagnostics and transparent missing/error statuses. [Evidence](../02-ui/news-and-logs-live-ui-contracts.md). Приёмка: stale repo result, unknown release id, rotated/non-UTF8 file, long lines и navigation tab switch.

### Home launcher

`REQ-UI-HOME-001—004` — primary action priority, independent Python/Unity selected updates, tester-code admission, progress/cancel/restart and truthful **partially committed update** state; [Home source evidence](../02-ui/home-launcher-update-and-game-state.md). Required fixtures: Python applied + Unity failed/cancelled; restart declined; Unity running while Python pending restart; user selects stale update after contour switch.

### Wiki navigation and Unicode headings

`REQ-UI-WIKI-001—003` — localized local Markdown, strict path-scheme separation, app deep links, history/reload/language navigation, stable Unicode heading anchors; `REQ-UI-GUIDE-001` — GuideDialog→Wiki lifetime and full GuideWidget validation backlog. [Evidence](../02-ui/wiki-navigation-localization-and-anchors.md). Приёмка: mixed RU/EN headings, duplicates, failed fallback, app link, traversal, guide window close/reopen.

### Guide Walkthrough: `REQ-UI-GUIDE-002—006`

Сохранить динамическую фильтрацию 13 зарегистрированных tutorial pages на уровни 3/5/13, пользовательский `GUIDE_LEVEL`, RU/EN, переходы между разделами и step-to-image focus/zoom, отсутствие изображения с текстовым fallback и переход в локальную Wiki. Контракт и проверки: [Guide Walkthrough](../02-ui/guide-walkthrough-and-image-focus.md).

### Dialog Lifecycle: `REQ-UI-DIALOG-001—005`

Сохранить независимое скрытие/отмену/закрытие фоновой задачи; Apply/Cancel с working копией pipeline и callback, reloaded singleton; раздельные data-export форматы, подтверждение и ошибки. Подробные source-backed контракты и будущие тесты: [UI dialogs](../02-ui/dialog-interaction-and-background-task-contracts.md).

## Дополнение: граф, история, memory ID, formula, Telegram, installable catalogue

| IDs | Requirement | Primary evidence | Доказательства / приёмка |
|---|---|---|---|
| `REQ-GRAPH-LEDGER-001—005` | Корректный processed-message ledger, обработка failed extraction, clear/rebuild и fence stale writers | [Graph extraction](../01-functional/graph-extraction-ledger-and-clear-consistency.md) | GUI clear оставил ledger в SQLite (reproduced); require retry and rebuild fixtures |
| `REQ-RESET-001—005` | Epoch-aware reset, explicit partial/atomic outcome всех stores, stale work handling | [History reset](../01-functional/character-reset-epoch-and-storage-consistency.md) | 23 history tests OK; cross-store race/rollback NOT tested |
| `REQ-MEM-ID-001—004` | Identity memory vs SQLite row ID, consistent derived-record lifecycle / purge / reindex | [Memory purge regression](../01-functional/memory-purge-embedding-identity-regression.md) | Real purge orphan + stale join reproduced; 18 other memory tests OK |
| `REQ-CHAR-CUSTOM-001—004` | Custom field schema, formula whitelist, deterministic bounds and read/write semantics | [Character custom fields](../01-functional/character-custom-fields-and-formula-policy.md) | 17 safe-eval/stats tests OK; Qt tests unavailable |
| `REQ-AI-BOUNDARY-001—004` | Self-contained Python AI worker dependencies, stable host boundary, no inference rewrite | [Worker import](../04-dependencies/ai-worker-python-core-import-boundaries.md) | Import-closure static evidence; standalone worker launch NOT tested |
| `REQ-UI-TG-001—004` | Challenge correlator, code/2FA cancellation, timeout UI outcome and secure input | [Telegram modal](../02-ui/telegram-auth-modal-contracts.md) | Qt/real Telegram login NOT tested |
| `REQ-INSTALL-CATALOG-001—004` | Catalog/implementation/installed/ready separation, stale load/cache recovery, custom IDs | [Lazy installable catalog](../01-functional/installable-catalog-lazy-registry-and-status.md) | Source-backed states; dynamic failure/recovery NOT tested |

Таблица содержит как подтверждённые текущее поведение и регрессионные примеры, так и **целевые инварианты**; их нельзя принимать за уже исполняемые гарантии старого Python Core.

## Функциональная спецификация: мир, контекст персонажей и групповая беседа

| ID | Необходимая возможность, независимо от Python-реализации | Доказательство | Parity / acceptance fixture |
|---|---|---|---|
| `REQ-WORLD-001` | Относить один `world_id` к конкретному character: owner/former owner/visitor или индивидуальный context | [World relations](../01-functional/character-world-and-environment-awareness.md) | 7 поставляемых world IDs, known aliases, кастомный мир, unknown world |
| `REQ-WORLD-002` | Формировать персональный transient lore для отдельного LLM turn без изменения global shared game state | [World relations](../01-functional/character-world-and-environment-awareness.md) | Две параллельные генерации разных персонажей в одном доме |
| `REQ-WORLD-STATE-001` | Различать last-known character-local Unity state и transient events/TV observation одного turn | [Unity world context](../03-runtime/unity-world-state-prompt-projections.md) | Частичные обновления, новая сцена, отсутствие повторного проигрывания старых событий |
| `REQ-WORLD-STATE-002` | Передавать стабильные каналы/интенты/catalog отдельно от динамической доступности, мирового состояния и пассивных общих фактов | [Unity world context](../03-runtime/unity-world-state-prompt-projections.md) | Connected/offline, action catalog известен, но capability unavailable, disabled intents |
| `REQ-WORLD-STATE-003` | Сохранять происхождение game data и control instructions, маркировать world events как данные, а не команды | [Unity world context](../03-runtime/unity-world-state-prompt-projections.md) | Злоупотребление reserved tags в world text, GM directive, shared mini-game read-only |
| `REQ-ENV-001` | Снабжать персонажа актуальным состоянием Unity install/connect, voice method/ready и app update, не путая configured и available | [Environment awareness](../01-functional/character-world-and-environment-awareness.md) | Desktop with Unity absent/present/connected; local/API/Telegram TTS states |
| `REQ-ENV-002` | Различать player-authored `APPLICATION/GAME/NONE` и сигнализировать о смене достоверного transport в том же диалоге | [Message source](../01-functional/character-world-and-environment-awareness.md) | app→game→app, unknown source, connected game without player transport |
| `REQ-GM-001` | Поддерживать скрытый director request от Unity с наблюдением/командой, policy, task result и typed actionable intent | [GameMaster](../01-functional/game-master-scene-direction.md) | command/observe, empty command, structured effects with no visible text |
| `REQ-GM-002` | Доставлять адресованную директиву GM как специальный контекст будущего ответа персонажа, не превращая GM в NPC очередь | [GameMaster](../01-functional/game-master-scene-direction.md) | GM intent→Unity event→ следующая реплика, optional GM voice |
| `REQ-DIALOGUE-VIEW-001` | Хранить раздельно identities conversation/epoch/turn, actor instance, character identity и participant capabilities | [Conversation session](../03-runtime/conversation-session-projections.md) | Два actor одного персонажа, disconnection, new epoch, missing actor |
| `REQ-DIALOGUE-VIEW-002` | Показывать read-only snapshot активной группы в GUI, отдельно от истории и авторитета Unity scheduler | [Conversation projection](../03-runtime/conversation-session-projections.md) | 1/2/3/4 participants, user selection mismatch, disconnect reset |

Новый experimental GameMaster rule engine, `GameMasterScheduler` и `DialogueTranscriptService` **не включены как обязательные требования паритета** без evidence production use. Выбор модели будущего director, если она потребуется, производится в последующей отдельной архитектурной фазе.

## Продолжение functional audit 2026-10-31 — новые проверяемые семейства требований

Это **возможности продукта**, которые новая реализация обязана сохранить при подтверждённом ACTIVE/CONDITIONAL статусе; описывается поведение, не структура классов и не выбор Rust crates.

| Семейство ID | Требование / граница | Источник |
|---|---|---|
| `REQ-CHAR-EFFECTS-01—06` | Разделять model-output intents, проверку допустимости, подтверждение локальных effects и исход внешних Unity действий | [Character effects](../01-functional/structured-character-actions-and-side-effects.md) |
| `REQ-INSTALL-CARDS-01—03` | Различать каталог и фабрику устанавливаемых компонентов, installed/ready/loaded и error/recovery | [Installables](../01-functional/installable-catalog-and-runtime-readiness-matrix.md) |
| `REQ-VOICE-REMOTE-01—03` | Хранить и выбирать независимые remote voice credentials/presets и назначение конкретному персонажу | [Remote voice](../01-functional/remote-voice-presets-and-character-routing.md) |
| `REQ-UI-ASR-01—04` | Каталог пяти ASR моделей, готовность, установка, настройки и UX включения распознавания | [ASR settings](../02-ui/asr-model-gallery-and-settings-workflows.md) |
| `REQ-UI-VOICE-LOCAL-01—04` | Поддерживать user journeys локальных TTS/VC моделей, управление голосами и compilation dialogs | [Local voice UI](../02-ui/local-voice-model-management-and-compile-dialogs.md) |
| `REQ-UI-API-01—05` | CRUD API presets и schema-driven редактор параметров моделей с сохранением, отменой и валидацией | [API presets](../02-ui/api-presets-and-model-parameter-editor-workflows.md) |
| `REQ-UI-RAG-01—04` | Обособить пользовательскую настройку pipeline, embedding provider, installation и loaded runtime state | [RAG UI](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md) |
| `REQ-UI-CTX-01—03` | Просмотр/поиск/копирование полного контекста LLM с отличием missing/fallback samples и estimated/actual usage | [Context viewer](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `REQ-UI-DB-01—03` | Scope-aware viewer истории/памяти/переменных/изображений/графа, edit/batch/delete и ручные описания | [DB viewer](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `REQ-DATA-FT-01—05` | Сбор полного запроса/ответа, рейтинг UUID, retention, фильтрация и Raw/ShareGPT экспорт | [FineTune data](../01-functional/fine-tuning-data-capture-curation-and-export.md) |
| `REQ-AI-HW-01—02`, `REQ-AI-ADMIN-01—02` | Windows GPU/CUDA identity discovery, `shared/split` topology operations, maintenance lifecycle, раздельные статусы | [Hardware and AI admin](../01-functional/hardware-acceleration-and-ai-engine-administration.md) |
| `REQ-LING-01—03` | Русская keyword/FTS морфология и многоязычная числовая нормализация TTS до inference | [Linguistics](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md) |
| `REQ-DEPS-DYNAMIC-01—03` | Сохранять optional capability discovery и границу core/worker, не трактовать инсталлятор как активный сервис | [Loaders](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md) |

`REQ`-семейства добавлены в [traceability](feature-traceability.md) с условиями приемки. Раздельный AI Engine и полный функциональный паритет сохраняются; GUI framework сравнивается позже, окончательная Rust architecture не проектировалась.

## Дополнение: каталог персонажей и доказательная граница зависимостей

| ID | Functional requirement | Source |
|---|---|---|
| `REQ-CHAR-CATALOG-01` | Каталог из 9 действующих IDs с раздельным хранением id, display/storage, voice short name, локализации; GameMaster не обычный NPC | [Character catalogue](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `REQ-CHAR-CATALOG-02` | Загрузка персонажа по запросу, initial fallback, persisted state overrides, чтение статистики без eager runtime | [Character lifecycle](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `REQ-CHAR-CATALOG-03` | Переключение/reload/prompts и history clear, включая неактивных персонажей, с observable outcome | [Character commands](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `REQ-CHAR-CATALOG-04` | Специальные typed effects доступны только поддерживающим их персонажам, GUI-only режим не притворяется запущенной model session | [Special actors](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| `REQ-DEPS-REQUIREMENTS-01` | При выборе Rust implementation разделять функциональную зависимость от Python distribution/transitive/native artifacts/AI worker dependency; сохранять `UNRESOLVED` до доказательства | [Full requirements](../04-dependencies/full-requirements-runtime-evidence-ledger.md) |


## Дополнительные функциональные требования (source-backed continuation)

| Requirement IDs | Функциональный контракт | Документ |
|---|---|---|
| `REQ-RAG-INDEX-001—003` | Разные корпусы и identity (`history.id`, `memory.eternal_id`); vector/FTS/keyword/sentence; missing vs all index, progress/cancel | [RAG](../01-functional/rag-storage-retrieval-and-indexing-modes.md) |
| `REQ-INST-PROBE-001—006` | Installable status по backend/model/weights, конкретные install/update/clean/uninstall/repair plans, probe vs execution | [Installables](../01-functional/installable-component-probe-and-operation-contracts.md) |
| `REQ-AI-MODEL-001—005` | ASR engines и TTS variants доступны через managed Python AI и отдельные model artifacts; выбор/установка/init/synthesis не слиты | [ASR/TTS](../01-functional/asr-tts-managed-backend-operational-contracts.md) |
| `REQ-UI-MODEL-001—003`, `REQ-UI-VOICE-001`, `REQ-UI-DEPS-001`, `REQ-UI-REACH-001` | Test connection, selection/list metadata и modal states; lazy voice progress/cancel; requirement only when reachable | [API and dialogs](../02-ui/api-model-discovery-and-conditional-dialogs.md) |
| `REQ-GAME-UI-001—002`, `REQ-BEAT-UI-001` | Выбор владельца игры Sandbox/Unity, gating кнопок; Beat backend/cache actions/status | [Games](../02-ui/game-settings-manual-launch-and-beat-cache.md) |
| `REQ-IMAGE-UI-001—005` | Independent screen/webcam/Unity camera capture, description provenance, image storage and cleanup, camera event→dialogue | [Screen/images](../02-ui/screen-camera-image-management-user-contracts.md) |

## Дополнение: внешние интеграции

| Requirement ID | Contract | Source |
|---|---|---|
| `REQ-EXT-ROUTE-001—003` | Различать registered/optional/standalone; отдельно Telegram/LLM tools/remote voice и authentication/provenance/correlation | [External entrypoints](../01-functional/external-integration-entrypoints-and-reachability.md) |


## Дополнение: RAG query и ranking

| Requirement IDs | Functional contract | Source |
|---|---|---|
| `REQ-RAG-RANK-001—004` | Auto vs tool; query actor context, source-qualified dedup; fusion modes and optional CE; graph quota, public meta/access metrics | [RAG ranking](../01-functional/rag-query-fusion-reranking-and-result-contracts.md) |


## Дополнение: RAG → LLM Prompt

| Requirement IDs | Contract | Evidence |
|---|---|---|
| `REQ-RAG-PROMPT-001—004` | Реакционный gate, explicit vs auto, source-aware rendering/clipping, distinct Unity dynamic context and empty-result behavior | [RAG prompt](../01-functional/rag-context-injection-and-source-rendering.md) |

### Локальный внешний IPC control-plane

- `REQ-LOCAL-IPC-001`: включение/выключение и смена TCP loopback listener через настройки, отдельно от lifecycle Core и AI worker.
- `REQ-LOCAL-IPC-002`: явно allowlisted discoverable commands, JSON request/response correlation и typed errors; не произвольный доступ к Core объектам.
- `REQ-LOCAL-IPC-003`: hardware inventory, AI topology и AI service restart предоставляются как отдельные admin capabilities, без смешения readiness listener/worker/model. [Evidence](../01-functional/local-runtime-ipc-external-control-contract.md).

### GUI первый запуск и согласие

- `REQ-UI-ONBOARD-001`: явный first-run consent gate и outcome accepted/rejected с persisted state; не трактовать GUI overlay как гарантированную блокировку headless Core.
- `REQ-UI-ONBOARD-002`: пользовательский выбор языка до согласия, текст EULA по отдельному языковому corpus с определённым fallback и обработка несовпадения с уже созданным GUI.
- `REQ-UI-ONBOARD-003`: после согласия переход в Guide и Wiki; повторный запуск с сохранённым consent не должен навязывать first-run путь. [Evidence](../02-ui/first-run-agreement-language-and-guide-flow.md).

### Нативные Windows возможности и граница Python AI

- `REQ-NATIVE-001`: GPU inventory отдельно от inference: DXGI physical device identity, optional CUDA driver assignment и absence states.
- `REQ-NATIVE-002`: устойчивый audio endpoint identity, hotplug/PortAudio readiness отдельно от ASR model installation.
- `REQ-NATIVE-003`: Unity update process guard привязан к точному executable и реальному завершению процесса, не только к факту закрытия окна.
- `REQ-NATIVE-004`: Windows credential security и OS permissions сохраняются как Core capabilities; внешние inference DLL/packages не являются Python зависимостями нового Rust Core. [Source evidence](../04-dependencies/native-system-api-and-ai-library-ownership.md).


## Дополнение: проверяемые требования нового functional pass

| Requirement IDs | Смысл | Source-backed спецификация | Будущие parity acceptance conditions |
|---|---|---|---|
| `REQ-INSTALL-ID-001—004` | Идентичность и тип ресурсов AI Hub; fixed 31 + dynamic RAG | [Catalog identity](../01-functional/installable-catalog-identity-and-coverage.md) | Full ID fixture, RU/EN metadata, custom/aggregate lookup, engine vs asset |
| `REQ-INSTALL-OBS-001—004` | Context/revision based readiness observation и late event | [Status observation](../03-runtime/installable-status-observation-and-invalidation.md) | pending vs not-ready, invalidate, changed ASR settings/voice language, late resolution |
| `REQ-INSTALL-QUEUE-001—005` | Admission/duplicate/FIFO/quiesce/cancel/completion/status recheck | [Install queue](../03-runtime/install-operation-admission-queue-and-completion.md) | two jobs serial, duplicate task, cancel queued/running, install/clean/remove/init, verify readiness |
| `REQ-UI-AIHUB-ACTIONS-001—004` | UI actions и состояние dirty form/progress/status | [Action ledger](../02-ui/ai-hub-interaction-traceability-checklist.md) | first open, category/filter, install/preflight, dirty guard, logs, partial refresh |
| `REQ-UI-STATUS-001—004` | Чат thinking/tool/compression/error/voicing и read-only chips | [Status UI](../02-ui/generation-progress-error-and-voice-indicators.md) | concurrent generation, background completion, per-message marker/error, stale event |

## Дополнение: функциональная семантика и проверяемые требования (UTC 30-minute continuation)

Приведённые требования возникают **из подтверждённых возможностей**, но не утверждают целевую Rust-схему/классы. Source evidence см. в каждой связанной спецификации.

- **REQ-CONTENT-001** — одно сообщение имеет multimodal representation и раздельные, согласованные projections: provider payload, history persistence, summary text, embedding text, UI. Неизвестные typed parts не должны исчезать без объявленной политики. [Источник](../01-functional/multimodal-message-content-representations.md).
- **REQ-TV-001** — телевизионный ролик с кадрами/субтитрами имеет отдельную provenance, отличается от речи игрока и действий игрового персонажа; event без пользовательского текста должен допускаться. [Источник](../01-functional/tv-observation-youtube-frame-and-dialogue-provenance.md).
- **REQ-WORLD-EXPORT-001** — пользователь выбирает character scope, категории, статусы, период и фильтры, получает переносимый экспорт исходных данных; embeddings остаются derivations с отдельным восстановлением. [Источник](../01-functional/world-db-json-export-import-user-workflow.md).
- **REQ-EMBED-WIRE-001** — разные providers могут иметь отдельный query/document mode, очередь/batch и форматы ответа, при этом core потребляет понятный результат/ошибку и стабильную связь vector с source identity. [Источник](../01-functional/embedding-provider-wire-and-failure-contracts.md).
- **REQ-TELEGRAM-DELIVERY-001** — auth/2FA, инициирование голоса, ожидание remote ответа и доставка audio в Unity/desktop — самостоятельные видимые стадии с cancellation/failure. [Источник](../01-functional/telegram-bot-protocol-routing-and-session-semantics.md).
- **REQ-INSTALL-OPS-001** — каждая карточка installable имеет подтверждённый family operation policy; не сводить `status/install/uninstall/initialize` в один «установлено» flag. [Источник](../01-functional/installable-families-runtime-operations.md).
- **REQ-UI-KEYBOARD-001** — сообщения, вложения, просмотрщики, редакторы и поиск должны сохранить реально доступные keyboard/clipboard/direct manipulation user actions, независимо от выбора GUI-фреймворка. [Источник](../02-ui/keyboard-clipboard-and-direct-manipulation-contracts.md).
- **REQ-UI-DEVICE-001** — доступность параметра голосовой модели зависит от выбранного фактического GPU/backend и должна отражаться как в GUI, так и при применении конфигурации. [Источник](../02-ui/voice-controls.md).
- **REQ-RUNTIME-TRACE-001** — пользовательский запрос должен иметь различимые состояния очереди, provider event/text, context/structured, ASR/TTS и delivery/playback; диагностика времён не должна раскрывать prompts и secrets. [Источник](../03-runtime/per-request-performance-traces-and-diagnostic-metrics.md).
- **REQ-TEST-PARITY-001** — проверка новой версии основывается на observable functionality и fixtures, с отдельными offline и external E2E уровнями. Старые Python тесты — источники сценариев, не обязательные зависимости Rust runtime. [Источник](existing-test-corpus-and-functional-parity-gates.md).


- **REQ-DIALOGUE-IDENTITY-001** — отдельные conversation/session, character, actor, speaker, sender, target, turn и message identifiers, с однозначным actor-to-character resolution и происхождением ответа. [Source](../01-functional/dialogue-actor-and-message-identity-contracts.md).
- **REQ-DIALOGUE-IDENTITY-002** — разрешение имя/actor/character target допустимо только при однозначном совпадении; uncertain sender должен сохранять различие между authoritative и declared identity. [Source](../01-functional/dialogue-actor-and-message-identity-contracts.md).


- **REQ-STREAM-001** — запрос имеет один start, упорядоченные content/reasoning/tool/usage events, отдельные terminal completed/failed; UI обязан отделять видимый текст от reasoning, не смешивать роли и не пропускать tail при штатном close. [Source](../03-runtime/llm-stream-event-and-presentation-lifecycle.md).


## Pass 11 — требования из дополнительных первичных контрактов
- **`REQ-DSL-EXEC-001`** — набор prompt-pack ресурсов выбирается по персонажу, сценарию и типу события; вложенные ссылки разрешаются относительно однозначного корня. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-002`** — логика условий, вычислений и подстановок предоставляет персонажу актуальные переменные без исполнения произвольного системного кода. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-003`** — различаются persistent character fields, локальные скриптовые значения и transient prompt features. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-004`** — static, volatile и отдельные dynamically generated sections сохраняют ordering/provenance перед LLM-запросом. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-005`** — функция инициализации memory/RAG/islands/graph из prompt pack сохраняет смысл side effects и их условия доступности, независимо от выбранного DSL. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-006`** — неразрешённый путь/ошибка выражения не должны выдавать непроверенный текст за корректную инструкцию; точное UX-поведение выбирается при проектировании. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-DSL-EXEC-007`** — сериализованный prompt-build со всеми side effects проверяется на повторяемость, независимость персонажей и смену настроек. [Привязка к исходникам](../01-functional/dsl-executable-prompt-contract.md).
- **`REQ-POSTDSL-001`** — трансформация текста выполняется в объявленном порядке и не теряет незатронутые фрагменты. [Привязка к исходникам](../01-functional/post-dsl-response-rules-and-debug-state.md).
- **`REQ-POSTDSL-002`** — совпадения и structured fields могут детерминированно обновлять параметры заданного персонажа; именованные captures доступны последующим действиям. [Привязка к исходникам](../01-functional/post-dsl-response-rules-and-debug-state.md).
- **`REQ-POSTDSL-003`** — расширяемый список debug-переменных не зависит от структуры GUI и имеет default при отсутствии файла конфигурации. [Привязка к исходникам](../01-functional/post-dsl-response-rules-and-debug-state.md).
- **`REQ-POSTDSL-004`** — text transformation и field effects различаются по времени выполнения относительно built-in effects. [Привязка к исходникам](../01-functional/post-dsl-response-rules-and-debug-state.md).
- **`REQ-MINIGAME-DETAIL-001`** — два отдельные gameplay rule sets — Chess и Sea Battle — с валидными ходами, фазами и итогом. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-002`** — пользовательские запросы, LLM-команды и игровые события имеют общий scope персонажа, но различные initiating actors. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-003`** — LLM получает роль-ограниченную, согласованную с игрой проекцию, включая «state not ready» и ошибки. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-004`** — доступность игр определяется настройками и текущим режимом работы с Unity. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-005`** — lifecycle игры и исходящие реакции не оставляют публичный session snapshot после остановки. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-006`** — включение автоматических реакций контролируется игроком и общими policy gates; автоматическая реакция — отдельное admission-событие. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-007`** — шахматный движок и его weights являются optional компонентами, а не обязательным Python AI runtime Core. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-MINIGAME-DETAIL-008`** — сохранена семантика недоступного/запаздывающего state после process start, без приписывания действиям гарантии выполнения. [Привязка к исходникам](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- **`REQ-ACTION-HISTORY-001`** — исходный structured ответ хранится отдельно от производной текстовой проекции LLM. [Привязка к исходникам](../01-functional/structured-action-history-and-compression-bridge.md).
- **`REQ-ACTION-HISTORY-002`** — действия associate-ятся с конкретным assistant turn, имеют chronological ordering и не выдаются за подтверждённый Unity effect. [Привязка к исходникам](../01-functional/structured-action-history-and-compression-bridge.md).
- **`REQ-ACTION-HISTORY-003`** — successful summary переносит только соответствующие requested actions через границу live/summary, не теряя scope персонажа. [Привязка к исходникам](../01-functional/structured-action-history-and-compression-bridge.md).
- **`REQ-ACTION-HISTORY-004`** — bounded context сохраняет последние значимые действия при переполнении, а не произвольный набор. [Привязка к исходникам](../01-functional/structured-action-history-and-compression-bridge.md).
- **`REQ-CORE-TRIGGER-001`** — система поддерживает точные условия активации независимо от вероятностного retrieval и включает их результат в текущий prompt с однозначным provenance. [Привязка к исходникам](../01-functional/exact-core-memory-triggers-and-session-activation.md).
- **`REQ-CORE-TRIGGER-002`** — кратковременное/закреплённое состояние принадлежит конкретному персонажу и сбрасывается при очистке сессии. [Привязка к исходникам](../01-functional/exact-core-memory-triggers-and-session-activation.md).
- **`REQ-CORE-TRIGGER-003`** — художественные сюжетные флаги не дают доступа к системным возможностям, credentials или privileged commands. [Привязка к исходникам](../01-functional/exact-core-memory-triggers-and-session-activation.md).
- **`REQ-MIC-001`** — catalog and compatibility derived from actual capture support, do not equate one PortAudio index with one physical device. [Привязка к исходникам](../01-functional/microphone-physical-identity-backends-and-monitoring.md).
- **`REQ-MIC-002`** — persistent identity where available; express unavailable vs ambiguous instead of silent switch. [Привязка к исходникам](../01-functional/microphone-physical-identity-backends-and-monitoring.md).
- **`REQ-MIC-003`** — monitoring has independent start/stop/error/session lifecycle; no hidden ASR/model requirement. [Привязка к исходникам](../01-functional/microphone-physical-identity-backends-and-monitoring.md).
- **`REQ-MIC-004`** — compatible backend selection must be explicit and deterministic; unsupported selection must be observable. [Привязка к исходникам](../01-functional/microphone-physical-identity-backends-and-monitoring.md).
- **`REQ-SPEECH-ARBITER-001`** — admission derives from actual concurrent playback sources and user option, not just presence of a generated audio file. [Привязка к исходникам](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
- **`REQ-SPEECH-ARBITER-002`** — retiring one utterance/client must not end another active speaking lease; stale disconnected-client events must not lock microphone. [Привязка к исходникам](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
- **`REQ-SPEECH-ARBITER-003`** — the game receives a reasoned acknowledgement whenever an input command is rejected or invalidated. [Привязка к исходникам](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
- **`REQ-SPEECH-ARBITER-004`** — bound an orphaned speaking lease and retain a short tail so ASR does not wake during playback decay. [Привязка к исходникам](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
- **`REQ-EVENT-ROUTE-001`** — parity cases must distinguish command acceptance, execution and resulting fact. [Привязка к исходникам](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md).
- **`REQ-EVENT-ROUTE-002`** — related events remain correctly ordered within a stream/capture/task; unrelated operations may progress independently. [Привязка к исходникам](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md).
- **`REQ-EVENT-ROUTE-003`** — GUI-only must not silently advertise full LLM/AI functionality. [Привязка к исходникам](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md).
- **`REQ-EVENT-ROUTE-004`** — downstream effects run only when their enabling conditions are satisfied, and failures do not retroactively imply that an assistant response was never persisted. [Привязка к исходникам](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md).
- **`REQ-UNITY-INGRESS-001`** — player input belongs only to an eligible game actor/session; reconnect revokes stale identity. [Привязка к исходникам](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- **`REQ-UNITY-INGRESS-002`** — separate requested generation from task status/progress and actual executed game commands; preserve request/message correlation. [Привязка к исходникам](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- **`REQ-UNITY-INGRESS-003`** — expose only relevant normalized game settings, with an observable revision/lifecycle. [Привязка к исходникам](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- **`REQ-UNITY-INGRESS-004`** — both result shapes, progress/chunks/error, same request identity and no unapproved model installation. [Привязка к исходникам](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- **`REQ-UNITY-INGRESS-005`** — speech playback leases and capture commands remain independent and ownership-aware. [Привязка к исходникам](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- **`REQ-GUI-ASYNC-001`** — смена выбора/параметров должна исключать публикацию результата устаревшего запроса на текущем экране. [Привязка к исходникам](../02-ui/intent-workloads-and-visible-state-consistency.md).
- **`REQ-GUI-ASYNC-002`** — повторная эксклюзивная команда для одного ресурса/операции не должна создавать дублирующиеся concurrent side effects. [Привязка к исходникам](../02-ui/intent-workloads-and-visible-state-consistency.md).
- **`REQ-GUI-ASYNC-003`** — серия одинаковых refresh triggers должна в итоге предоставить последнее актуальное состояние, не умножая полную работу на число сигналов. [Привязка к исходникам](../02-ui/intent-workloads-and-visible-state-consistency.md).
- **`REQ-GUI-ASYNC-004`** — закрытие/удаление экрана прекращает его подписки и публикацию результатов; длительная работа не блокирует UI. [Привязка к исходникам](../02-ui/intent-workloads-and-visible-state-consistency.md).
- **`REQ-GUI-ASYNC-005`** — промежуточные UI states (`loading`, `preparing`, `queued`, `running`, `ready`, `error`) не должны сливаться в один булев `busy`; набор состояний зависит от функции. [Привязка к исходникам](../02-ui/intent-workloads-and-visible-state-consistency.md).

### Pass 11 — режим Core без GUI

- **`REQ-HEADLESS-SURFACE-001`** — Core и игровое взаимодействие доступны без графического runtime; наличие/отсутствие GUI не должно скрывать обязательную готовность backend. [Источники](../03-runtime/headless-core-functional-surface-and-readiness.md).
- **`REQ-HEADLESS-SURFACE-002`** — отдельный TCP listener, AI workers и готовность services различаются в статусе, ошибках и health. [Источники](../03-runtime/headless-core-functional-surface-and-readiness.md).
- **`REQ-HEADLESS-SURFACE-003`** — shutdown координирует Core/AI/network lifecycle и возвращает наблюдаемый процессный результат. [Источники](../03-runtime/headless-core-functional-surface-and-readiness.md).
- **`REQ-HEADLESS-SURFACE-004`** — операции с интерактивными подтверждениями и аутентификацией в отсутствии GUI явно сообщают о недоступности либо применяют проверенный независимый канал; не следует молча ожидать окно. [Источники](../03-runtime/headless-core-functional-surface-and-readiness.md).
- **`REQ-HEADLESS-SURFACE-005`** — временной запуск и периодические snapshots отсчитываются на monotonic clock и отделены от таймеров беседы. [Источники](../03-runtime/headless-core-functional-surface-and-readiness.md).

- **`REQ-INSTALL-FIXTURE-001`** — каждый статически зарегистрированный компонент имеет собственную identity, применимые операции, наблюдаемые состояния готовности, resource owner и проверку фактической consumer activation (когда применимо). Dynamic RAG модели — тот же контракт без фиксированного количества карточек. [Матрица проверки](installables-component-by-component-parity-matrix.md).

### Pass 12 — новые подтверждённые пользовательские и системные контракты

- `REQ-UI-DIALOG-001—003`: реестр modal/modeless окон, повторный показ singleton и скрытие windows не равнозначны результату операции; `protocol_pipeline` реализуется через `MessageProcessingDialog`, а не класс с созвучным именем. [Источник](../02-ui/dialog-class-reachability-and-action-outcomes.md).
- `REQ-RAW-EVT-001—004`: начальная и дополнительная страницы history различаются, raw-string events должны иметь correlation/source и независимый Qt consumer; periodic screen trigger отдельно от ручного attach. [Источник](../00-research/raw-string-event-reachability-and-ui-bridges.md).
- `REQ-GRAPH-INGEST-001—004`: inline/legacy/realtime/manual extraction, source-provenance/history-memory tagging, batch only-new/redo и различение persisted graph от RAG-visible graph. [Источник](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md).
- `REQ-NATIVE-DIALOG-001—004`: один/много файлов, папка, output path, отмена и независимое завершение; scopes selected/all и Sandbox/Unity character selection. [Источник](../02-ui/native-dialogs-and-file-input-output-workflows.md).
- `REQ-UI-CONFIRM-001—004`: user consent перед удалением/перезаписью; несколько outcomes для dirty preset, legacy restore и отсутствующих RAG моделей; Yes является admission, не successful completion. [Источник](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md).
- `REQ-RAG-PRESET-001—004`: четыре встроенных RAG preset, user snapshots, Save current & Apply и отдельное предложение загрузить отсутствующие модели; `Custom` не сохраняемый встроенный preset. [Источник](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md).
- `REQ-SET-RAG-001—003`: идентичность 99 зарегистрированных RAG/Memory settings keys, реальные consumer-readers, defaults и side-effects должны проверяться отдельно. [Источник](../00-research/rag-settings-direct-consumer-evidence-index.md).
- `REQ-UI-SIGNAL-001—003`: зарегистрированный signal callback не равен подтверждённому функциональному intent; отдельно фоновые timers, settings UI preferences и user commands. [Источник](../00-research/gui-signal-registration-callsite-index.md).
- `REQ-EXE-001—004`: вызов FFmpeg/7z, managed subprocess, Windows native DLL и AI-only dependency не должны сливаться в один тип ресурсной зависимости. [Источник](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md).

### Pass 12 — RAG ready/runtime generation

- `REQ-RAG-READY-001`: независимо наблюдать enabled/installed/ready.
- `REQ-RAG-READY-002`: агрегировать readiness только по required targets текущих настроек.
- `REQ-RAG-READY-003`: не принимать устаревшие результаты другого runtime generation.
- `REQ-RAG-READY-004`: смена модели/worker должна вести к повторной проверке готовности.

Источник: [RAG readiness and worker generation](../01-functional/rag-model-runtime-readiness-and-worker-generation.md).

### Pass 12 — deterministic RAG result surface

- `REQ-RAG-GOLDEN-001`: сохранить source identity и метаданные результатов, не смешивать одинаковые ID разных источников.
- `REQ-RAG-GOLDEN-002`: валидировать формат и размерность векторов.
- `REQ-RAG-GOLDEN-003`: фиксировать return shape, provenance и детерминированный порядок на offline fixtures, не копируя ML-эвристику.

Источник: [RAG deterministic surface](../01-functional/rag-deterministic-golden-surface-and-result-types.md).

### Pass 12 — history UI projection and paging

- `REQ-HISTORY-VIEW-001`: persisted role, speaker/sender/target и UI presentation role не смешивать.
- `REQ-HISTORY-VIEW-002`: сохранять character identity, request correlation и raw offset при paging.
- `REQ-HISTORY-VIEW-003`: сохранять типизированную семантику TV observation и legacy user.

Источник: [history UI](../01-functional/history-ui-projection-actor-identity-and-paging.md).

### Pass 12 — dynamic registries and conditional backend capabilities

- `REQ-DYNIMPORT-001`: каталог ID, доступность, UI choice и failure наблюдаются отдельно от загрузчика.
- `REQ-DYNIMPORT-002`: dependency audit покрывает dynamic import, subprocess probes, native/installer-owned dependencies.
- `REQ-DYNIMPORT-003`: failure optional capability не должен выдавать все независимые capabilities недоступными.
- `REQ-DYNIMPORT-004`: различать registry/factory/instance/user action.

Источник: [динамические реестры](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md).
