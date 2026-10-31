# Прогресс-бар функционального аудита — фиксированные области покрытия

**Дата актуального среза:** 2026-10-31, Pass 13; [сводный каталог и конкретные оставшиеся gates](current-functional-baseline.md). Старые 30-minute записи ниже исторические. Это **контрольный список первичных runtime-контрактов, не оценка общего процента завершённости**. Единица — область, а не число файлов. Значение `PRIMARY` означает, что ключевой runtime path исследован и описан, **не** что домен полностью закрыт по тестам/GUI/интеграциям. `PARTIAL` означает, что выявлены незавершённые paths. `UNRESOLVED` требует базового source discovery.

## Pass 13: что изменилось в остатках

Счёт **13 PRIMARY / 7 PARTIAL** сохранён; исходные exit criteria не понижаются. Новые source evidence закрывают отдельные вопросы, а не physical/runtime gates целиком:

| Область | Новый результат | Остаётся |
|---|---|---|
| 05 History / 18 exchange | [Final history receiver/fencing](../02-ui/history-page-fencing-and-live-replay.md), [DB export/import fixture](../01-functional/world-db-exchange-isolated-validation.md) | Qt+DB late older pages, реальный legacy/multimodal recovery, concurrent cross-store mutations |
| 06 RAG/Graph | [Mixed-model repositories/provenance](../01-functional/rag-mixed-model-recall-and-provenance.md), [settings consumer semantics](../02-ui/memory-rag-settings-consumer-semantics.md) | Remaining indirect consumers, complete model/source/index/query/injection integration |
| 14 UI / 04 content | [Modal downstream callbacks](../02-ui/dialog-class-reachability-and-action-outcomes.md), [node authoring](../02-ui/prompt-editor-authoring-and-node-workflow.md) | Remaining conditional callbacks/menus, live Qt; editor Create/Delete outcome unconfirmed |
| 16 Installables | [Family-specific status/install/initialize/remove addition](../06-design-input/installables-component-by-component-parity-matrix.md) | Реальная среда/скачивание/inference/repair, физически 0/31; отсутствие универсального repair теперь описано явно |
| 17 External / 20 routes | [Enum/raw aliases, direct settings startup, unproven model bridges](raw-string-event-reachability-and-ui-bridges.md) | Indirect dynamic registrations и actual external service/network outcomes |
| 19 Dependencies | [131 METADATA + selected native PE](../04-dependencies/installed-wheel-metadata-and-native-evidence.md), [real niche](../04-dependencies/core-niche-alternatives-and-parity-gates.md) и [common Rust paths](../04-dependencies/core-library-alternatives-and-native-costs.md) | Target release/managed-layer native closure, selected Rust build/corpus parity и license provenance decisions |
| 20 Traceability | [Pass 13 requirements и explicit validation distinction](../06-design-input/feature-traceability.md) | Полная remaining-action linkage; AST counts не заменяют функциональное доказательство |

## Историческая шкала и накопительные материалы

## Измеримый прогресс по 20 заранее обозначенным областям

`PRIMARY: 13/20` — [█████████████░░░░░░░] 65% **первичных контрактов** документированы. `PARTIAL: 7/20`. Никакая из этих величин **не означает 65% общего аудита**: полный перечень active capabilities ещё расширяется, внешние интеграционные тесты не исполнялись, часть GUI-depth/edge paths открыта.

| № | Functional workstream | Coverage | Подтверждённые материалы | Остаток |
|---:|---|---|---|---|
| 01 | Startup/shutdown/headless | PRIMARY | `03-runtime/startup-and-shutdown.md` | partial-failure shutdown + all headless consumers |
| 02 | LLM dialogue/generation lifecycle | PRIMARY | `01-functional/llm-and-generation.md`, `03-runtime/llm-requests.md` | effect tails + E2E retries |
| 03 | Provider wire protocols | PRIMARY | `03-runtime/openai-protocol-state-machines.md`, `provider-wire-contracts.md` | remote protocol conformance, other adapters |
| 04 | Prompts/DSL/assets | PRIMARY | `01-functional/prompt-system.md`, `prompt-language-and-packs.md` | external prompt editor / packs reachability |
| 05 | History/memory persistence | PARTIAL | `01-functional/history.md`, `memory.md`, `history-compression.md` | identity/delete/recovery/cross-recipient consistency |
| 06 | RAG/FTS/graph | PARTIAL | `01-functional/rag.md`, `knowledge-graph.md`, `graph-maintenance-and-entity-lifecycle.md`, `02-ui/graph-viewer-interactions.md` | multi-storage identity, reindex/GC atomicity and fixtures |
| 07 | Characters/settings/effects | PRIMARY | `01-functional/characters.md`, `registered-character-catalog-and-identity-contracts.md`, `structured-character-actions-and-side-effects.md`, `character-custom-fields-and-formula-policy.md`, `02-ui/character-library-and-maintenance-actions.md` | non-primary tails: alias migration, legacy input reachability, special scene/voice downstream |
| 08 | AI Engine IPC/environment | PRIMARY | `03-runtime/ai-ipc.md`, `ai-environments.md` | independent worker imports, fatal restart E2E |
| 09 | Audio/ASR/TTS | PRIMARY | `01-functional/speech-input.md`, `voice-output.md` | device/hardware and streaming failure tests |
| 10 | Unity Python transport/conversation contract | PRIMARY | `03-runtime/unity-transport.md`, `01-functional/unity-auto-dialogue.md` | remaining Unity client internals deferred |
| 11 | Tools/mini-games/BeatSync | PRIMARY | `01-functional/tools-and-web.md`, `desktop-mini-games.md`, `music-beats.md` | optional UX/helpers/remote outcomes |
| 12 | Images/screen/media | PRIMARY | `01-functional/images-and-capture.md`, `03-runtime/unity-media-transfer.md` | actual Unity producer/integrity and TTL consumer |
| 13 | Settings/migrations/schemas | PRIMARY | `01-functional/settings-storage-and-migrations.md`, `02-ui/settings-navigation-and-lazy-pages.md`, `settings-key-consumer-evidence.md` | remaining builders, dynamic key aliases and effects |
| 14 | GUI all pages/widgets/actions | PARTIAL | `02-ui/*.md`, sandbox/chat/graph/gallery/character/home/news/logs docs | wiki/help, dialogs, other page actions and exhaustive UI matrix |
| 15 | Updates/launcher/release | PRIMARY | `01-functional/launcher-and-updates.md`, `03-runtime/build-and-release-distribution.md` | exact bundled release validation/Windows E2E |
| 16 | Installers/readiness/recovery | PARTIAL | `01-functional/installations.md`, `asr-rag-beat-install-plans.md` | complete readiness matrix, download/repair fixtures |
| 17 | Telegram/other external integrations | PARTIAL | `01-functional/telegram-voice.md`, `standalone-web-surface.md` | real auth, remaining integration reachability |
| 18 | Data maintenance/exports/compatibility | PRIMARY | `01-functional/data-maintenance.md`, `compatibility-imports.md` | cross-storage fixtures and destructive migration QA |
| 19 | Dependency classification/Core vs AI | PARTIAL | `04-dependencies/python-import-reachability.md` | dynamic imports, native DLL, runtime-only modules, Rust comparisons later |
| 20 | Capability traceability/validation evidence | PARTIAL | `06-design-input/feature-traceability.md` | per-action exhaustive matrix + fixtures |

### Что остаётся непосредственно для закрытия аудита

**Наиболее крупные активные gaps:** незакрытые GUI action paths (remaining dialogs (Guide, background task, pipeline and export independently documented), notification errors), оставшаяся settings key-to-consumer matrix, runtime reachability динамических imports/плагинов, граф GC/identity integration tests и часть effects/migration, all installable health states, dependency/native boundary и верификация functionality → requirement → future parity test.

**Исключено по текущему решению пользователя:** выбор GUI-фреймворка и проектирование итоговой Rust-архитектуры (это отдельные фазы **после** аудита), детальный старый Unity animation/rendering internals, перенос Python inference на Rust.

### Принцип обновления

При каждом продолжении изменять статус **только** если добавлено source evidence и описан основной end-to-end контракт; при обнаружении новой функциональной области **увеличивать denominator**, а не искусственно повышать completion ratio. Если функциональность не подтверждена active/conditional, оставлять `UNRESOLVED` либо `EXPERIMENTAL`, не считать обязательным parity.

**См. также:** [checkpoint](research-progress.md), [реестр](active-feature-inventory.md), [неясности](open-questions.md), [матрица требований](../06-design-input/feature-traceability.md).

## Обновление текущего прохода — подтверждённые новые evidence, без повышения первичного процента

`PRIMARY 12 / 20` — [████████████░░░░░░░░] **60% базовых контрактов**. `PARTIAL 8 / 20` — [████████░░░░░░░░░░░░]. **Полная завершённость аудита не измерена**.

| Workstream | Новое source evidence | Непройденная граница до PRIMARY |
|---|---|---|
| 05 History/Memory | [history epoch](../01-functional/character-reset-epoch-and-storage-consistency.md), [memory purge ID repro](../01-functional/memory-purge-embedding-identity-regression.md) | Other identity/purge/reindex races, transactional restoration |
| 06 RAG/FTS/Graph | [processed ledger vs clear](../01-functional/graph-extraction-ledger-and-clear-consistency.md) | Extract failure/retry, stale asynchronous graph result, graph revision/correct reconstruction |
| 07 Characters | [custom formula/clamp policy](../01-functional/character-custom-fields-and-formula-policy.md) | Character effect consumers, complete settings interaction and runtime GUI tests |
| 08 AI Engine | [worker imported-core surface](../04-dependencies/ai-worker-python-core-import-boundaries.md) | Independent Python worker E2E, no actual Rust IPC chosen |
| 14 GUI | [Telegram auth modal](../02-ui/telegram-auth-modal-contracts.md) | Other pending UI actions/Qt end-to-end |
| 16 Installables | [lazy catalogue and readiness distinctions](../01-functional/installable-catalog-lazy-registry-and-status.md) | Component-specific readiness/repair/end-to-end backend transitions |
| 17 Integrations | [Telegram auth future lifecycle](../02-ui/telegram-auth-modal-contracts.md) | Real Telegram login/2FA, rate-limits and delivery failure E2E |
| 19 Dependencies | [AI worker import graph](../04-dependencies/ai-worker-python-core-import-boundaries.md) | Full imports incl DLL and dynamically loaded variants |
| 20 Traceability | 7 new docs & explicit regression acceptance conditions | Exhaustive action→requirement→test matrix across remaining active functions |

**Воспроизведено:** 2 класса SQLite дефектов на временных базах. **Unit-тесты:** 58 OK в 3 группах; blocked PyQt6 test excluded. **Невыполнено:** full GUI/Win/CUDA/network/hardware tests. Количество MD файлов и число тестов не следует выдавать за измеренный процент полного аудита.

## Новая функционально-ориентированная итерация

**Доля основных контрактов: `12 / 20` — [████████████░░░░░░░░] 60%.** Осталось `8 / 20` областей уровня `PARTIAL` — [████████░░░░░░░░░░░░]. Это по-прежнему **не измерение полной готовности исследования**.

| Область | Новый functional evidence | Что осталось |
|---|---|---|
| 07 Characters/settings/effects (PARTIAL) | [Персональный мир и environment awareness](../01-functional/character-world-and-environment-awareness.md): 7 world resources, owner/former/visitor, Unity install/connected, TTS lifecycle, app/game input source | Остальные характерные gameplay effects / динамические сценарии и авторский контент |
| 10 Unity boundary (PRIMARY) | [GameMaster scene direction](../01-functional/game-master-scene-direction.md): два действующих task event, structured intents, hidden directive returned via Unity runtime events; [Unity world state projection](../03-runtime/unity-world-state-prompt-projections.md): stable rules vs capabilities vs transient events | Client-side executor outcome/deep Unity internals отложены |
| 14 GUI (PARTIAL) | [Conversation projection](../03-runtime/conversation-session-projections.md): runtime snapshot → event → ChatPanel title/source/participants, disconnect reset | Full per-action GUI matrix и остальные dialog/settings callbacks |
| 17 Integrations (PARTIAL) | Структурировано разделение `APPLICATION`/`GAME`/`NONE` источника player-authoring и `UNITY` источника session snapshot | Реальная внешняя сеть/Telegram подтверждения и интеграционные пути |
| 20 Traceability (PARTIAL) | `CAP-WORLD-001`, `CAP-ENV-001/002`, `CAP-GM-001/002`, `CAP-DIALOGUE-VIEW-001/002/003` → новые требования и validation fixtures | Исчерпывающий one-action-per-requirement каталог |

**Критерий фокуса:** вопросы о старой реализации разбираются лишь для определения функций, состояний и гарантий. Баги фиксировать мимоходом, не тратить проходы на репродукторы и проектирование исправлений. Пробелы функциональности важнее новых расследований дефектов. `GameMasterDirectiveRegistry` и новый bounded transcript — `EXPERIMENTAL/UNRESOLVED` до доказательства production registration.

## Актуальное обновление: 2026-10-31 — функциональный проход без баг-охоты

**PRIMARY: `13/20`** — [█████████████░░░░░░░] **65% покрытия основных контрактов**; **PARTIAL: `7/20`**. Изменение `12→13` основано на проверенном `CharacterManager._CHARACTER_DEFINITIONS`, жизненном цикле ленивого runtime и полном пути structured character effects (`characters/character.py`, `model_controller.py`, `character_controller.py`), а **не** на приросте числа документов. Остальные 7 областей требуют дополнительных доказательств. Это **не процент всего аудита**. Предыдущие записи `12/20` выше отражают прошлые снимки, не актуальную оценку.

| Workstream | Доказанное углубление | Невыполненные задачи |
|---|---|---|
| **07 Characters** (PARTIAL → **PRIMARY**) | [9 IDs, lazy registry, per-character overrides, GUI-only profile](../01-functional/registered-character-catalog-and-identity-contracts.md); [ordered effects, local vs Unity action requests](../01-functional/structured-character-actions-and-side-effects.md) | Legacy action-ingress reachability, редкие команды и миграция кастомных alias |
| 09 Audio/voice (PRIMARY) | [Remote provider presets](../01-functional/remote-voice-presets-and-character-routing.md), [local voice GUI](../02-ui/local-voice-model-management-and-compile-dialogs.md), [ASR catalog](../02-ui/asr-model-gallery-and-settings-workflows.md) | Реальные аудиоустройства, AI workers и online credentials E2E |
| 14 GUI (PARTIAL) | [API preset/schema editor](../02-ui/api-presets-and-model-parameter-editor-workflows.md), [RAG/embedding pipeline](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md), [context/database inspector](../02-ui/context-and-sqlite-data-inspection-workflows.md) | Exhaustive callback/action inventory; conditional dialogs and notifications |
| 16 Installables (PARTIAL) | [31 static entries / 11 loader groups / dynamic RAG](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md); [manifest→install→ready](../01-functional/installable-catalog-and-runtime-readiness-matrix.md) | Per-component readiness and successful end-to-end install/repair |
| 18 Export/maintenance (PRIMARY) | [Fine-tune sample ratings, retention, filters, Raw/ShareGPT](../01-functional/fine-tuning-data-capture-curation-and-export.md) | Sample fixture / lossless-multimodal compatibility |
| 19 Core/AI dependencies (PARTIAL) | [84 requirements, 32 direct import mappings, 52 without direct import](../04-dependencies/full-requirements-runtime-evidence-ledger.md), [720 files AST](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md), [GPU/topology](../01-functional/hardware-acceleration-and-ai-engine-administration.md) | Wheel transitives, Windows native DLL, dynamic execution, sandbox boot with AI worker |
| 20 Traceability (PARTIAL) | Functional matrix expanded for new domains in [feature-traceability](../06-design-input/feature-traceability.md) | Proof for each UI action and conditional install/backend |

**Принцип:** в этом проходе только чтение исходников и разработка документации. GUI, Windows, network, CUDA и install E2E не выполнялись. Фреймворк GUI и окончательная архитектура Rust сознательно исключены.


## Functional continuation 2026-10-31: углубление шести контрактов, без искусственного прироста процента

`PRIMARY 13/20` — [█████████████░░░░░░░] **65% основных путей**; `PARTIAL 7/20`. Число документов и приведённые ниже source ranges не заменяют закрытия каждого непроверенного пользовательского сценария. Общая завершённость аудита **не измерена**.

| Workstream | Что дополнительно подтверждено | Остаток до полноценного аудита |
|---|---|---|
| 05 History/memory (PARTIAL), 06 RAG/FTS/graph (PARTIAL) | [RAG corpus identities + index modes](../01-functional/rag-storage-retrieval-and-indexing-modes.md) — поиск active/archive, forgotten/island, по модели, full vs missing | cross-store fixtures, complete metadata consistency/graph search/provenance |
| 09 Audio/ASR/TTS (PRIMARY) | [5 ASR IDs + TTS backend lifecycle](../01-functional/asr-tts-managed-backend-operational-contracts.md) | actual Python worker, device and credentials E2E |
| 11 Games/Beat (PRIMARY) | [Explicit manual games target + Beat cache UX](../02-ui/game-settings-manual-launch-and-beat-cache.md) | game runtime results and Unity outcome E2E |
| 12 Images/screen (PRIMARY) | [Desktop/camera/Unity provenance and image storage UI](../02-ui/screen-camera-image-management-user-contracts.md) | Unity FrameRecorder producer and actual device transfer |
| 14 GUI (PARTIAL) | [API catalog/dialog reachability](../02-ui/api-model-discovery-and-conditional-dialogs.md), games, screen/camera controls | remaining action matrix, windows lifecycle and Qt E2E |
| 16 Installables (PARTIAL) | [Component probe/action distinctions](../01-functional/installable-component-probe-and-operation-contracts.md) | real managed env install/uninstall/repair, all component statuses |
| 19 Dependencies (PARTIAL) | [ASR/TTS model/backend boundary](../01-functional/asr-tts-managed-backend-operational-contracts.md) | transitive/native/DLL closure and dynamic imports |
| 20 Traceability (PARTIAL) | 6 new documents and requirements added to [traceability](../06-design-input/feature-traceability.md) | exhaustive action-by-action coverage and executable parity fixtures |

**Фокус:** реализованное поведение, не дефекты старого Python. Legacy не менялись. Slint/Qt сравнительный выбор и Rust-архитектура остаются после завершения discovery. Отчёт о тестах: в этом проходе только source reading и проверка навигации docs, без live E2E.

## Дополнительная проверка внешних интеграций

| Workstream | Новое подтверждение | Следующая проверка |
|---|---|---|
| 17 External integrations (PARTIAL) | [Production/optional/standalone entrypoint classification](../01-functional/external-integration-entrypoints-and-reachability.md): Telegram, builtin tools, remote voice, web/VTT, HOI4 | live external credentials/bot/network E2E and remaining integration producers |


## Дополнительно: RAG ранжирование и условия доступности результата

| Workstream | Дополнено | Остаток |
|---|---|---|
| 06 RAG/FTS/graph (PARTIAL) | [query context + fusion + optional CE](../01-functional/rag-query-fusion-reranking-and-result-contracts.md): 5 combine policies, source IDs, access stats | actual LLM prompt injection limits and real worker/graph+DB data tests |


## Дополнение: RAG injection — функциональный контракт запроса

| Workstream | Новые исходники и сценарии | Остаётся |
|---|---|---|
| 06 RAG/FTS/graph (PARTIAL) и 02 LLM lifecycle (PRIMARY) | [auto / tool gate, memory/history/graph rendering, custom template, ordering](../01-functional/rag-context-injection-and-source-rendering.md) | E2E реального контекста, storage fixtures/graph lifecycle/edge actor provenance |

### Дополнение: локальное IPC внешнего управления

В области **17 / External integrations** подтверждён production-registered optional local TCP/JSON control-plane, **шесть методов** (`ipc.ping/status/methods`, `hardware.snapshot`, `ai.topology`, `ai.restart_service`), с независимой activation/settings lifecycle. [Source-specific contract](../01-functional/local-runtime-ipc-external-control-contract.md). **PRIMARY 13/20, PARTIAL 7/20** — не изменены: внешние live consumers и полноценный audit по остальным интеграциям ещё не покрыты.

### Дополнение: обязательный пользовательский first-run flow

Область **14 / GUI**: подтверждена активная ветвь first-use согласия `EULA_ACCEPTED → EULAWidget → Accept/Reject → optional LANGUAGE restart → Guide/Wiki`, ранее отсутствовавшая в каталоге отдельных сценариев. [Контракт](../02-ui/first-run-agreement-language-and-guide-flow.md). **13 PRIMARY / 7 PARTIAL без повышения:** полное покрытие всех действий GUI не закончено.

### Дополнение: native systems / AI dependencies

Область **19 / Core vs Python AI dependencies**: подтверждены функциональные Windows boundaries `DXGI/nvcuda hardware inventory`, `PortAudio/ole32 audio endpoint identity`, `user32 Unity process close`, `DPAPI account`, `kernel32 AI native loader path`, а также перечисление AI installer/runtime packages. [Source audit](../04-dependencies/native-system-api-and-ai-library-ownership.md). **13 PRIMARY / 7 PARTIAL** неизменно; полноты wheel/native closure нет.


## Functional pass: конкретно закрытые подпути при сохранении 13/20

Новый пакет: **5 дополнительных** source-backed specifications. Для областей со статусом `PARTIAL` указан проверяемый denominator *подпутей*, не приписывается универсальный процент готовности проекта.

| Workstream | Подпуть, документирован в этом проходе | Что ещё блокирует PRIMARY/full parity |
|---|---|---|
| 16 Installers/readiness (PARTIAL) | 31 статическая карточка + dynamic RAG identity; metadata/probe/late event; backend preview/admission/FIFO/cancel/result/recheck | Все компонентные `status/plan/initialize/repair`, managed environment transitions, downloads, реальные AI compatibility fixtures |
| 14 GUI actions (PARTIAL) | 17 строк AI Hub action→intent→effect; thinking/compression/tool/status/errors и per-message voicing | Все оставшиеся Settings UI builders/action handlers, modal lifecycle, shortcuts/keyboard, live Qt end-to-end |
| 20 Traceability (PARTIAL) | Новый traceability для 5 CAP с источником, requirement и конкретными future tests | Доказать исчерпывающий список active actions других страниц и предоставить исполняемые parity fixtures |

**Нельзя повышать 13/20 только за описание компонентов:** readiness без проверки конкретных Python AI-воркеров, UI action mapping без остальных экранов, отсутствие full network/hardware/Qt runs не устраняются архивированием документов. Из семантически открытого остается также `05 History`, `06 RAG/Graph`, `17 Integrations`, `19 Dependencies`.

### Exit-gates ближайших PARTIAL областей (не универсальный процент всего проекта)

Чтобы прогресс внутри области был наблюдаемым, следующий **фиксированный** контрольный список меняется только при закрытии критерия evidence. `✓` — проверено чтением исходников/спецификацией, `○` — не закрыто. Runtime E2E — самостоятельная стадия, не покрытая static audit.

| Area | Exit gate | Evidence | Состояние |
|---|---|---|:---:|
| 16 Installation | Полная номенклатура static/dynamic IDs | [31+RAG](../01-functional/installable-catalog-identity-and-coverage.md) | ✓ |
| 16 Installation | Context-based status/readiness и доставка позднего результата | [Status](../03-runtime/installable-status-observation-and-invalidation.md) | ✓ |
| 16 Installation | Admission/FIFO/cancel/complete/recheck | [Queue](../03-runtime/install-operation-admission-queue-and-completion.md) | ✓ |
| 16 Installation | **Исчерпывающий** source review каждого `status/plan/initialize/repair` | Component families частично в [probes](../01-functional/installable-component-probe-and-operation-contracts.md) | ○ |
| 16 Installation | Реальные Windows/backend/AI environment/download E2E | Не исполнялись | ○ |
| 14 GUI | Идентификация основных pages/settings | [navigation](../02-ui/settings-navigation-and-lazy-pages.md) | ✓ |
| 14 GUI | AI Hub page-action matrix | [17 actions](../02-ui/ai-hub-interaction-traceability-checklist.md) | ✓ |
| 14 GUI | Generation/status/error/voice event projection | [Status](../02-ui/generation-progress-error-and-voice-indicators.md) | ✓ |
| 14 GUI | Все оставшиеся dialogs/settings actions/hotkeys | Не завершено | ○ |
| 14 GUI | Live Qt E2E, keyboard/accessibility | Не исполнялись | ○ |

**Срез 2026-10-31:** `16 Installation: 3/5 exit gates`, `14 GUI: 3/5 exit gates` по указанному фиксированному списку. Это помогает видеть движение внутри *частично* аудированных областей; полный статус остаётся `PRIMARY 13/20, PARTIAL 7/20` до закрытия независимых оставшихся контрактов.

## Wall-clock continuation: evidence added without inflating headline percentage

**Промежуточный срез**: начало 2026-10-30 **22:42:47 UTC**, целевой конец **23:12:47 UTC**. Пока подтверждены **13/20 PRIMARY, 7/20 PARTIAL**, то есть 65% покрытия *основных функциональных контрактов*; весь аудит не имеет измеренного процента завершения. Новые документы служат evidence следующих подпутей, но не закрывают live E2E:

| Workstream | Новое evidence | Открытый exit gate |
|---|---|---|
| 05 History/memory PARTIAL | [Пользовательские операции, active/archive/facts/summaries](../01-functional/history-memory-lifecycle-and-user-operations.md); [экспорт/импорт World DB](../01-functional/world-db-json-export-import-user-workflow.md) | Совместимые legacy-экспорты, реальные recovery fixtures/превью, полный cross-store audit |
| 06 RAG/Graph PARTIAL | [Провайдеры embeddings](../01-functional/embedding-provider-wire-and-failure-contracts.md), [состав мультимодального content](../01-functional/multimodal-message-content-representations.md) | Реальные model/provider fixtures, graph integration и конечный перечень query options |
| 14 GUI PARTIAL | [12 разделов Settings, действия](../02-ui/settings-functional-actions-and-live-effects.md), [7 страниц](../02-ui/main-pages-action-reachability-matrix.md), [горячие клавиши](../02-ui/keyboard-clipboard-and-direct-manipulation-contracts.md) | Остальные dialog/action branches, GUI E2E, доступность и локализация |
| 16 Installer PARTIAL | [31 статический ID по семействам](../01-functional/installable-families-runtime-operations.md), статус/планы отдельно | Все API каждой конкретной модели + Windows/download/inference E2E |
| 17 External PARTIAL | [Telegram маршруты](../01-functional/telegram-bot-protocol-routing-and-session-semantics.md), [web/remote endpoints](../01-functional/external-http-sources-and-user-actions.md), [YouTube TV](../01-functional/tv-observation-youtube-frame-and-dialogue-provenance.md) | Credentials/network/Unity live integration и остальных conditional branches |
| 19 Dependencies PARTIAL | [Optional/transitive/installer-owned dependencies](../04-dependencies/implicit-optional-and-installer-owned-packages.md); [process topology](../03-runtime/functional-process-topology-and-ownership-boundaries.md) | Exact transitive wheel graph, native DLL closure, Windows deployment |
| 20 Traceability PARTIAL | [Message/turn/actor ID](../01-functional/dialogue-actor-and-message-identity-contracts.md), [actual test corpus](../06-design-input/existing-test-corpus-and-functional-parity-gates.md), [traceability matrix](../06-design-input/feature-traceability.md) | Exhaustive per-action source→capability→requirement→validation, deterministic parity+E2E |

**Не делать:** подменять процент полного аудита числом Markdown-файлов, считать все `test_*.py` успешно прошедшими, переносить реализацию Python один-в-один или устранять дефекты вместо описания поведения. Шкала обновляется только доказательствами по фиксированным exit-gates.


| 02 LLM lifecycle PRIMARY | [Типизированный поток и presentation lifecycle](../03-runtime/llm-stream-event-and-presentation-lifecycle.md): STARTED, text/reasoning, tool, usage, completed/failed; 25ms coalescing | реальный provider SSE/Qt end-to-end |


### Pass 11 — продвижение без изменения headline PRIMARY gate

| Незакрытая область | Новые проверенные факты | Что всё ещё нужно для перехода из PARTIAL |
|---|---|---|
| 05 История | [requested action history через compression boundary](../01-functional/structured-action-history-and-compression-bridge.md) | Все редкие операции и сохранение импортируемых форматов + parity tests |
| 06 RAG/Graph | [seed facts/islands/relations через prompt DSL](../01-functional/dsl-executable-prompt-contract.md) | Все graph extraction и model-specific retrieval options/fixtures |
| 14 GUI | [52 live candidate async callsites / 20 ViewModels](../02-ui/intent-workloads-and-visible-state-consistency.md) | Полный реестр modal actions и подтверждение register→handler→effect, живой UI E2E |
| 17 External | [Unity server inbound seven requests](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md); [ASR game speaking lease](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md) | Client-side Unity end-to-end, Telegram/network variants, optional pathways |
| 20 Traceability | [288 объявленных событий, 202 literal callees, 117 dual-sided static evidence](event-producer-consumer-callsite-index.md); [Pass 11 trace rows](../06-design-input/feature-traceability.md) | Ручная проверка reachability event graph, непрямой/dynamic registrations и полного regression suite |

**Headline unchanged: 13/20 PRIMARY / 7 PARTIAL.** Углубление не заменяет полное закрытие этих exit-gates.

**Pass 11, PRIMARY workstream 01 (startup):** [дополнительная headless граница](../03-runtime/headless-core-functional-surface-and-readiness.md) и 6 адресных offline tests, без перевода PARTIAL installable/external/GUI областей в PRIMARY. Для GUI Gate 14: [инвентаризация 52 async-callsite](gui-async-operation-callsite-index.md), не подтверждённый E2E. **Итог: 13 PRIMARY / 7 PARTIAL неизменен.**

**Pass 11, Installer 16 PARTIAL:** [подготовлена исчерпывающая per-component validation matrix](../06-design-input/installables-component-by-component-parity-matrix.md), 31/31 static catalog ID, 0/31 machine E2E. Это закрывает план статической проверки, но **не** machine readiness/install exit gate.

**Selected offline tests (Pass 11):** 308 passed in separate invocations, 3 failed, 2 successful subtests; missing PyQt6 and `chess` block four additional test modules at collection. See [handoff](pass11-functional-audit-handoff.md). These do not close hardware/UI/network/install gates.

## Pass 12 — конкретное продвижение семь `PARTIAL` областей без подмены процента

**Headline не меняется: `13/20 PRIMARY` (65% только первичных контрактов), `7/20 PARTIAL`.** Новые величины ниже относятся к измеряемому source discovery, **не** являются процентом полного аудита или доказательством Windows/GUI/network E2E.

| PARTIAL workstream | Что дополнительно изучено и измерено в Pass 12 | Не закрытая проверка |
|---|---|---|
| 05 — History/Memory | [Raw event-пейджинг](raw-string-event-reachability-and-ui-bridges.md): отдельные initial / older load, `request_id`, `character_id`, смещение страницы; [16 file-selection и import/export contexts](../02-ui/native-dialogs-and-file-input-output-workflows.md) | Актуальность старой страницы при смене recipient, cross-storage импорт/удаление и реальные GUI+DB fixtures |
| 06 — RAG/FTS/Graph | [99 unique UI settings keys](../02-ui/memory-rag-registered-settings-source-index.md), [96 внешних literal references и три спецслучая](rag-settings-direct-consumer-evidence-index.md); [4 graph ingestion modes](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md); [4 built-in pipeline presets](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md) | Полный consumer context каждого key, dynamic access, source→embedding→index→query→LLM output E2E, реальные HF/RAG устройства |
| 14 — GUI | [20 именованных QDialog candidates, 17 constructor callsites](../02-ui/dialog-class-reachability-and-action-outcomes.md), [16 file / 8 short input dialogs](../02-ui/native-dialogs-and-file-input-output-workflows.md), [29 QMessageBox.question](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md), [517 Qt signal connect callsites в 75 файлах](gui-signal-registration-callsite-index.md) | Для каждого handler проследить Core side effect; динамические меню/keyboard/events; реальные Qt state/cancel/permissions/GUI E2E |
| 16 — Installation/readiness | Продолжено изучение asset/process boundary; offline target tests для catalog status, typed queue, model readiness, lazy loader — **51 passed, 6 subtests passed** в трёх адресных pytest запусках (см. checkpoint) | E2E фактической установки: **0/31** static cards физически проверены на Windows/GPU; не считать 51 unit test доказательством ready всех моделей |
| 17 — External integrations | [Внешние программы и нативные loader scopes](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md) отделены от AI worker; new raw event screen-capture producer поддаётся трассировке | Live Telegram auth/MTProto, external providers, optional tools/network, реальная Unity client delivery |
| 19 — Dependencies | Выделены `ffmpeg.exe`, 7z, subprocess, CUDA/ONNX/Torch DLL и Windows системные API по consumer boundary, без предложения переписать AI inference | Транзитивные wheel metadata и native redistributables, локальные runtime environments/системные библиотеки |
| 20 — Traceability | 10 новых source-grounded документов, granular requirements; индексы [GUI callbacks](gui-signal-registration-callsite-index.md), [raw events](raw-string-event-reachability-and-ui-bridges.md), [99-key consumers](rag-settings-direct-consumer-evidence-index.md) | Доказать для каждого действующего action `entrypoint→registered handler→effect→storage/GUI/Unity→validation`; автоматическая синтаксическая ссылка без runtime не закрывает gate |

**Дополнительная addressable unit evidence Pass 12:** `test_runtime_features.py`, `test_settings_registry.py`, `test_rag_preset_view_model.py` — **20 passed**; `test_rag_preset_model_downloads.py`, `test_rag_readiness.py`, `test_installable_catalog_loaders.py` — **16 passed**; `test_installable_catalog_service.py`, `test_installable_controller.py`, `test_rag_model_catalog.py` — **35 passed, 6 subtests passed**. Итого **71 successful tests (6 subtests отдельно)** в трёх offline invocation groups; не full test suite. Запуски предыдущих проходов сюда не прибавлять.

## Pass 12 — итоговое углубление (source/static/offline evidence)

**Headline:** `13/20 PRIMARY = 65% первичных контрактов`; `7/20 PARTIAL`. Не является оценкой полного объёма.

- 05 History: [projection/paging/actor identity](../01-functional/history-ui-projection-actor-identity-and-paging.md), 22 addressed tests (вместе с sender/epoch), без live GUI.
- 06 RAG/Graph: [99 UI keys](../02-ui/memory-rag-registered-settings-source-index.md), [direct consumer evidence](rag-settings-direct-consumer-evidence-index.md), [four graph ingestion paths](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md), [RAG golden fixtures](../01-functional/rag-deterministic-golden-surface-and-result-types.md), [readiness generations](../01-functional/rag-model-runtime-readiness-and-worker-generation.md).
- 14 GUI: [517 signal connections](gui-signal-registration-callsite-index.md), [20 dialog candidates/17 direct calls](../02-ui/dialog-class-reachability-and-action-outcomes.md), [16 file/8 input dialogs](../02-ui/native-dialogs-and-file-input-output-workflows.md), [29 user confirmations](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md); static evidence, not handler→effect completeness.
- 16 Installation: model/catalog/queue offline tests, **0/31 actual Windows/GPU installations**.
- 17 External: native/ffmpeg/7z and external tools separated from AI worker, no live Telegram or network E2E.
- 19 Dependencies: external executables/natives by responsible process, transitive wheel/DLL closure open.
- 20 Traceability: 250 files/2177 static `test_*` functions [inventory](test-suite-static-validation-map.md), 157 passed, 14 subtests, 4 failed in 8 completed invocations (not a full suite).

[Pass 12 handoff](pass12-functional-audit-handoff.md).

**Pass 12 dynamic loaders:** [LLM/ASR/tools/GUI/installable/worker registry](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md) отдельно от direct Python imports; `test_tool_manager_lazy.py`, `test_ai_contour_boundaries.py`, `test_declarative_model_profiles.py` → **19 passed**. 32 direct imported requirements из 84 не дают complete runtime dependency closure.

**Pass 12 Dependency workstream 19:** [24 dynamic import/WinDLL/CDLL callsites / 18 production `.py` files](production-dynamic-import-callsite-index.md), включая 16 import_module и 5 WinDLL; полное wheel/native transitive closure всё ещё **PARTIAL**.
