# Runtime-реестры и динамическая импортируемость: фактическая карта функциональности

**Scope:** discovery Python releases (`CodeNow.zip`, срез 2026-10-30), без выбора Rust crates. Этот документ отделяет (а) доступность в реестре, (б) загрузку Python-модуля, (в) запуск функции, (г) наличие на машине нативных runtime/dependencies. Только (в) подтверждает реально исполняемый conditional capability; отсутствие простого `import` не доказывает unused dependency.

## Метод и охват

AST `Import`/`ImportFrom` и ручной аудит обнаруженных `import_module`/`__import__`, реестров статических строк, runtime factories и worker probe. Проверено **720 файлов `src/**/*.py` за вычетом `utils/Testing` и cache-каталогов**; все прошли AST parse, без синтаксических ошибок. Этот счётчик охватывает также conditional/legacy/standalone modules: это **не** число active production-файлов. Нет исполнения реальных native/AI/network imports и не построена транзитивная closure зависимостей из installed wheels.

## Главные runtime-реестры

| Реестр / источник | Известные реализации | Когда реально загружается | Что это подтверждает |
|---|---|---|---|
| `ui/pages/main_page_registry.py:21-39` | home, news, gallery, sandbox, settings, wiki, logs — **7** main page specs | `get_main_page_factory()` или `build_main_pages()` через import_module | Определённый набор главных страниц; нет доказательства eager-создания каждой страницы при каждом запуске |
| `ui/pages/settings/section_registry.py:24-164` | general, language, api, characters, voice, microphone, ai_engine, game, models, screen, updates, data_collection — **12** | lazy section builder/UiPresentationHub; full screen mode может ограничить доступные sections | Реальные GUI-направления нельзя вывести из static PyQt imports в top level |
| `controllers/main_controller.py:299-481` → `services/runtime_features.py` | telegram, audio, local_voice, voice_models, speech, capture, reminders, embedding, reranker, graph, install, installables — **12** | Flag-enabled startup или явный `ensure`/on-demand factory | Условная доступность, DAG и state machine; не каждый service создаётся в базовом запуске |
| `installables/catalog_manifest.py:42-902` → `registry_builder.py:13-177` | **31 статическая non-RAG карточка**, 11 уникальных loader paths | При component status/settings/install через group lazy import | Карточка видима без импорта TTS/ASR/model heavy implementation; карточка≠installed≠ready |
| `installables/catalog_manifest.py:905-1059` | динамические RAG по пресетам, custom active model, 2 агрегатных install IDs | При перечислении каталога; implementation через `managers.rag.install_spec:create_rag_installable_components` | Список RAG не является статическим числом; aggregate IDs для lookup, не UI grid |
| `handlers/asr_models/registry.py:8-55` | google, gigaam, gigaam_onnx, whisper, whisper_onnx — **5** | `engine_class(id)` с lru_cache; непосредственно распознавание/установка могут быть в Python AI worker | Установка backend не доказывает загрузку ASR модели в GPU |
| `managers/provider_manager.py:15-48` | chatgpt_plan, responses, gemini, common — **4** HTTP provider classes | `ProviderManager` инициализирует provider instances, регистрирует доступные; unavailable — отдельно | Наличие preset/protocol не равно зарегистрированному исправному provider; один provider обслуживает множество пресетов |
| `handlers/llm_providers/__init__.py:5-27` | lazy `GeminiProvider`, `CommonProvider` public exports | При доступе к module attribute через `__getattr__` | Не считать deferred provider импортом, выполняемым на каждом запуске |
| `managers/tools/tool_manager.py:14-84` | 4 lazy builtin: calculator, web_search, google_search, web_reader; memory/reminder добавляет ModelController | При schema/description/run для enabled tool; error cache | Наличие `ddgs`/web client у проекта не означает загрузку search при отсутствии инструментов |
| `managers/tools/dialects/registry.py:13-70` | package discovery для tool dialect modules (`openai`, `gemini`) с alias `anthropic`/`deepseek`→`openai` | В `ToolManager` initialization, через pkgutil/import_module | Alias — выбор encoder для вызовов tools, не полноценный provider API integration |
| `handlers/ai_engine/worker_process.py:247-277` | список worker-specific `probe_modules` | В runtime preflight после dynamic `importlib.invalidate_caches` | Импортируемость модуля — health probe, не доказательство готового inference/декодирования |

## Состав installables — проверяемые статические ID

AST построил 31 `InstallableCatalogEntry(...)`, 11 loader groups:

- Backend (**3**): `backend:cpu`, `backend:cuda`, `backend:onnx`.
- TTS (**12**): `edge_tts_rvc_cuda`, `silero_rvc_cuda`, `edge_tts_rvc_onnx`, `silero_rvc_onnx`, `omnivoice`, `medium`, `medium+`, `medium+low`, `high`, `high_clf5`, `high+low`, `high_clf5+low`.
- ASR (**5**): `google`, `gigaam`, `gigaam_onnx`, `whisper`, `whisper_onnx`.
- Beat (**1**): `beat_this`.
- Dependencies (**2**): `ffmpeg`, `opencv`.
- Character voice assets (**8**): `all`, `CrazyMita`, `MitaKind`, `CappieMita`, `Mila`, `ShorthairMita`, `SleepyMita`, `GhostMita`.

Указанные ID — suffix внутри семейства; точный persisted ID имеет префикс `tts:`/`asr:`/`voices:`/`dependency:`. Dynamic RAG разрабатывает карточки из модельных пресетов плюс выбранной пользовательской модели: не суммировать их как фиксированное количество. Подробный контракт download/initialize/repair: [catalog/readiness](../01-functional/installable-catalog-and-runtime-readiness-matrix.md).

## Условные Python imports vs Rust Core requirements

Core-visible объекты можно разделить функционально:

1. **Presentation:** PyQt6/qtawesome подгружаются через main page / settings builders. Будущий Rust UI обязан сохранять функции окон, но не пакеты.
2. **Pure orchestration / application:** provider HTTP, URL/headers/credentials, очередь tools, mapping characters, game transport, settings, updater, registry. Эти функции должны быть реализованы в новом Core без Python; он не должен требовать импортов `src` только ради этих функций.
3. **Device/OS boundary:** camera/screen (`handlers/camera_handler.py:42` dynamic `cv2`, `screen_handler.py:56` PIL), sounddevice/pygame, Windows DPAPI and native installer tools. Нужны собственные native integration requirements; наличие Python wrapper не означает зависимость от того же native DLL.
4. **Python inference:** ASR engines, local TTS/RVC, embeddings/reranking, beats и их TORCH/ONNX/CUDA зависимости остаются у Python AI. Python worker **сейчас** использует некоторые `core`, `managers`, `handlers` utilities; это наблюдаемая source boundary, не допустимая зависимость нового Rust executable от старого Python Core (см. [AI worker imports](ai-worker-python-core-import-boundaries.md)).
5. **Standalone / testing / unresolved:** web/vtt/mock app, HOI4 prototype, utilities/Testing и model/dev requirements без активного entrypoint — нельзя автоматически приписывать их desktop Core либо исключать как неиспользуемые.

В выборке без `utils/Testing` найдено 14 файлов с явными программными dynamic-import call sites: `edge_tts_rvc_model`, tool dialect registry, presentation hub, screen/camera, installable registry, provider manager, page/settings registries, tools manager/builtin, ASR registry, LLM exports, AI worker. Это **не** полный перечень indirect loaders: `pkgutil`, `entry_points`, subprocess Python code strings, C extension imports и runtime `find_spec` учитываются отдельно. Один caller может иметь несколько sites.

## Контракт dynamic capabilities

Потребитель спрашивает сначала `available/declared` (метаданные/requirements), затем `load/ensure` (может запустить импорт/worker), затем `ready` (проверяет файлы/device/состояние), затем `execute` (side effect), затем `shutdown`. В коде эти состояния разделены по Registry/RuntimeFeatureManager/InstallableService/AI worker. При переносе без Python должно сохраниться **семантическое разделение**, но не строковые module names и Python callback factories. Ошибка импорта TTS implementation не должна отключать LLM, а отсутствие GPU может оставить metadata карточки видимой.

## Остаток исследования

Для окончательной матрицы необходимо собрать полную цепочку reachability `startup -> registered callback -> optional service -> dynamic import -> installed distribution` на Windows, включая native wheels/DLL, tkinter? (если есть), CUDA Runtime и окружения. Для ряда requirements без прямого import требуется доказать транзитивную необходимость или выписать в `UNRESOLVED`, а не писать `REMOVE FROM CORE` без consumer evidence. ABI/лицензии/crate alternatives сознательно не выбраны в этой функциональной фазе.
