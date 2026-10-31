# Контракты файловой системы, конфигурируемые пути и ограничения нативных loader

**Статус:** ACTIVE / CONDITIONAL. **Цель:** фиксировать требования к переносимости состояния/моделей и владению файловыми областями, не копируя автоматически модель `Settings/`/`Lib/` Python. Исследованы в основном функции пути, несколько потребителей и конкретные Windows loader adapter, не все legacy hard-coded paths во всей кодовой базе.

## CAP-PATH-001: четыре независимых корневых области

**Исходники:** `src/core/app_paths.py:7-93`; `src/core/runtime_environments.py:683-715`; `scripts/run.py:838-854`; `src/__main__.py:28-37`.

| Функция | Текущий источник правды | Текущее назначение и гарантия |
|---|---|---|
| `base_dir()` | `NEUROMITA_BASE_DIR` либо `Path(__file__).resolve().parents[2]` | Основа `Settings`, `Logs`, `Prompts`, `checkpoints`; override раскрывает `~` и выполняет `resolve` |
| `settings_path(...)` | `base_dir()/Settings` | Регулярные настройки/учётные данные нескольких сервисов, parent создаётся по флагу |
| `prompts_dir()` | `NEUROMITA_PROMPTS_DIR` либо `base_dir()/Prompts` | Возможность вынести пользовательские сценарии/промпты независимо от приложения |
| `checkpoints_dir()` | `NEUROMITA_CHECKPOINTS_DIR` либо `base_dir()/checkpoints` | Отдельное хранилище моделей; **относительный** override привязывается к `base_dir`, не cwd |
| `runtime_log_path()` | `NEUROMITA_LOG_PATH` либо `base_dir()/Logs/NeuroMitaLogs.log` | Один лог core, относительное значение привязывается к `base_dir` |
| `ai_worker_log_path(name)` | `base_dir()/Logs/AIWorkers/{sanitized}.log` | Наименование worker превращается в безопасный basename; не является универсальным sandbox ACL |
| Managed AI runtime | `NEUROMITA_RUNTIME_ROOT` / `NEUROMITA_CORE_DIR` / `NEUROMITA_ENVIRONMENT_DIR` | Необязательные overlays/bases/staging/locks/registry в `Lib/environment`, core packages в `Lib/core`; runtime владеет отдельной границей удаления |

`src/__main__.py:32` использует `NEUROMITA_BASE_DIR` или `Path.cwd()` для своего начального определения base; `core.app_paths.base_dir()` имеет отдельный fallback относительно файла. **Не утверждать**, что любой пользовательский запуск без environment override имеет одинаковый default path: эти источники различаются. Production wrapper `scripts/run.py:838-843` явно задаёт managed runtime vars, но в просмотренном блоке **не** задаёт `NEUROMITA_BASE_DIR`. Относительные пути зависят от контекста запуска и bootstrap; их полный path invariant требует теста на собранном дистрибутиве.

`prompt_path(configured)` имеет отдельный compatibility-resolution (`app_paths.py:45-68`): absolute path оставляет как есть, относительный путь пробует с учётом перемещённого `Prompts` каталога, удаляет устаревший ведущий сегмент `Prompts/` когда он совпадает, затем `root/candidate`, потом `base_dir/candidate`. Возвращает **первый существующий файл**; если ничего нет — первый предположительный путь для диагностики. Тесты `src/utils/Testing/test_app_paths_prompts.py` покрывают внешний `Prompts` и relative checkpoints. **Наличие теста не означает**, что он исполнялся в данном аудите.

## CAP-PATH-002: различные default пути для RAG и AI worker

**Исходники:** `src/managers/rag/install_spec.py:76-82`; `src/handlers/ai_engine/rag_runtime.py:24-30`; `src/handlers/embedding_handler.py:37-46`.

Все три fallback схемы читают `NEUROMITA_CHECKPOINTS_DIR`/`NEUROMITA_BASE_DIR`, но при их отсутствии получают `checkpoints` относительно `os.path.dirname(sys.executable)`, а `core.app_paths.checkpoints_dir()` — относительно `base_dir`. Также helper `install_spec.py` возвращает значение `NEUROMITA_CHECKPOINTS_DIR` **как есть** (без нормализации относительного пути), в отличие от `core.app_paths.checkpoints_dir()`.

**Условный риск (INFERRED):** установка модели и runtime load могут смотреть в разные каталоги при запуске под разными cwd/entrypoint/environment. На стандартной собранной конфигурации они могут совпадать; воспроизводимого дефекта без динамической проверки нет. Для нового Core требование — одна определённая модель ownership/path resolution для каждого именованного model asset, передаваемая через typed contract в Python AI Engine, а не эвристика `sys.executable` внутри inference service.

## CAP-PATH-003: Windows Unicode path compatibility внутри AI loader

**Исходники:** `src/utils/native_paths.py:13-61`, `src/handlers/asr_models/gigaam/decoding.py:18-25`, `src/handlers/asr_models/silero_vad_compat.py:12-29`, тесты `src/utils/Testing/test_asr_handler.py:180-195`.

`path_for_native_loader()` оставляет ASCII или не-Windows путь неизменённым. Для Windows Unicode пути вызывает `GetShortPathNameW` и принимает только существующий ASCII 8.3 вариант; если такого пути нет, выбрасывает `NativePathError` и рекомендует ASCII-only runtime. Эта ветвь используется **не во всём core**, а минимум в `SentencePieceProcessor.load()` для GigaAM и `init_jit_model()` для Silero VAD. В последнем случае exception преобразуется в `RuntimeError` с сообщением о несовместимости path. Поддержка Unicode в обычном Python `Path` **не гарантирует** её во всех загружаемых DLL/моделях.

**Требование:** установка NeuroMita и моделей должна диагностировать реальные native-loader ограничения, по возможности поддерживать Unicode/long paths либо явно ограничивать конкретные AI components. Rust Core не может автоматически исправить несовместимый Python/native dependency loader; путь нужно согласовать на границе AI service и протестировать на Windows с non-ASCII user profile и выключенными short names.

## CAP-PATH-004: запись логов и lifecycle

`src/main_logger.py:29-55,169-208` задаёт отдельные rotating AI worker logs (`5 MiB`, 3 backups) и основной runtime log (`10 MiB`, 5 backups), `QueueHandler/QueueListener` для async записи с fallback на synchronous handlers. `AIWorkerFileLogger` пишет отдельный файл на имя worker, ошибки/traceback отдельной строкой `DEBUG`. `QueueListener` регистрирует `atexit.stop`, однако аварийный worker exit через `os._exit(70)` в CUDA fatal policy **не обещает** нормального `atexit` flush. Подробности worker failure в [CUDA recovery](cuda-fatal-worker-recovery.md).

**Семантика:** «log record accepted by in-memory queue» ≠ «log durably written». Для диагностики recovery требуется явно различать события основного процесса и crashed worker, их correlation/trace identity и подтверждение завершения flush при штатном shutdown.

## Контракты новой реализации и открытые проверки

- `REQ-PATH-001`: user settings, prompt packs, model checkpoints, AI environments, logs и install/update staging имеют самостоятельную ownership/backup/delete политику, не зависят неявно от текущего рабочего каталога.
- `REQ-PATH-002`: допускается перенос пользовательского `Prompts` каталога, absolute/relative aliases нормализуются детерминированно, legacy prefixes мигрируют без потери ссылок.
- `REQ-PATH-003`: один canonical model asset path передаётся между installer, Rust Core и Python worker; после установки он должен удовлетворять loader-specific readiness, а не только `file.exists()`.
- `REQ-PATH-004`: non-ASCII/long/UNC Windows пути должны быть частью матрицы compatibility tests; строго фиксировать, какие ограничения обусловлены внешним native library.
- `REQ-PATH-005`: логирование сохраняет actor/process ownership, bounded retention, trace correlation и диагностику отсутствующих последних записей при аварийном завершении.

**Открыто:** полный inventory прямых `os.getcwd()/__file__/sys.executable` path heuristics, перенос исторических абсолютных путей JSON settings/character profiles, file locks и permissions/ACL для secrets; запуск release bootstrap из shell с другим cwd; реальные model loader experiments. Архитектурный стек пока не выбирается.
