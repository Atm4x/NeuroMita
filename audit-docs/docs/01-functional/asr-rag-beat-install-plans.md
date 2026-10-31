# Установка ASR, RAG и Beat Sync: детальные компонентные контракты

**Статус:** `CONDITIONAL`, engine/backend/settings dependent. **Источник:** Python `CodeNow.zip` (историческая привязка `releases/38172493` из checkpoint; ZIP без Git history). **Режим:** static implementation audit; без реальной установки, загрузок, моделей, GPU, API-запросов или запуска приложения. Продолжает [общий аудит](installations.md) и [voice/media планы](installer-component-plans.md).

## Capability: CAP-INSTALL-003 — ASR runtime и веса моделей

### Регистрация и пользовательский сценарий

`src/handlers/asr_models/registry.py:8-51` лениво регистрирует **ровно пять engine id**: `google`, `gigaam`, `gigaam_onnx`, `whisper`, `whisper_onnx`. `src/handlers/asr_handler.py:257-343` создаёт recognizer по ID, управляет сменой активного instance и экспортирует installable catalog; `:291-329` формирует install ctx из GPU/device/`NEUROMITA_LIB_DIR`, а неизвестный engine выражается как заведомо провальный `call`-plan, не как exception при его построении. Настройки конкретного engine применяются при смене/сохранении. `get_settings_schema` расширяет схему информацией о hardware (`:345-364`).

Общий installer `src/handlers/asr_models/speech_recognizer_base.py:177-285`:

1. Создаёт runtime ctx и применяет settings (exceptions в apply на этом шаге подавляются).
2. Если `status(ctx).ready` и не `clean` — zero-action `already_installed`.
3. Преобразует `pip_install_steps` в последовательные `InstallAction(type='pip')`.
4. Если `install_manifest()` непуст — `download_http` для model files. Если пуст — `call_async(self.install())`; это **разные ветви с разными проверяемыми исходами**.
5. После установки `is_installed` используется как final-check; отрицательный результат сопровождается диагностикой missing requirements/files (`:246-313`). Required backend прикреплён к plan отдельно от actual readiness.
6. `build_uninstall_plan` использует engine-specific `uninstall_pip_packages` и `uninstall_paths`; общие пакеты намеренно не удаляются, paths удаляются с подавлением IO errors и шаг может вернуть `True`, даже когда файл физически остался (`:315-382`). `build_initialize_plan` у базового интерфейса пустой; реально `init` — отдельный runtime lifecycle (`:384-405`).

### Конкретная матрица пяти ASR engines

| ID | Подтверждённый runtime/install contract | Источник | Ограничения |
|---|---|---|---|
| `google` | CPU, `SpeechRecognition`, `sounddevice`, `silero-vad`; remote recognizer, без локальных model files | `asr_models/google_recognizer.py:65-104` | Установка Python модуля ≠ доступность удалённой службы |
| `gigaam` | Torch preferred backend, hydra/omegaconf/sentencepiece, VAD/audio; `.ckpt` и (для некоторых моделей) tokenizer, существует список допустимых моделей | `gigaam_recognizer.py:58-59,164-246` | `is_installed` проверяет pip/backend и обязательные ненулевые model files (`:207-227`) |
| `gigaam_onnx` | ONNX backend плюс `onnx` python module, model checkpoint/tokenizer pipeline, export tooling | `gigaam_onnx_recognizer.py:145-221` | **`is_installed` проверяет только requirements**, не `install_manifest` и не валидность checkpoint (`:195-202`) |
| `whisper` | Faster-Whisper/CTranslate2, модельный repo и явный набор файлов, выбранный model/device | `whisper_recognizer.py:179-195,248-332` | `is_installed` требует ненулевые файлы и requirements (`:275-300`); uninstall исключает общие пакеты, удаляет model root (`:317-325`) |
| `whisper_onnx` | ONNX backend, optimum, transformers, YAML, VAD/audio; config/tokenizer/preprocessor + encoder/decoder ONNX parts | `whisper_onnx_recognizer.py:139-229` | required files перечислены в `requirements()`, значит `is_installed` проверяет их посредством common requirement engine (`:193-200`) |

**Подтверждённый статический инвариант с нарушением:** `GigaAMOnnxRecognizer.is_installed` отвечает «установлен» при выполненном Python requirements, даже если выбранные модельные файлы отсутствуют, поскольку manifest создаётся, но не проверяется в predicate. Это может дать `already_installed` без download action через `SpeechRecognizerInterface.build_install_plan`. Это несогласованность проверок **по исходникам**, не динамически подтверждённая регрессия. Проверить отдельным unit fixture: удовлетворить requirements через fake checker, оставить model path пустым и сравнить predicate/plan.

### Состояния/сбои и требования

`Discovered → settings validated? → requirement probe → already-installed | plan → pip steps → download/async fallback → validate → installed → init → ready → transcribe → cleanup`. Промежуточные ошибки: недоступный backend, отсутствующая модель, сломанный внешний Python пакет, загрузка с 404, cancel, timeout, partial file, ошибка subprocess inference. Приоритет Rust Core: размещение Python AI environments, статусы и управления worker, **не портирование ASR inference**.

`REQ-ASR-INSTALL-001`: `installed (packages)`, `artifacts_present`, `initialized`, `recognition_ready` — разные поля состояния для каждого engine/model variant. `REQ-ASR-INSTALL-002`: `clean` не допускает early already-installed; final predicate включает полный набор обязательных файлов выбранной версии. `REQ-ASR-INSTALL-003`: uninstall только owned artifacts/exclusive packages, с verified outcome, не считать подавление ошибок завершённым удалением.

## Capability: CAP-INSTALL-004 — RAG модель по активным настройкам или по каталогу

### Кто определяет, нужны ли модели

`src/managers/rag/install_spec.py:31-178`: `TARGET_EMBEDDINGS`, `TARGET_RERANKER`, `TARGET_CURRENT`; active targets вычисляются из `RAG_ENABLED`, `RAG_VECTOR_SEARCH_ENABLED` + local embeddings provider, `RAG_CROSS_ENCODER_ENABLED` + выбранный CE model. `missing_model_targets` специально смотрит только отсутствующие model artifacts, а не весь Python runtime (`:145-165`). Поэтому **RAG включён ≠ обе локальные модели обязательны**.

`install_spec.py:210-305`: требуются Torch preferred backend + transformers/huggingface-hub; `bitsandbytes` нужен **только** при INT8 reranker, NVIDIA и не-LM reranker. `get_install_status` проверяет наличие **директории-кэш-маркера** для model ID, плюс Python/backend requirements. Наличие директории само по себе не доказывает полноту weights — это слабый file predicate, а не модельный health probe. Runtime `ensure_runtime_ready` пересобирает worker-ctx и выбрасывает ошибку, если status плохой (`:308-323`).

### Два разных сценария установки

1. **Settings-driven** `build_install_plan(target)` → разрешение active embedding/reranker → пакеты → optional INT8 packages → huggingface snapshot download `repo_id` → final status (`install_spec.py:434-516`). При выключенном/не требуемом target возвращается `already_installed_status='Not required'`, что не означает наличие модели.
2. **Model-specific** `RagModelInstallableComponent(kind,hf_id)` → уникальный component id на модель, но общий `item_id` по виду (`embeddings`/`reranker`) → installer устанавливает ровно указанную HF model, независимо от текущей selected model (`install_spec.py:530-709`). Каталог включает агрегатные cards + model-specific, а custom selected specs добавляются условно (`:764-789`).

`_snapshot_download_action` запускает из управляемого Python interpreter `huggingface_hub.snapshot_download` с нужными Python paths/HF_TOKEN, stdout через pipe, process cancellation hook через `pip_installer`, общий deadline с ≤24h промежуточными waits для Windows (`install_spec.py:326-431`). Python subprocess здесь downloader, а не обязательный Rust Core dependency. Upload/progress UI не обязан интерпретировать `progress=65..99` как байты реально загруженной модели.

### Удаление и риски

Оба `RagModelInstallableComponent.build_uninstall_plan` и `RagInstallableComponent.build_uninstall_plan` сейчас **возвращают noop `RAG uninstall is not implemented yet.`** (`install_spec.py:705-706,757-758`). Это не реализованное удаление RAG weights или shared packages. Следует учесть как `UNIMPLEMENTED` для фактической операции uninstall, несмотря на наличие кнопки/контракта в каталоге; UI нельзя выдавать noop за physical deletion. Не нужно переносить заглушку в новый Core как целевое поведение.

`REQ-RAG-INSTALL-001`: различать optional/not-required, installed artifacts, checked deps и worker-ready. `REQ-RAG-INSTALL-002`: selected-model install и explicit-model install не подменяют друг друга; component identity ≠ shared runtime identity. `REQ-RAG-INSTALL-003`: uninstall model из каталога имеет проверяемое фактическое удаление owned assets; noop явно заявляет неподдерживаемость.

## Capability: CAP-INSTALL-005 — Beat Sync backend plan

`src/game_connections/services/beat_install.py:24-149` поддерживает выбор `DSP`, `librosa`, `beat_this`. DSP является встроенным режимом и не требует установки/инициализации. Для librosa/beat_this `status` gate → pip package list от `beat_backend_spec` → runtime validation. Torch kind только для Beat This. Uninstall определён для **Beat This** (`beat-this`, `rotary-embedding-torch`, `einops`, `tqdm`), для остальных возвращает no-op (`:86-115`); необходимо выяснить фактическую совместимость удаления shared Python packages. Explicit initialization plan отдельно вызывает `_initialize_beats_service` и `_backend_ready`, но `BeatThisInstallableComponent.build_initialize_plan` возвращает `noop_plan`, так как runtime selection владеет инициализацией (`:117-199`). 

Регистрация `create_beat_installable_components()` создаёт **только карточку Beat This**; `librosa` и DSP остаются поддерживаемыми выборами backend и действиями `start_beat_install`, но не обязаны иметь самостоятельные catalog cards (`:198-225`). `REQ-BEAT-INSTALL-001`: доступность DSP, установленность библиотеки, выбранность backend и готовность runtime — независимые состояния. `REQ-BEAT-INSTALL-002`: registry содержит проверенную explicit cardinality, не выводить список поддерживаемых backend из числа карточек каталога.

## Ограничения проверки и дальнейшие тесты

- Все source line ranges относятся к поставленной версии; при новой git revision сверять заново.
- В этом исследовании не запускались ASR inference, HTTP/HF download, pip, GPU backend, remove или production GUI.
- Тестовая матрица: все пять engines, CPU/NVIDIA/ONNX, partial model files, cold init, hidden metadata requirements, clean, cancel/timeout, wrong model ID; RAG active/explicit/no-target, INT8 variants, stale marker, failed snapshot, uninstall noop; Beat built-in vs installed, runtime selection, shutdown.
- Неисследованные границы: весь `core/install_requirements` на уровне per-platform probes, real downloadable SHA, lifecycle installer queue при убийстве процесса; полный `beat_backend_spec`/worker инсталляции, все custom ASR model distributions и remote license facts.
