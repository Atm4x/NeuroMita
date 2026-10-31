# External executables and native loader surfaces: current functional contracts (Pass 12)

**Задача:** восстановить, какие операции NeuroMita выполняет с внешними процессами, DLL и бинарными утилитами, без автоматического переноса нынешних Python libraries в будущий Rust Core. Источник — `CodeNow.zip`, чтение `src` и статический поиск `ctypes`, `subprocess`, `os.add_dll_directory` в runtime-кандидатах. **Это не полная Windows DLL closure**: binaries в managed environment загружаются при установке и отсутствуют в исходном ZIP; Windows/CUDA не запускались.

## CAP-DEPS-PROCESS-001 — реально требуемые *функциональные* операции

| Операция пользователя / runtime | Внешний ресурс | Инициатор и проверяемое поведение | Граница Core vs AI |
|---|---|---|---|
| Audio media conversion | локальный `ffmpeg.exe` | `src/utils/audio_converter.py:8-62`: при вызове конвертация в WAV PCM16, 44.1 kHz, stereo; subprocess с timeout (по умолчанию 600s) и false для отсутствующего EXE/ошибки/тайм-аута | media conversion service; *не* inference |
| Auto-bootstrap FFmpeg | download ZIP с `ffmpeg.exe` | `src/controllers/gui/system_controller.py:21-62` проверяет `./ffmpeg.exe`, запускает supervised background installer; `src/utils/ffmpeg_installer.py:16-137` скачивает архив, выбирает только ffmpeg.exe и удаляет временный ZIP | installer/media dependency; conditional при использовании микрофона или voice |
| Archive extraction with optional 7z | установленный `7z`/`7za` | `src/utils/archive_utils.py:82-105,139-214,523-558`: поиск в PATH/Program Files и subprocess для password/format-specific archive, temporary staging, cancellation, terminate→kill | install/update artefact extraction; 7z не обязателен для любого ZIP |
| Model checkpoint download | отдельный Python interpreter и `huggingface_hub` | `src/managers/rag/install_spec.py:326-397` запускает isolated `python -c` для snapshot_download, передаёт `HF_TOKEN` и Python paths, передаёт статус/ошибки родительскому installer | Python AI component/managed model assets; Core orchestrates process |
| AI worker lifecycle | отдельный процесс Python | `src/controllers/ai_engine_controller.py:690-748`: shutdown control в queue, bounded wait, terminate/kill и Windows `taskkill /T /F` для process tree при заданных условиях | Core supervises; модельный inference остаётся в worker |
| CUDA/Triton compilation | Python child process, TorchInductor/Triton | `src/handlers/voice_models/compile_fish_speech.py:18-114`, `src/core/torch_compile_runtime.py`; explicit GPU/device selection and compile cache | Python inference/tooling, не библиотека Rust Core |
| UI opening Explorer | Windows `explorer` | `src/controllers/gui/home_page_controller.py:172`: открыть каталог пользователя/игры; UI shell integration | OS shell optional UI command |
| Application relaunch | новый launcher/core process | `src/utils/app_restart.py:55,99`: system restart workflow, env/arguments management | Core application lifecycle, не AI inference |

**Source caveat:** `src/utils/models_downloader.py` содержит старый Pixeldrain пример, но блоки закомментированы; не следует превращать их в действующий обязательный download contract только на основании URL. Наличие `src/scripts/Launcher.exe` в исходном snapshot не означает наличия всех бинарников дистрибутива.

## CAP-DEPS-PROCESS-002 — по смыслу различающиеся нативные API

| Surface | Источник | Контракт и условие |
|---|---|---|
| `dxgi.dll` + `nvcuda.dll` | `src/services/hardware_inventory_service.py:73-219` | физические адаптеры (DXGI) и CUDA driver ordinals (NVIDIA); CUDA DLL optional, GPU inventory не должен требовать Python inference |
| `user32` Win32 | `src/services/unity_process_guard.py:11-110` | найти окна конкретного Unity процесса и попросить graceful shutdown перед обновлением/заменой файла |
| `kernel32.GetShortPathNameW` | `src/utils/native_paths.py:13-61` | fallback короткого пути для определённых native model loaders; не ограничение всех пользовательских путей |
| `win32crypt`/DPAPI | `src/handlers/llm_providers/chatgpt_plan_auth.py:525-555` | пользовательские OAuth/session credentials; не заменяется установкой torch/onnx |
| Windows native PortAudio/WASAPI + COM | `src/infrastructure/audio/windows_endpoint_identity.py`, `services/microphone_selection.py` | physical device identity и миграция индексов backend; ASR weights/decoder отдельно |
| Torch/ONNX DLL search | `src/handlers/ai_engine/worker_process.py:188-228` | только explicit AI environment roots, `torch/lib`, `onnxruntime/capi` добавляются в native loader search path; путь `Lib/core` не должен перекрывать backend-specific DLL |
| Fish Speech compilation DLL search | `src/handlers/voice_models/compile_fish_speech.py:23-67` | Python/Torch paths + `torch/lib`; изолированная модельная операция |
| DWM visual integration | `src/utils/win_titlebar.py:51+` | оформление GUI titlebar; не функциональная зависимость LLM/AI и не требование воспроизвести PyQt-API |

## CAP-DEPS-PROCESS-003 — жизненный цикл ресурсов

Подтверждены **несовпадающие** ресурсы: файловый артефакт (`ffmpeg.exe`, model checkpoint), запущенный subprocess, загруженный DLL, открытый аудиодевайс, пользовательский credential store. Признаки `installed`, `usable`, `initialized`, `running`, `healthy` не взаимозаменяемы; installable catalog имеет свои probes. Закрытие установки UI не обязано завершить subprocess; остановка AI worker не удаляет его окружение; наличие CUDA драйвера не гарантирует, что установлен `onnxruntime-gpu` либо готова TTS модель.

Для model worker `worker_process.py:188-228` явно очищает наследуемую часть PATH от runtime roots и добавляет выбранные model-specific DLL directories; это **изоляционный функциональный контракт** актуального Python AI процесса. При будущей перестройке границы Core↔worker его необходимо либо сохранить, либо заменить другой проверяемой средой запуска. Выбор ABI, Tokio и Rust crates здесь намеренно не выполняется.

## Критерии паритета / открытые доказательства

- `REQ-EXE-001`: отправитель должен различать request/process started/terminal success/failed/cancelled и отображать причину; user-visible install state не выводится из наличия открытого log window.
- `REQ-EXE-002`: сохранять возможность конвертировать аудио, распаковывать поддерживаемые архивы, скачивать модельные checkpoints, запускать/останавливать Python workers — не обязательно теми же исполняемыми файлами.
- `REQ-EXE-003`: Windows hardware/proc/window/DPAPI native capabilities принадлежат соответствующим платформенным операциям; Torch, ONNX, CUDA models, Triton compile остаются за самостоятельной Python AI границей.
- `REQ-EXE-004`: тестовый матрикс включает отсутствие ffmpeg, optional 7z, недоступный torch/onnx DLL, GPU без CUDA, CUDA без подходящих weights, Unicode paths и subprocess cancellation.

**Ещё не выполнено:** actual `dumpbin`/Dependencies.exe graph bundled DLL, wheel transitive graph каждого managed env, PowerShell/Windows VM tests, запуск аудиоконвертации, загрузка real model weights; нет основания объявлять dependencies workstream `PRIMARY`.

**Связанные:** [Native system API](native-system-api-and-ai-library-ownership.md), [AI environments](../03-runtime/ai-environments.md), [install readiness](../03-runtime/installable-status-observation-and-invalidation.md).
