# NeuroMita Core 2.0: функциональное исследование

**Актуальный срез — 2026-10-31, Pass 13:** [сводный функциональный каталог, доказательства и оставшиеся gates](00-research/current-functional-baseline.md). Начинать с него: ниже сохранены навигация и исторические итерации, их прежние «дальше/не исследовано» не всегда актуальны. Аудит продолжается; итоговая Rust-архитектура и сравнение GUI находятся за его рамками.

Полученный Pass 12 импортирован полностью: [181 документ, backup и сверка с кодом](00-research/pass13-import-and-source-baseline.md). Новые результаты Pass 13:

- [Смешанные embedding models, lexical recall и provenance](01-functional/rag-mixed-model-recall-and-provenance.md).
- [Смысл настроек памяти/RAG, TTL и maintenance](02-ui/memory-rag-settings-consumer-semantics.md).
- [Две ветки history paging и защита от запоздавшего результата](02-ui/history-page-fencing-and-live-replay.md).
- [World DB exchange: изолированная проверка scope/remap/repeat/rollback](01-functional/world-db-exchange-isolated-validation.md).
- [Prompt editor и предел node workflow](02-ui/prompt-editor-authoring-and-node-workflow.md).
- [Dialog callbacks → draft/save/system effects](02-ui/dialog-class-reachability-and-action-outcomes.md), [per-family install/initialize/uninstall outcomes](06-design-input/installables-component-by-component-parity-matrix.md).
- [Локальные wheel metadata и PE imports](04-dependencies/installed-wheel-metadata-and-native-evidence.md), [нишевые Rust alternatives](04-dependencies/core-niche-alternatives-and-parity-gates.md), [остальные core libraries и native cost](04-dependencies/core-library-alternatives-and-native-costs.md).

По исследованным не-AI функциям hard blocker «обязательно нужен Python Core» не выявлен. Это не готовый Cargo stack и не обещание полного паритета: отдельно отмечены морфология/числительные, Telegram sessions, лицензии/provenance, media/native packaging и непроведённые runtime проверки.

NeuroMita объединяет диалог с персонажами, игровое окружение Unity, историю и память, голосовые функции и управление устанавливаемыми AI-компонентами. Первичный composition root подтверждает эти области, но регистрация компонента сама по себе не доказывает полноту его функционального аудита.

## Навигация

- [Область и ограничения](00-research/scope.md).
- [Метод исследования](00-research/methodology.md).
- [Карта репозиториев](00-research/repository-map.md).
- [Точки входа](00-research/runtime-entrypoints.md).
- [Реестр функциональных областей](00-research/active-feature-inventory.md).
- [Индекс доказательств](00-research/source-evidence-index.md).
- [Прогресс и продолжение](00-research/research-progress.md).
- [Прогресс-бар покрытия 20 функциональных областей и список оставшихся хвостов](00-research/audit-coverage-ledger.md).
- [Открытые вопросы](00-research/open-questions.md).
- [Запуск и завершение](03-runtime/startup-and-shutdown.md).
- [Жизненный цикл необязательных функций](03-runtime/optional-features.md).
- [Основной диалоговый turn и structured effects](01-functional/llm-and-generation.md).
- [Формирование контекста](01-functional/prompt-system.md).
- [Авторские наборы, DSL и Post-DSL](01-functional/prompt-language-and-packs.md).
- [История, редактирование и snapshots](01-functional/history.md).
- [LLM retries, fallback и deadlines](03-runtime/llm-requests.md).
- [Unity retry outbox](03-runtime/unity-retry-outbox.md).
- [Unity transport с двух сторон](03-runtime/unity-transport.md).
- [Media и settings projection](03-runtime/unity-media-transfer.md), [Unity admission и ASR](01-functional/unity-dialogue-admission.md).
- [Автодиалог, продолжения и idle Unity](01-functional/unity-auto-dialogue.md).
- [Смысл локаций для персонажей, context окружения и осведомлённость о доступных функциях](01-functional/character-world-and-environment-awareness.md).
- [GameMaster: действующий Unity-intent путь и отдельно не подключённый control plane](01-functional/game-master-scene-direction.md).
- [Контекст групповой беседы: Unity ownership, Core snapshot и UI-проекция](03-runtime/conversation-session-projections.md).
- [Как Unity передаёт правила, состояние мира, доступные действия и одноразовые события в prompt](03-runtime/unity-world-state-prompt-projections.md).
- [Structured response: schema, sparse, repair и effect gates](03-runtime/structured-response-contract.md).
- [Изображения, экран и веб-камера: функции Python](01-functional/images-and-capture.md).
- [Инструменты персонажа и веб](01-functional/tools-and-web.md).
- [Музыкальные биты и кеш Beat Sync](01-functional/music-beats.md).
- [Desktop мини-игры: шахматы и морской бой](01-functional/desktop-mini-games.md).
- [Отдельные VTT и mock HTTP API](01-functional/standalone-web-surface.md).
- [HOI4 standalone-прототип (не подтверждённый active Core)](01-functional/hoi4-standalone-prototype.md).
- [Контекстное окно и сжатие](01-functional/history-compression.md).
- [Персонажи и их состояние](01-functional/characters.md).
- [Память](01-functional/memory.md), [RAG](01-functional/rag.md), [граф знаний](01-functional/knowledge-graph.md).
- [Напоминания и таймеры](01-functional/reminders-and-timers.md).
- [SQLite и persistence](03-runtime/persistence.md).
- [AI IPC и supervision](03-runtime/ai-ipc.md), [managed environments](03-runtime/ai-environments.md).
- [Озвучка и доставка аудио](01-functional/voice-output.md), [голосовой ввод и устройства](01-functional/speech-input.md).
- [Telegram voice и авторизация](01-functional/telegram-voice.md).
- [Каталог и установки](01-functional/installations.md), [AI Hub GUI](02-ui/ai-hub.md).
- [Навигация, галерея, новости, справка и логи](02-ui/navigation-gallery-and-help.md).
- [Запуск игры, обновления и восстановление](01-functional/launcher-and-updates.md).
- [Песочница, диагностика и экспорт данных](01-functional/diagnostics-and-data-export.md).
- [Локальное JSON IPC управление](03-runtime/local-control-ipc.md), [языки и предпочтения UI](02-ui/localization-and-preferences.md).
- [API presets, модели и параметры](01-functional/provider-configuration.md), [browser OAuth и аккаунты](01-functional/account-authentication.md).
- [Оценка контекста, токены, provider pricing и реальные usage](01-functional/token-budget-and-pricing.md).
- [Wire-контракты Gemini / ChatGPT Plan](03-runtime/provider-wire-contracts.md), [transform pipeline сообщений](01-functional/message-transforms.md).
- [CUDA fatal recovery Python AI worker](03-runtime/cuda-fatal-worker-recovery.md), [конкретные AI install plans](01-functional/installer-component-plans.md).
- [Chat Completions и Responses: request/stream/failed states](03-runtime/openai-protocol-state-machines.md).
- [ASR, RAG и Beat: подробные планы установки](01-functional/asr-rag-beat-install-plans.md), [голосовые пакеты персонажей](01-functional/voice-asset-distribution.md).
- [Installer: отмена, rollback, clean, uninstall, repair](03-runtime/installer-recovery-and-uninstall.md), [build/release/bootstrap/Launcher.exe](03-runtime/build-and-release-distribution.md).
- [Частичная матрица Python imports и функциональных зависимостей](04-dependencies/python-import-reachability.md).
- [Хранилище настроек и подписки](03-runtime/settings-and-preferences-store.md).
- [Настройки/секреты/API schemas/migrations](01-functional/settings-storage-and-migrations.md), [typed services + subscriptions](03-runtime/typed-services-and-settings-observers.md), [полный реестр Settings UI и lazy loading](02-ui/settings-navigation-and-lazy-pages.md).
- [Filesystem paths, Unicode native loaders и каталог моделей](03-runtime/filesystem-paths-and-native-loaders.md).
- [HTTP client ownership, ошибки, timeout/retry](03-runtime/network-client-ownership-and-errors.md).
- [Редактор БД, импорт/экспорт, переиндексация и очистка](01-functional/data-maintenance.md).
- [Совместимость и восстановление старых сохранений](01-functional/compatibility-imports.md).
- [Голосовые модели, профили и действия GUI](02-ui/voice-controls.md).
- [Фоновые задачи, отмена, перегрузка и события](03-runtime/background-tasks-and-events.md).
- [Settings: 83 статически зарегистрированных ключа и подтверждённые потребители](02-ui/settings-key-consumer-evidence.md).
- [Graph GC, merge, retagging, full clear и lifecycle сущностей](01-functional/graph-maintenance-and-entity-lifecycle.md); [действия просмотрщика графа](02-ui/graph-viewer-interactions.md).
- [Sandbox: панель управления и presentation contract](02-ui/sandbox-page-functional-contract.md).
- [Чат: ввод и вложения](02-ui/chat-composer-and-attachments.md), [история, stream и действия над сообщениями](02-ui/chat-stream-history-and-message-actions.md), [structured panels](02-ui/structured-ai-results-presentation.md).
- [Галерея Unity: thumbnail pipeline и просмотрщик](02-ui/gallery-lifecycle-and-photo-viewer.md).
- [Библиотека персонажей: selected vs active и обслуживание](02-ui/character-library-and-maintenance-actions.md).
- [Новости релизов и Live Logs: contracts/refresh/focus](02-ui/news-and-logs-live-ui-contracts.md).
- [Home launcher: launch/stop/update selection, partial update/restart](02-ui/home-launcher-update-and-game-state.md).
- [Wiki: Markdown navigation, locale fallback и Unicode anchors](02-ui/wiki-navigation-localization-and-anchors.md).
- [Guide: уровни, интерактивные screenshot steps, Wiki deep links](02-ui/guide-walkthrough-and-image-focus.md).
- [Диалоги: hide vs cancel, pipeline Apply, fine-tuning/SQLite export и alert](02-ui/dialog-interaction-and-background-task-contracts.md).
- [Дефекты, риски и компромиссы](05-architecture/current-problems.md).
- [Выявленные требования](06-design-input/functional-requirements.md).
- [Матрица source → capability → requirement → validation](06-design-input/feature-traceability.md).

## Новый проход: идентичность AI Hub, очередь, статусы и ошибки

- [31 статическая карточка AI Hub, динамические RAG модели и ownership ассетов](01-functional/installable-catalog-identity-and-coverage.md).
- [Наблюдение готовности компонентов, invalidation и поздние статусы](03-runtime/installable-status-observation-and-invalidation.md).
- [Admission, FIFO очередь, cancel и завершение установки](03-runtime/install-operation-admission-queue-and-completion.md).
- [Трассировка действий в AI Hub от кнопки до backend/state](02-ui/ai-hub-interaction-traceability-checklist.md).
- [GUI: thinking/compression/tool/error/voicing и индикаторы состояния](02-ui/generation-progress-error-and-voice-indicators.md).

## Что уже установлено

Приложение поддерживает full, gui_only и headless. Видимость GUI, готовность обязательного backend и готовность голосовых/поисковых компонентов — разные состояния. Внешний игровой сервер создаётся после обязательных сервисов, но необязательные функции в этот момент могут ещё загружаться.

AI inference остаётся в Python. Исследованный IPC использует multiprocessing spawn/Queue и Python values; самостоятельный worker для Rust потребует нового wire contract. Readiness endpoint, установленное окружение и загруженная модель различаются. Часть service payloads и installer lifecycle ещё требует исследования.

Пока нельзя обоснованно выбрать GUI, схему хранения, транспорт AI IPC, модель actors или границы Rust-модулей: для этого сначала нужен полный каталог поведения. Существующие классы служат доказательствами, их структура не является заданием на перенос.

## Текущий проход: проверенные контракты и воспроизведения

Добавлены source-backed документы по [консистентности графовой экстракции и clear](01-functional/graph-extraction-ledger-and-clear-consistency.md), [сбросу истории и epoch](01-functional/character-reset-epoch-and-storage-consistency.md), [пользовательским полям и формулам персонажей](01-functional/character-custom-fields-and-formula-policy.md), [идентичности memory embeddings и purge](01-functional/memory-purge-embedding-identity-regression.md), [границам Python imports AI worker](04-dependencies/ai-worker-python-core-import-boundaries.md), [Telegram auth modal и сервисным future](02-ui/telegram-auth-modal-contracts.md), [каталогу/lazy-installables](01-functional/installable-catalog-lazy-registry-and-status.md).

Выполнены локальные **SQLite-воспроизведения на временных БД**: journal графовой экстракции остаётся после GUI clear; memory purge оставляет embedding при несовпадении SQLite ID/eternal ID и допускает повторную ассоциацию stale embedding. Проведено 58 успешных unit-тестов в трёх группах (23 история, 17 формулы/характеристики, 18 память). Это НЕ end-to-end Windows/GUI/CUDA/сетевые тесты и НЕ доказательство отсутствия иных дефектов. История прежнего прохода ниже должна читаться как исторический срез; в текущем проходе destructive DB проверки делались **только на временных изолированных базах**.

Историческая шкала того прохода: 12/20 PRIMARY и 8/20 PARTIAL; актуальные значения приводятся ниже и в [ledger](00-research/audit-coverage-ledger.md). Общий процент завершения полного аудита не вычислялся.

## Продолжение: приоритет функциональности, а не дефектов

По уточнённому поручению следующий проход сосредоточен **на том, что система реализует и как действует**, а не на поиске ошибок существующего Python-кода. Изучены [персональные смыслы игровых миров и функциональная осведомлённость персонажа](01-functional/character-world-and-environment-awareness.md), [скрытое управление сценой GameMaster](01-functional/game-master-scene-direction.md), [три различных контракта текущей групповой беседы](03-runtime/conversation-session-projections.md) и [разделение статических правил Unity, динамической доступности и одноразовых событий](03-runtime/unity-world-state-prompt-projections.md). Подтверждена граница: старый Unity→GM→structured-intents путь присутствует в production, а новые `GameMasterDirectiveRegistry`/`GameMasterActionExecutor` пока обнаружены только как отдельная, не подключённая к composition реализация.

В этой итерации ошибки не исследовались; тесты не запускались, пользовательские хранилища не изменялись. Текущая шкала `12/20 PRIMARY` **не повышена**: углубление уже частичных областей 07/14/20 не означает закрытия всех сценариев. Новые документы добавляют source-backed functional contracts и проверяемую трассировку, не предлагая структуру Rust-модулей.

## Functional audit pass — 2026-10-31 (30 минут wall-clock)

Новая документация этого прохода описывает **действующие возможности**, состояния и ограничения поведения; исследования ошибок старого Python специально не проводились. Исходный Python snapshot `CodeNow.zip` и все документы прошлой итерации сохранены неизменными, кроме дополнений к реестрам/оглавлению.

**Пользовательские и application capabilities:**

- [Каталог девяти персонажей, ленивые runtime, GameMaster, специальные эффекты и identity](01-functional/registered-character-catalog-and-identity-contracts.md).
- [Путь structured LLM response до локальных side effects и запрошенных Unity действий](01-functional/structured-character-actions-and-side-effects.md).
- [Удалённые голоса: credentials, presets, character routing](01-functional/remote-voice-presets-and-character-routing.md).
- [Fine-tuning capture, рейтинги, retention, Raw/ShareGPT export](01-functional/fine-tuning-data-capture-curation-and-export.md).
- [GPU detection и shared/split Python AI Engine, полное обслуживание среды](01-functional/hardware-acceleration-and-ai-engine-administration.md).
- [Русская лемматизация RAG и отдельная подготовка числительных для TTS](01-functional/language-normalization-rag-morphology-and-speech-numerals.md).

**GUI как пользовательские сценарии, а не набор QWidget-классов:**

- [ASR engines, настройки и model gallery](02-ui/asr-model-gallery-and-settings-workflows.md).
- [Локальные TTS/VC модели и диалоги сборки](02-ui/local-voice-model-management-and-compile-dialogs.md).
- [API preset CRUD и редактор параметров моделей](02-ui/api-presets-and-model-parameter-editor-workflows.md).
- [RAG pipeline и embedding providers](02-ui/rag-pipeline-and-embedding-provider-user-workflows.md).
- [Контекст LLM, инспекция SQLite и редактирование данных](02-ui/context-and-sqlite-data-inspection-workflows.md).

**Runtime/зависимости:**

- [Installable catalog: 31 static non-RAG cards, dynamic RAG и различие installed/ready/runtime](01-functional/installable-catalog-and-runtime-readiness-matrix.md).
- [Карта lazy runtime imports, GUI/services/installer registry и Core-vs-AI](04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md).
- [Полный manifest `requirements.txt`: 84 записи, 32 direct import и 52 без прямого AST import](04-dependencies/full-requirements-runtime-evidence-ledger.md). Это **инвентаризация**, не перечень обязательных Rust dependencies.

**Покрытие:** [актуальный ledger](00-research/audit-coverage-ledger.md) — **13 из 20** областей имеют основной source-backed контракт (`65% первичных областей`), **7** остаются `PARTIAL`. Это **не 65% всего аудита**: вложенные сценарии и зависимости ещё требуют сверки, реальное Windows/CUDA/Qt/Telegram E2E не проводилось. [Следующая точка](00-research/research-progress.md) зафиксирована. Выбор Slint/Qt и проектирование Rust-архитектуры — отдельно после аудита.


## Текущий функциональный проход: RAG-корпусы, AI-установщики, GUI-сценарии

Последовательно углублены шесть ранее неполно документированных контрактов:

- [RAG: поисковые корпуса, типы retrieval и режимы индекса](01-functional/rag-storage-retrieval-and-indexing-modes.md) — active vs archive history, memory `eternal_id`, исключение islands, vector/FTS/keyword/graph, missing vs full reindex.
- [Component probes и lifecycle installables](01-functional/installable-component-probe-and-operation-contracts.md) — CPU/CUDA/ONNX, FFmpeg/OpenCV, пакет голосов, Beat Sync, RAG-модели, статус/repair/update/uninstall.
- [Управляемые ASR/TTS backend](01-functional/asr-tts-managed-backend-operational-contracts.md) — пять распознавателей и модельно-ориентированные TTS engines, установка отдельно от запуска inference.
- [API model catalogue и conditional dialogs](02-ui/api-model-discovery-and-conditional-dialogs.md) — запрос списка моделей, сортировка/фильтрация/выбор, загрузка голоса, уведомления FFmpeg, неподтверждённые legacy dialogs.
- [Ручные мини-игры и Beat Sync](02-ui/game-settings-manual-launch-and-beat-cache.md) — выбор конкретного персонажа Sandbox/Unity и управление кэшем битов.
- [Экран/камеры/изображения](02-ui/screen-camera-image-management-user-contracts.md) — различие desktop/webcam/Unity head camera, non-native описание, ручная очистка изображений.

**Контроль покрытия:** [13 PRIMARY / 7 PARTIAL](00-research/audit-coverage-ledger.md) на фиксированных 20 workstreams; новые документы уточняют уже исследованные домены, не закрывают все их сценарии. Функциональный аудит продолжается, GUI framework/полная Rust-архитектура отложены. Источник — локальный Python snapshot, Windows/Unity/CUDA/network E2E в этом проходе не проводились.

- [Внешние интеграции: production registration, optional tools и standalone surfaces](01-functional/external-integration-entrypoints-and-reachability.md).

- [RAG: QueryState, union/intersect/two-stage/RRF, cross-encoder и итоговые кандидаты](01-functional/rag-query-fusion-reranking-and-result-contracts.md).

- [RAG → Prompt: eligibility, шаблоны по типу источника и отдельное system-сообщение](01-functional/rag-context-injection-and-source-rendering.md).

- [Локальный IPC: внешнее управление Core](01-functional/local-runtime-ipc-external-control-contract.md) — включаемый TCP/JSON control-plane, ограниченный реестр из шести команд, hardware/AI diagnostics и lifecycle.

- [Первый запуск: EULA, локаль и Guide](02-ui/first-run-agreement-language-and-guide-flow.md) — обязательный GUI agreement, смена языка до согласия, принятие/отказ и переход в интерактивное руководство.

- [Native Windows и Python AI dependency boundaries](04-dependencies/native-system-api-and-ai-library-ownership.md) — DXGI/CUDA hardware, PortAudio endpoint, Unity process guard, Windows DPAPI и осознанное отделение inference DLL.

## Functional continuation — 30-minute UTC wall-clock pass (2026-10-30)

Этот проход сознательно исследует **функциональную семантику**, а не дефекты старого кода и не выбор Rust-архитектуры. Новые материалы удобно читать по предметным границам:

**Функциональные контракты:** [операции всех семейств устанавливаемых компонентов](01-functional/installable-families-runtime-operations.md); [история/память: сценарии пользователя и производные индексы](01-functional/history-memory-lifecycle-and-user-operations.md); [движки эмбеддингов и wire-контракты](01-functional/embedding-provider-wire-and-failure-contracts.md); [Telegram bot: запрос/ожидание/доставка](01-functional/telegram-bot-protocol-routing-and-session-semantics.md); [структурные представления мультимодальных сообщений](01-functional/multimodal-message-content-representations.md); [YouTube TV observation и источники кадров](01-functional/tv-observation-youtube-frame-and-dialogue-provenance.md); [World.db JSON export/import](01-functional/world-db-json-export-import-user-workflow.md); [внешние HTTP ресурсы](01-functional/external-http-sources-and-user-actions.md).

**GUI:** [семь активных главных страниц и команды](02-ui/main-pages-action-reachability-matrix.md); [все 12 групп Settings и функциональные эффекты](02-ui/settings-functional-actions-and-live-effects.md); [клавиатура/буфер обмена/прямое редактирование](02-ui/keyboard-clipboard-and-direct-manipulation-contracts.md).

**Runtime и platform boundary:** [политика доступности structured effects](03-runtime/runtime-effect-availability-and-structured-schema-policy.md); [наблюдаемость одной генерации/ASR/TTS через trace](03-runtime/per-request-performance-traces-and-diagnostic-metrics.md); [фактическая топология процессов по пользовательским функциям](03-runtime/functional-process-topology-and-ownership-boundaries.md); [dynamic/installer-owned зависимости](04-dependencies/implicit-optional-and-installer-owned-packages.md); [тестовый corpus и исходные проверочные сценарии](06-design-input/existing-test-corpus-and-functional-parity-gates.md).

**Сквозная прослеживаемость:** [новые source-backed функциональные требования](06-design-input/functional-requirements.md) и [тестовые идеи](06-design-input/feature-traceability.md). Изменены также [mini-game public state](01-functional/desktop-mini-games.md), [viewer actions](02-ui/context-and-sqlite-data-inspection-workflows.md) и [допустимость FP16 для выбранного GPU](02-ui/voice-controls.md).


- [Идентичность разговора: character/actor/speaker/turn/message](01-functional/dialogue-actor-and-message-identity-contracts.md) — две игровые инстанции одной личности, provenance событий, неоднозначные адресаты.

- [LLM streaming events и отображение в GUI](03-runtime/llm-stream-event-and-presentation-lifecycle.md) — started/delta/tool/usage/terminal, reasoning отдельно, buffering/flush.

## Продолжение — функциональные контракты Pass 11

- [DSL EXEC](01-functional/dsl-executable-prompt-contract.md) — prompt building, author DSL, controlled side effects.
- [POSTDSL](01-functional/post-dsl-response-rules-and-debug-state.md) — post-generation transformation and custom state.
- [MINIGAME DETAIL](01-functional/minigame-chess-seabattle-state-and-character-reactions.md) — two rulesets and game-bound character reactions.
- [ACTION HISTORY](01-functional/structured-action-history-and-compression-bridge.md) — retained requested action context across summary.
- [CORE TRIGGER](01-functional/exact-core-memory-triggers-and-session-activation.md) — deterministic story state distinct from access control.
- [MIC](01-functional/microphone-physical-identity-backends-and-monitoring.md) — physical microphone selection, monitoring and hotplug.
- [SPEECH ARBITER](01-functional/asr-speech-arbitration-and-unity-speaking-leases.md) — microphone gating against local+Unity playback.
- [EVENT ROUTE](03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md) — event fact/command/progress distinction.
- [UNITY INGRESS](03-runtime/unity-ingress-seven-actions-and-state-outcomes.md) — seven inbound Unity request families and ownership.
- [GUI ASYNC](02-ui/intent-workloads-and-visible-state-consistency.md) — freshness, exclusive side effects, refresh coalescing.
- [Синтаксическая карта producer/consumer всех объявленных внутренних событий](00-research/event-producer-consumer-callsite-index.md) — аудит прямых callsites, не доказательство runtime reachability.

## Pass 11 — дополнительные находки о достижимости и headless

- [Работа Core без GUI: реальная функциональная поверхность, readiness и ограничения](03-runtime/headless-core-functional-surface-and-readiness.md).
- [Полный статический индекс 52 асинхронных GUI-операций в 20 модулях](00-research/gui-async-operation-callsite-index.md) — только source callsites, без обещания live UI reachability.
- [Недоказанные и standalone функции: CommandParser, remote DSL resolver, GM scheduler, web/VTT, test AI](00-research/standalone-and-unproven-runtime-reachability.md) — не включать автоматически в обязательный паритет Rust Core.

- [Матрица функционального паритета 31 установочного компонента + dynamic RAG](06-design-input/installables-component-by-component-parity-matrix.md) — все статические ID и сценарии проверки, без заявленного install E2E.

- [Pass 11: детальная точка продолжения, тесты, статусы доказательств](00-research/pass11-functional-audit-handoff.md).

## Pass 12 — новые функциональные маршруты (продолжение 2026-10-31)

- [Подтверждённые QDialog и WindowManager: какие окна реально открываются](02-ui/dialog-class-reachability-and-action-outcomes.md).
- [Грубый подсчёт всех UI signal→handler соединений: 517 callsites в 75 файлах](00-research/gui-signal-registration-callsite-index.md). Синтаксическая инвентаризация, не live GUI E2E.
- [Системные file pickers, короткие текстовые вводы и область действия импортов](02-ui/native-dialogs-and-file-input-output-workflows.md).
- [Подтверждение удаления, миграции, перезаписи и отложенного применения: 29 modal-question callsites](02-ui/confirmation-and-destructive-intent-semantic-matrix.md).
- [100 Memory/RAG UI descriptor, 99 unique settings keys](02-ui/memory-rag-registered-settings-source-index.md) и [проверка ссылок на реальные потребители](00-research/rag-settings-direct-consumer-evidence-index.md).
- [Четыре встроенных RAG-пресета, сохранение Custom и проверка недостающих моделей](02-ui/rag-preset-complete-user-journey-and-model-readiness.md).
- [Graph ingestion: inline/legacy/realtime/manual batch и происхождение данных](01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md).
- [События с raw-string именами: история, экраны, loading и наблюдение изображений](00-research/raw-string-event-reachability-and-ui-bridges.md).
- [FFmpeg/7z, Python workers и Windows native loader как разные ресурсные зависимости](04-dependencies/external-executables-and-native-loader-functional-boundaries.md).

Это дополнительные source-grounded спецификации для будущей полной Rust-версии. Выбор GUI-фреймворка и целевой архитектуры оставлен на следующий этап; основной статус исследования по-прежнему `13 PRIMARY / 7 PARTIAL` из фиксированных 20 областей.

- [RAG: готовность, рестарты, поколения runtime (Pass 12)](01-functional/rag-model-runtime-readiness-and-worker-generation.md)

- [История GUI: проекция ролей, actor identity, paging (Pass 12)](01-functional/history-ui-projection-actor-identity-and-paging.md)
- [Карта тестового корпуса: 250 файлов, 2177 объявлений (Pass 12)](00-research/test-suite-static-validation-map.md)

- [Pass 12 — функциональный handoff, 14 документов, тесты, нерешённые критерии](00-research/pass12-functional-audit-handoff.md)

- [Динамические registries/imports: LLM, ASR, tools, GUI, installables, AI worker](04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md)

- [Статический индекс 24 динамических import/native loader вызовов (Pass 12)](00-research/production-dynamic-import-callsite-index.md)
