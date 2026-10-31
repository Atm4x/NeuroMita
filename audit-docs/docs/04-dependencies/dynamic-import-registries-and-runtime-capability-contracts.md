# Динамические импорты: функциональные реестры и границы Core/AI (Pass 12)

**Назначение:** доказать, почему прямой подсчёт Python `import` не даёт полного инвентаря используемых зависимостей; выявить наблюдаемые пользовательские возможности зарегистрированных, условно загружаемых и несовместимых модулей. **Не** предлагается переносить Python loader architecture на Rust.

**Основание:** исходники `CodeNow.zip`; в Pass 13 они сверены с Windows checkout releases `38172493fa0d1caf1a5225bc1c559f095f18bb7a`. Архивные результаты не заменяют runtime smoke именно этого checkout.

## Реестры, которые содержат runtime import, а не статический `import` в вызывающем файле

| CAP | Функциональная группа | Source (implementation) | Источник факта об ID | Когда импортируется | Наблюдаемый контракт |
|---|---|---|---|---|---|
| `CAP-DYNIMPORT-001`  LLM adapters | `src/managers/provider_manager.py:15-46` | `_PROVIDER_TYPES` (ChatGPT Plan, Responses, Gemini, Common) | При инициализации `ProviderManager`, каждый adapter в `try` | Успешно загруженные providers сортируются по priority; недоступные регистрируются с причиной; `generate` по requested provider name/capabilities |
| `CAP-DYNIMPORT-002`  ASR engines | `src/handlers/asr_models/registry.py:8-48` | `_ENGINE_LOADERS` (google, gigaam, gigaam_onnx, whisper, whisper_onnx) | Первый запрос `engine_class(engine_id)`, затем `lru_cache` | Пять стабильных selection IDs; неизвестный ID не создаёт recognizer |
| `CAP-DYNIMPORT-003`  Core tools | `src/managers/tools/tool_manager.py:14-103` | Lazy instances calculator, web_search, google_search, web_reader | Первый запрос schema/description/run соответствующего инструмента | Вызов отключённого инструмента не обязан грузить тяжёлую реализацию; ошибка загрузки кэшируется на lazy proxy |
| `CAP-DYNIMPORT-004`  LLM tool dialects | `src/managers/tools/dialects/registry.py:16-88` | Перебор package modules через `pkgutil.iter_modules` | При `ToolDialectRegistry` discovery | `Dialect` или `create_dialect`, нормализованные ID, aliases deepseek→openai/anthropic→openai; индивидуальная ошибка модуля не означает отсутствие прочих |
| `CAP-DYNIMPORT-005`  Static AI installable catalogue | `src/installables/registry_builder.py:13-76` | Catalog manifest с `loader_path` на группу | При статусе/операции нужной группы | Карточка доступна без импорта worker библиотеки; одна загрузка на группу; ожидание конкурентного loader; remembered failed group до reset |
| `CAP-DYNIMPORT-006`  GUI pages | `src/ui/pages/main_page_registry.py:10-56` | Семь `MAIN_PAGE_SPECS`, с module/factory | При создании main pages/по factory lookup | Семь пользовательских навигационных вкладок; регистрация factory и создание QWidget — два отдельных факта |
| `CAP-DYNIMPORT-007`  Settings sections | `src/ui/pages/settings/section_registry.py:16-189`, `src/controllers/gui/presentation_hub.py:135-154` | `SETTINGS_SECTION_SPECS`, builder `module:callable` | При подготовке секции и построении widgets | UI знает navigation spec до полной загрузки конкретного builder; updates/data_collection имеют отдельный способ разрешения |
| `CAP-DYNIMPORT-008`  Python AI worker probes | `src/handlers/ai_engine/worker_process.py:250-280` | Список `probe_modules` для запуска worker | При bootstrap конкретного окружения | Готовность среды включает успешный импорт в **AI subprocess**; это не обязательная import-зависимость Rust Core |
| `CAP-DYNIMPORT-009`  Edge-TTS/RVC adapters | `src/handlers/voice_models/edge_tts_rvc_model.py:350-417,585-608,1186,1252` | `RVC_IMPORT_CANDIDATES` одной из разных сборок | По запросу активации выбранного RVC | Несколько поддерживаемых имён модуля для ABI/packaging compatibility; наличие альтернативы не требует переписывать inference |

## Производные функциональные выводы

1. Реестр ID и availability находятся на разных уровнях. Список пяти ASR ID не означает, что все пять engines доступны в текущей машине. Аналогично 31 static installable не означает 31 загруженную реализацию.
2. Динамическая загрузка у LLM Provider и Tool Manager даёт разные failure semantics: provider unavailable сохраняется как запись причины при старте, а lazy tool кэширует ошибку при попытке использования. Для паритета важны **отображение доступности, действие пользователя и прогнозируемая ошибка**, а не использование `importlib` в новой реализации.
3. Python AI-worker bootstrap импортирует библиотеки из **своего** окружения. Эти импорты следует учитывать при проверке bundle/venv/inference dependencies и health probes, но нельзя автоматически помечать как Rust Core requirements.
4. Статический AST `import` пропускает `module_name`/`module:callable` и runtime package discovery. Поэтому прежняя классификация `84 requirements: 32 direct imports / 52 without direct import` — не эквивалент «32 реально нужны / 52 не нужны».
5. Source reachability начинается с composition root, конфигурации и пользовательского route; наличие loader registry само по себе ещё не доказывает, что конкретное условно зарегистрированное расширение вызывается в production.

## Requirements и проверка функционального паритета

- `REQ-DYNIMPORT-001`: для каждого каталога фиксировать stable ID, условия доступности, UI selection, статус и наблюдаемый failure class отдельно от способа загрузки реализации.
- `REQ-DYNIMPORT-002`: перед классификацией библиотек на Core vs Python AI учитывать динамическую загрузку, subprocess probes, native loader, install-plan dependency и packaging, не только static import.
- `REQ-DYNIMPORT-003`: отказывать или деградировать **конкретную** необязательную функцию по текущему подтверждённому поведению, не удаляя другие независимые зарегистрированные возможности из пользовательского каталога.
- `REQ-DYNIMPORT-004`: различать регистрацию GUI factory, инстанцирование GUI и фактический пользовательский вызов; не приравнивать одно к другому.

**Validation gate:** статические реестры и loader paths подтверждены исходниками; это **не** полноценная smoke-инициализация всех библиотек в изолированных Python AI environments. Не проводились Windows native DLL dependency closure и remote provider/network E2E.

**Остаток:** инвентаризировать package/module names, получаемые из manifest/runtime settings, транзитивные wheel зависимости в каждом install plan, declared feature flags, plugin dialect discovery paths и условия Core/AI deployment. См. [direct requirements ledger](full-requirements-runtime-evidence-ledger.md), [dynamic reachability](dynamic-loader-reachability-and-core-ai-boundaries.md), [external native executables](external-executables-and-native-loader-functional-boundaries.md).

## Pass 13: граница расширяемости и исполняемых языков

Дополнительно прочитаны ProviderManager registration, ToolDialectRegistry целиком, ToolManager registry callsites, GUI section preparation, AI probe bootstrap, native audio endpoint loader и safe_eval dispatcher. [24-callsite index](../00-research/production-dynamic-import-callsite-index.md) группируется по функциональному владельцу:

| Число callsites | Группа | Что выбирает implementation / functional boundary |
|---:|---|---|
| 4 | GUI section/page imports | Статические main-page/settings specs и preparation map; пользователь выбирает страницу/секцию, а не произвольный Python module |
| 2 | Provider imports | ProviderManager имеет фиксированные четыре module/class пары (Plan, Responses, Gemini, Common); package lazy export отдельно. Import failure сохраняет unavailable reason; protocol routing выбирает provider |
| 4 | Tool/builtin/dialect imports | Lazy tool module names и package exports; dialect discovery внутри `managers.tools.dialects` (две реализации openai/gemini), не arbitrary URL plugin loader |
| 1 | Installable group registry | Manifest loader_path выбирает группу под static catalog; статус/операция загружает её по требованию |
| 1 | ASR registry | Пять фиксированных engine IDs и их class paths |
| 1 | AI worker probe | Import имен `probe_modules` в отдельном Python worker; backend failure не требует запуска Python внутри будущего Rust Core |
| 3 | RVC adapters | Python model compatibility imports, включая onnx_inference/inference_onnx; inference boundary остаётся Python |
| 2 | Camera/screen optional modules | cv2 и PIL.Image; функция camera/image acquisition, не Python scripting для пользователя |
| 6 | Native DLL loaders | PortAudio/ole32 для physical endpoint identity; DXGI/CUDA inventory; user32 game window/process guard; kernel32 native paths |

Tool dialect discovery вызывает create_dialect либо Dialect, регистрирует непустой id, изолирует ошибки отдельных modules. ToolManager создаёт registry с **фиксированным package** и aliases deepseek/anthropic→openai. Это aliases формата tool messages; они не доказывают полноценный независимый Anthropic wire adapter. Поддержка добавленного разработчиком файла в этом package — возможность реализации, но публичный пользовательский plugin-install/extension lifecycle из этого не следует.

Отдельно AST-проверены **717 src modules + 14 scripts + 39 prompt_editor modules**, исключая Lib/Testing/not_used/venv/cache: parse errors 0. Прямых вызовов builtins `eval`, `exec`, `compile` в src/scripts не найдено. В prompt_editor найдено 8 прямых eval callsites в dsl_engine/dsl_runner. Это ограниченный синтаксический результат: aliases, внешние packages и вызов пользовательского интерпретатора он не исключает.

Core `safe_eval.py::eval` — **метод собственного AST visitor** (`ast.parse(mode="eval")` → разрешённые `_visit_*`), а не вызов builtin eval; Qt dialog/app `.exec`, model `.eval` и Qt SQL `.exec` также не являются исполнением Python source. Существующие expression/DSL/formula contracts можно реализовать собственным интерпретатором на другом языке; наличие Python-like syntax не доказывает обязательного embedded CPython. [DSL](../01-functional/dsl-executable-prompt-contract.md), [formula policy](../01-functional/character-custom-fields-and-formula-policy.md) и [отдельный editor preview](../02-ui/prompt-editor-authoring-and-node-workflow.md) задают разные semantics.

**Вывод ограниченного discovery:** подтверждённого пользовательского сценария «выполнить произвольный Python plugin/hook как обязательную функцию Core» не найдено. Это не обещание отсутствия любых скрытых/внешних extensions. Не включать embedded Python в будущий Core только по importlib, `.exec()` или имени eval; если такая extensibility потребуется продукту, это отдельное требование. Реальные native/managed-layer smoke gates остаются открытыми.
