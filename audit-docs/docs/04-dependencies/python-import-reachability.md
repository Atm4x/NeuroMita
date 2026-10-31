# Частичная матрица Python requirements и runtime-import reachability

**Дата:** 2026-10-30. **Фаза:** dependency discovery, не выбор Rust crates. Источник: `requirements.txt:1-90`, текущие Python-файлы из `CodeNow.zip`, `scripts/run.py` и активные компоненты из linked docs. **Важно:** это пока **не полная доказанная call-graph reachability matrix**: статический import AST и конкретные найденные вызовы. Он не доказывает отсутствие динамического `importlib`, plugin loading, packaging hooks, `__import__`, внешних бинарников. Python source ZIP не содержит git history; SHA указан по previous checkpoint.

## Метод и границы подсчёта

Прочитаны 720 синтаксически разбираемых `src/**/*.py` вне `src/utils/Testing`/`__pycache__` с использованием Python AST `Import`/`ImportFrom` (в т.ч. вложенные imports; AST **не** устанавливает, исполнится ли ветвь). Отдельно прочитаны `requirements.txt`, `scripts/run.py:43-93,350-387,647-778`, `handlers/ai_engine/worker_process.py` и выбранные entrypoints. Число 720 — размер выборки анализа, а не denominator активных модулей. `src` содержит также files с возможными syntax/encoding и отдельные tests; нужен отдельный parse/exclusion report до заявления полного охвата.

**Принцип:** наличие в requirements и даже import в Python Core ещё не делает библиотеку требованием Rust Core 2.0. Сохраняем функциональные требования; inference остаётся изолированным Python AI. Решения ниже — *предварительная классификация*, не автоматический выбор crate.

## Исполнение сегодня: фактическая граница установщика

- `requirements.txt:1-90` — основной Python Core requirements с GUI/сетевыми/голосовыми/переходными transitive пакетами; этот список одновременно используется bootstrap, **не** является точной архитектурной границей.
- `scripts/run.py:62-78` явно запрещает установку `torch`, `torchaudio`, `torchvision`, `onnxruntime*`, `ctranslate2`, `faster-whisper`, `f5-tts`, `fish-speech-lib`, `xformers`, Triton и ряд других AI runtime distributions в `Lib/core`; `:756-763` aborts activation при обнаружении. Следовательно, нельзя утверждать, что современная NeuroMita просто складывает все AI зависимости в core.
- `scripts/run.py:647-687` собирает core зависимость в отдельный target `Lib/core` через uv/pip; `:724-777` staging/activation/rollback. `:350-387` точечно ставит `num2words2==1.0.20` с `--no-deps` после строгой сверки версии; этот packaging detail **не** является функциональным ограничением Rust. Путь worker и layers исследован в [ai-environments](../03-runtime/ai-environments.md) и [ai-ipc](../03-runtime/ai-ipc.md).
- `handlers/embedding_handler.py:16-18` имеет type-checking imports torch/transformers, но их настоящая загрузка идёт из отдельных методов `:99-117,138-149,162-199` (в историческом Python-модуле с core-oriented name). При переписывании это кандидат на перенос в оставляемый Python AI worker, но нельзя объявлять отсутствие скрытого Python Core import без полной reachability проверки.

## Матрица контрактов по подтверждённым imports/flows

| Python dependency / family | Конкретная функция | Доказанный текущий источник | Контур | Предварительное решение и оставшееся подтверждение |
|---|---|---|---|---|
| PyQt6, qtawesome | desktop windows, Qt signal/widgets/icons | `src/ui/**`; `src/controllers/gui/**`; `src/__main__.py`; [UI inventory](../02-ui/navigation-gallery-and-help.md) | GUI / Python application | `REPLACE WITH RUST` в смысле **заменить презентационный слой**, не копировать QWidget; GUI framework comparison отдельно |
| pygame | audio playback/mixer | `src/handlers/audio_handler.py:7`; [voice output](../01-functional/voice-output.md) | Audio Core | `REPLACE WITH RUST`; сохранить playback/mixer/device semantics, лицензии и native backend отдельно проверить |
| sounddevice, soundfile, numpy | audio capture/arrays/conversion | `src/handlers/asr_audio_capture.py:13,372`, `src/handlers/audio_handler.py:54-55`, AI services | mixed Audio Core + Python AI | `REQUIRES RESEARCH`; native capture/playback в Rust, Numpy inference buffers оставить Python AI; отделить wire audio format |
| ffmpeg-python | audio conversion/transcoding pipeline | `src/handlers/local_voice_handler.py:8` | mixed core/media | `REPLACE WITH RUST` для orchestration, runtime FFmpeg/decoder binaries отдельно; не равнять py wrapper и ffmpeg.exe |
| pywin32 / winpty | Windows integration, installer PTY/DPAPI path | `src/utils/pip_installer.py:1909`; `src/handlers/llm_providers/chatgpt_plan_auth.py:19`; Windows endpoint/device source | OS + install tooling | `USE NATIVE SYSTEM API` или отдельный OS adapter; проверить конкретные win32 imports/FFI/native handles |
| portalocker | account credential store interprocess locking | `src/handlers/llm_providers/chatgpt_plan_auth.py:19` | optional account | `REPLACE WITH RUST` lock semantics, не обязательно тот же package/layout |
| httpx | LLM transport, updates, accounts | `src/handlers/llm_providers/http_transport.py`, `src/updater.py:28` | Core networking | `REPLACE WITH RUST`; typed timeouts/stream/cancel/error from [provider protocols](../03-runtime/openai-protocol-state-machines.md) |
| telethon | Telegram voice/auth/messages | `src/handlers/telegram_handler.py:2-10`; [telegram flow](../01-functional/telegram-voice.md) | conditional integration | `REPLACE WITH RUST` или protocol adapter; MTProto semantics проверять отдельно; не inference |
| ddgs, bs4 | web search/page extraction tools | `src/managers/tools/builtin/web_search.py:4`, `web_read.py:5` | optional tools | `REPLACE WITH RUST` при сохранении search/html extraction behavior, external limitations отдельно |
| python-chess | chess game rules/AI engine bridge | `src/modules/Chess/board_logic.py:2` | optional desktop game | `REPLACE WITH RUST`/`REIMPLEMENT SMALL FUNCTION` **после** восстановления полного chess rule contract |
| pydantic / pydantic-core | structured responses, settings validation, character configs | `src/schemas/{structured_response,sparse_structured_response}.py`, `src/managers/character_config_manager.py:10` | Core contracts | `REPLACE WITH RUST` typed schema/validation; не смешивать coercion/repair и strict deserialization |
| json-repair | invalid structured JSON recovery | `src/utils/structured_response_parser.py:269` | LLM pipeline | `REIMPLEMENT SMALL FUNCTION` либо специализированный parser; сохранение эвристик — по fixture tests |
| pymorphy3 | RU morphology normalization for RAG query | `src/managers/rag/rag_utils.py:64-65` | conditional RAG query preprocessing | `REQUIRES RESEARCH`: качество лемматизации/словоформ и native morphology/DB dictionaries; нельзя назвать готовым Rust analog без сравнения |
| numpy (other Core paths) | vectors, cosine, FTS, RAG, graphs | `src/managers/rag/**`, `src/controllers/embedding_controller.py:8` | Core data algorithm + AI worker boundary | `REPLACE WITH RUST` для vector arithmetic; **не** переносить inference Torch в Rust только из-за NumPy buffers |
| torch, transformers, onnxruntime, torchaudio, TTS runtimes | embedding/ASR/TTS/RAG/beat inference | `src/handlers/ai_engine/**`, `src/handlers/asr_models/**`, `src/handlers/voice_models/**`; [AI IPC](../03-runtime/ai-ipc.md) | AI inference | `KEEP IN PYTHON AI`, установить независимый worker wire protocol; runtime/loader code может ещё импортировать Python Core helpers |
| soxr | AI Beat Service resampling | `src/handlers/ai_engine/services/beats_service.py:421-423` | Python AI beat engine | `KEEP IN PYTHON AI` при неизменённой inference pipeline; Rust audio requirements отдельно |
| tiktoken | token estimate/context display | `src/managers/context_counter.py:27-31` | Core context budget | `REPLACE WITH RUST` или `REIMPLEMENT SMALL FUNCTION` с валидируемой ошибкой приближения; fallback heuristic уже существует |
| num2words2 | spoken numbers/text transform | `src/utils/__init__.py:18,316-446` | speech text preparation | `REQUIRES RESEARCH`: language-specific numeral declensions и current scope уточнить |
| dotenv / platformdirs | environment/config/bootstrap/data path | `src/startup/runtime_bootstrap.py:298` и path/config modules | Platform and configuration | `REIMPLEMENT SMALL FUNCTION`/OS adapter; раздельно определить env input and filesystem paths |
| py7zr | archive/install/release extraction | `src/release_contract.py:112`; `src/updater.py`, [launcher](../01-functional/launcher-and-updates.md) | updater/packager | `REPLACE WITH RUST` or external extractor; сохранить archive formats/security/rollback semantics |
| uvicorn | standalone HTTP VTT/mock | `src/web/server.py:4`; [standalone web](../01-functional/standalone-web-surface.md) | standalone/experimental | `REMOVE FROM CORE` **пока только кандидат**: production reachability не подтверждена; поддерживать лишь при доказанном требовании |
| SpeechRecognition, PyAudio | remote Google ASR adapter + legacy audio | `src/handlers/asr_models/google_recognizer.py:65-95`; `requirements.txt:38,53` | conditional ASR | SpeechRecognition `KEEP IN PYTHON AI` в существующем engine; PyAudio direct usage в просмотренных Python imports не обнаружен, но transitive/runtime нуждаемость **UNRESOLVED** |
| nodriver, mistralai SDK, pyworld, google-cloud-storage | присутствуют в requirements, прямых AST imports в выборке нет | `requirements.txt:26,62,72,80` | unknown/conditional/transitive | `REQUIRES RESEARCH`, **не объявлять unused** из-за динамического import/subprocess/dependency |
| aiohttp, requests и прочие сети | requirements и потенциальные transitive deps | `requirements.txt:2,46` | unknown | `REQUIRES RESEARCH`; отсутствие прямого AST import в исследованной выборке не доказывает неиспользование |

## Нерешённые вопросы и критерии перехода в CONFIRMED

1. Полная closure `startup → dynamic import/registry → modules`, включая lazy installables (`src/installables/registry_builder.py`), settings-driven imports, submodule/standalone apps и platform-dependent ветви. AST показал 720 parsed, но не устанавливал reachability.
2. Distribution-level graph из requirements/lock/wheels/metadata; package name не всегда совпадает с import top-level (`pillow→PIL`, `python-chess→chess`, `json-repair→json_repair`, `pywin32→win32*`).
3. Разделить `CURRENT CORE`, `CURRENT OPTIONAL PYTHON SERVICE`, `TARGET RUST CORE`, `TARGET PYTHON AI`, `build/dev/transitive`, особенно для shared Python core helpers и model bootstrapping.
4. Русская морфология и произношение чисел: проверить реальные text fixture sets и quality, прежде чем выбирать библиотеку. Это один из потенциально нетривиальных functional replacements.
5. Реальная поддержка native crates, licensing, Win dependencies, и maturity **не проверялись в этом проходе**; не выдавать эти строки за готовую Rust dependency matrix.

**Инвариант:** фактический import — доказательство технического использования в нынешнем source, но не доказательство, что новая система обязана использовать ту же dependency. И наоборот, отсутствие прямого import не является доказательством неиспользования.
