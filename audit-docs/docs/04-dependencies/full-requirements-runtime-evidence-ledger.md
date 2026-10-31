# Полный реестр `requirements.txt` и происхождение потребности в зависимостях

**Фаза:** функциональный аудит, **не** исследование и утверждение Rust-crates. **Источник:** `requirements.txt:1-90` Python snapshot `CodeNow.zip`; 720 AST-разбираемых `src/**/*.py` вне `utils/Testing` и `__pycache__`; выбранные `src/scripts`/bootstrap и registry routes рассмотрены в [общем отчёте](python-import-reachability.md) и [карте dynamic loaders](dynamic-loader-reachability-and-core-ai-boundaries.md). Метод **не устанавливает transitively-needed packages** из wheel metadata и не выполняет runtime import.

## Состав списка и правило доказательства

Из 90 строк **84 объявления** зависимостей; 2 закомментированных package pin (`httpx`, `numpy`) не учитываются как объявленные отдельные пакеты, поскольку ниже есть действующие строки. Остальные четыре строки — пустые или поясняющие комментарии. Для **32** declared distributions AST обнаруживает хотя бы один соответствующий top-level import; для **52** такого импорта не обнаружено. Отсутствие прямого import не означает `LEGACY`, `unused` либо `REMOVE`: это могут быть транзитивные зависимости, bootstrap-only пакеты, динамические загрузки или зависимости внешнего инструмента. `STATIC` означает **синтаксическое вхождение**, не execution reachability. `RUNTIME` означает, что выбранный source consumer связан с реестром/активным поведением.

## 32 объявления с обнаруженным top-level import

| `requirements` строка/пакет | Контракт, который импорт обеспечивает | Scope / доказательство и предел |
|---|---|---|
| 13 `colorlog` | Форматирование цветных логов | `src/main_logger.py` — logging infrastructure, core-side |
| 16 `ffmpeg-python` | Медиа-конверсия в local voice | `src/handlers/local_voice_handler.py` — VOICE/условно; наличие wrapper ≠ необходимость именно python library |
| 30 `num2words2` | Произношение чисел в подготовке текста | `src/utils/__init__.py` — mixed Core speech text preprocessing; [подробности](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md) |
| 32 `packaging` | Сравнение установленных версий и ограничений | `controllers/install_controller.py`, `core/install_requirements.py`, `core/backends/service.py` |
| 40 `pycryptodome` (`Crypto`) | Шифрование/credential context ChatGPT Plan | `handlers/llm_providers/chatgpt_plan_auth.py`; Windows credential path относится к provider auth, не AI inference |
| 41–42 `pydantic`, `pydantic-core` | Структурированные JSON/schema contracts и config | `schemas/structured_response.py`, `schemas/sparse_structured_response.py`, `managers/character_config_manager.py` |
| 43 `pygame` | Воспроизведение и микширование аудио | `handlers/audio_handler.py` — audio Core |
| 51–52 `sounddevice`, `soundfile` | Захват/чтение/запись аудио и сервисы обработки | `handlers/asr_audio_capture.py`, `services/microphone_monitor.py`; `handlers/ai_engine/services/beats_service.py` и voice-model consumers — **mixed** |
| 53 `speechrecognition` | Облачный Google ASR adapter | `handlers/asr_models/google_recognizer.py` — conditional ASR, candidate remain Python AI |
| 54 `telethon` | Telegram user session, MTProto, voice bot media | `handlers/telegram_handler.py` — условная **интеграция Core**, не AI inference |
| 55 `tiktoken` | Оценка token budget/cost | `managers/context_counter.py` — Core context/accounting, approximation distinct from provider usage |
| 56 `tqdm` | Индикатор прогресса в ASR model handling | `handlers/asr_models/gigaam/__init__.py` — Python AI/conditional |
| 64 `dotenv` | Environment bootstrap settings | `startup/runtime_bootstrap.py` — application startup |
| 65 `pymorphy3` | Нормализация русского текста для RAG | `managers/rag/rag_utils.py` — conditional retrieval preparation; не тот же контракт, что numeric TTS |
| 67 `ddgs` | Веб-поиск как инструмент LLM | `managers/tools/builtin/web_search.py`, lazy tool registry — Core optional |
| 68 `bs4` | Извлечение текста веб-страницы | `managers/tools/builtin/web_read.py` — Core optional |
| 74 `numpy` | Векторные вычисления, аудио/model buffers | Прямые imports в **36** файлах в разных контурах; смешанная зависимость, нельзя целиком назначить в Core или AI |
| 75 `httpx` | LLM/provider networking, update/acct status | Прямые imports в **12** файлах, включая `core/networking/http_clients.py`; Core HTTP + отдельные условные потребители |
| 77 `pywin32` (`win32`) | Работа с Windows HWND/окнами | `controllers/capture_controller.py`, `handlers/screen_handler.py` и native import patterns; Windows Core/GUI |
| 78 `py7zr` | Архивы обновлений и установщиков | `release_contract.py`, `utils/archive_utils.py` — update/packaging |
| 79 `uvicorn` | Standalone web server | `web/server.py`; primary desktop entrypoint reachability **не подтверждена**, не обязательный Core без проверки |
| 81 `python-chess` (`chess`) | Правила/ходы настольных шахмат | `modules/Chess/board_logic.py`, `chess_board.py`, `engine_handler.py` — conditional mini-game |
| 83–84 `qtawesome`, `pyqt6` (`PyQt6`) | GUI, виджеты, presentation и icons | `qtawesome` **50** files, `PyQt6` **146** files; речь о функциях UI, а не наследовании Python GUI stack |
| 85 `pillow` (`PIL`) | Изображения/сжатие/capture/UI preview | `handlers/screen_handler.py`, `controllers/history_controller.py`, `ui/widgets/image_preview_widget.py` |
| 86 `portalocker` | File locking для auth state | `handlers/llm_providers/chatgpt_plan_auth.py` — Core optional account safety |
| 87 `pywinpty` (`winpty`) | Windows pseudo-terminal при установке | `utils/pip_installer.py` — install tooling/OS |
| 88 `soxr` | Ресемплинг Beat service | `handlers/ai_engine/services/beats_service.py` — Python AI internal, не вся audio subsystem |
| 89 `json-repair` (`json_repair`) | Ремонт невалидного model JSON | `utils/structured_response_parser.py` — Core LLM/response contract |
| 90 `huggingface_hub` | Получение/доступ к ASR и TTS model artifacts | `handlers/asr_models/gigaam/vad_utils.py`, `handlers/voice_models/omnivoice_model.py` — AI and conditional installer |

**Пояснение:** группы в таблице покрывают **все 32 отдельные строки**; объединённые строки (pydantic, sounddevice, GUI и т.п.) не меняют количество distributions.

## 52 объявления без обнаруженного непосредственного Python `import` в выбранной выборке

| Семейство/назначение для дальнейшей проверки | Все строки `requirements.txt` в группе | Эпистемический статус |
|---|---|---|
| Async HTTP stack, обычные low-level/network/transitive packages | 1 `aiohappyeyeballs`, 2 `aiohttp`, 3 `aiosignal`, 6 `anyio`, 7 `attrs`, 8 `brotli`, 9 `certifi`, 10 `cffi`, 11 `charset-normalizer`, 17 `frozenlist`, 19 `h11`, 20 `httpcore`, 22 `idna`, 27 `multidict`, 35 `propcache`, 46 `requests`, 50 `sniffio`, 59 `urllib3`, 60 `yarl`, 76 `h2` | `STATIC-NOT-FOUND`; **возможные** transitives или subprocess/optional. Приписывание точного parent wheel без metadata запрещено |
| Crypto/session transport-related | 36 `pyaes`, 37 `pyasn1`, 39 `pycparser`, 47 `rsa` | `STATIC-NOT-FOUND`; может потребляться текущими бинарными/сетевыми библиотеками; не объявлять лишними |
| Packaging/dev/bootstrap-related | 4 `altgraph`, 14 `distro`, 18 `future`, 25 `macholib`, 29 `nest-asyncio`, 33 `pefile`, 34 `pip`, 48 `setuptools`, 49 `six` | `STATIC-NOT-FOUND` только для `src`; сборочные/установочные скрипты и metadata требуют отдельной closure |
| Typing, parser, generic helpers | 5 `annotated-types`, 15 `eval-type-backport`, 23 `jiter`, 24 `jsonpath-python`, 28 `mypy-extensions`, 44 `python-dateutil`, 45 `regex`, 57 `typing-extensions`, 58 `typing-inspect` | `STATIC-NOT-FOUND` для перечисленных, за исключением явно оговорённого `packaging`; типично часть vendor/transitive, но не утверждать без wheel metadata |
| Другие utility/external SDK, потенциальные функции без подтверждённого ingress | 12 `colorama`, 26 `mistralai`, 38 `pyaudio`, 61 `emoji`, 62 `nodriver`, 63 `platformdirs`, 72 `pyworld`, 73 `onnx`, 80 `google-cloud-storage`, 82 `google-api-core` | `UNRESOLVED`: может относиться к старой, дополнительной или external dependency; нужен runtime/installer evidence |

**Сверка:** `packaging` (строка 32) находится только в группе с подтверждённым импортом. Требуется сопоставить runtime/package metadata, затем проверить native DLL, чтобы принять решение о переносе функции без прямой python-библиотеки.

## Что переносится в функциональные требования, а что нет

**Обязательна семантика**, а не Python wheel: Telegram login/media, LLM HTTP/streaming/auth, шахматная логика, speech capture/playback, контекстный счётчик, окна/редактор и архивная совместимость. **Не переносится inference** моделей ASR/TTS/embedding/Beat из Python AI без отдельного решения владельца проекта. Компоненты со статусом `STATIC-NOT-FOUND` нельзя ни переносить, ни удалять только по имени пакета. Вместо фиктивного dependency parity нужна таблица `runtime feature → active caller → native/system/artifact → Core/AI boundary → validation`.

**Открытые проверки:** полный `scripts/run.py` bootstrap requirements closure; `Lib/core` staging filters; dynamic imports под flags; wheel metadata/site-packages distribution requires; Windows DLL/COM/CUDA toolchain; реальные локальные модели и installs; внешний network/I/O. Из них не следует уже готовая Rust architecture.

## Дополнительная функциональная проверка `STATIC-NOT-FOUND`: package-name как данные installer, а не импорт

**Важно:** `STATIC-NOT-FOUND` измеряет только синтаксис Python `import`. В source обнаружены явные **операционные** упоминания нескольких этих пакетов. Это уточняет назначение без гадания о metadata wheel:

| Пакет в requirements без прямого import | Подтверждённая связь | Scope / что не доказано |
|---|---|---|
| `google-api-core` (строка 82) | `src/handlers/voice_models/f5_tts_model.py:300-344` — прямой элемент списка `InstallAction(type="pip")` для F5-TTS | **Подтверждён installer dependency** условного Python TTS; не самостоятельная функция Rust Core |
| `platformdirs` (строка 63) | `src/game_connections/services/beat_backend_spec.py:50-74` — явный элемент `BEAT_SHARED_PACKAGES` | **Подтверждён install-plan package**, Python Beat runtime остаётся AI/optional; не доказан Core direct import |
| `requests`, `certifi`, `charset-normalizer`, `idna`, `urllib3`, `cffi`, `pycparser` | `src/game_connections/services/beat_backend_spec.py:50-74` — пакетные элементы общей Beat-спецификации | Подтверждён **явный provisioning contract** для Beat, помимо потенциальной транзитивности; не все обязательны в core startup |
| `mistralai` (строка 26) | `src/presets/api_templates.py:30` и `src/utils/api_filters.py:64-66,150-152` содержат строковые *имена провайдера/модели* | **Не подтверждён импорт Python SDK** `mistralai`; строка `mistralai/...` не доказательство зависимости от distribution |
| `pyaudio` (строка 38) | `src/core/install_requirements.py:338` упоминает как пример optional dependency Google-ASR | Комментарий не подтверждает runtime import; сам Google recognizer и speech input проверяются отдельно |
| `nodriver`, `pyworld`, `google-cloud-storage` | Среди обследованных `src`/`scripts` не обнаружены реальные потребители вне самого `requirements.txt` | `UNRESOLVED`: отсутствие text/import не доказывает транзитивную ненужность/legacy; не включать в Rust core автоматически |

Эта запись **не превращает** оставшиеся 52 объявления в ещё одну статически импортируемую категорию: 32/52 — прежняя метрика AST. Для решений `KEEP IN PYTHON AI`, `REPLACE WITH RUST`, `REMOVE FROM CORE` требуется различать package install action, import in Python AI worker, actual Core operation и транзитивный wheel dependency. Последние без lock/wheel metadata не доказаны.
