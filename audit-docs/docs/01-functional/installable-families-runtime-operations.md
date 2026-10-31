# Устанавливаемые компоненты: полная номенклатура и операции по семействам

**Цель.** Не выбирать библиотеки Rust и не переносить нынешние Python-классы, а реконструировать фактические пользовательские возможности `AI Hub → management runtime` для каждого семейства: обнаружить компонент, увидеть совместимость/готовность, предварительно рассчитать действия, установить, удалить, переключить/инициализировать.

**Baseline:** локальные исходники поставленного `CodeNow.zip` (без `.git`, поэтому не приписывать архиву достоверный commit SHA). **Статус:** статически подтверждены регистрация, точки status/plan и состав основных операций; не запускались сеть, CUDA, Python model worker, реальные pip/install/uninstall и Qt UI.

## CAP-INSTALL-COVER-001 — каталог, identity и lazy resolution

`src/installables/catalog_manifest.py:42-904,906-1042` содержит **31 статический non-RAG ID**, сгруппированный ниже. Динамические RAG cards добавляются из model specs, в то время как агрегаты `rag:embeddings` и `rag:reranker` включены в `catalog_by_id` для lookup, но не в пользовательскую сетку (`:949-1035`). Все разделы представлены `ComponentCategory` (`src/core/installables/types.py:11-18`), а состояния — `unknown/not_installed/installed/ready/needs_reinstall/backend_missing/failed` (`:21-28`). Это больше, чем двоичная installed/uninstalled модель.

| Family | Точные ID | Число | Loader / основной источник |
|---|---|---:|---|
| AI backend | `backend:cpu`, `backend:cuda`, `backend:onnx` | 3 | `src/core/backends/installable_component.py:18-106` |
| TTS Edge/Silero + RVC | `tts:edge_tts_rvc_cuda`, `tts:silero_rvc_cuda`, `tts:edge_tts_rvc_onnx`, `tts:silero_rvc_onnx` | 4 | `src/handlers/voice_models/edge_tts_rvc_model.py:346-606,1182-1295` |
| TTS OmniVoice | `tts:omnivoice` | 1 | `src/handlers/voice_models/omnivoice_model.py:40-229,232-319` |
| TTS Fish Speech | `tts:medium`, `tts:medium+`, `tts:medium+low` | 3 | `src/handlers/voice_models/fish_speech_model.py:47-517,520-716` |
| TTS F5 | `tts:high`, `tts:high_clf5`, `tts:high+low`, `tts:high_clf5+low` | 4 | `src/handlers/voice_models/f5_tts_model.py:79-457,459-643` |
| ASR | `asr:google`, `asr:gigaam`, `asr:gigaam_onnx`, `asr:whisper`, `asr:whisper_onnx` | 5 | `src/handlers/asr_handler.py:291-343`; `src/handlers/asr_models/speech_recognizer_base.py:60-407` |
| Beat | `beats:beat_this` | 1 | `src/game_connections/services/beat_install.py:24-199` |
| External dependency | `dependency:ffmpeg`, `dependency:opencv` | 2 | `src/installables/{ffmpeg_component,opencv_component}.py` |
| Character voice assets | `voices:all`, `voices:CrazyMita`, `voices:MitaKind`, `voices:CappieMita`, `voices:Mila`, `voices:ShorthairMita`, `voices:SleepyMita`, `voices:GhostMita` | 8 | `src/installables/voice_assets.py:47-58,140-357` |
| **Итого** | **31 статический компонент** | **31** | `catalog_manifest.py` |

В дополнение: `rag:embeddings` и `rag:reranker` — агрегатные `lookup` ID; `rag:embeddings:<slug>` / `rag:reranker:<slug>` — динамические cards отдельных HF-моделей из пресетов и активных custom choices (`src/managers/rag/install_spec.py:646-789`, `catalog_manifest.py:906-1040`). Число RAG cards **не константа** и зависит от конфигурации, поэтому `31` — только static non-RAG denominator.

`src/installables/registry_builder.py:13-154`: метаданные разрешаются без heavy model import, а реализация лениво импортируется группой loader. Сбой загрузки кэшируется на уровне группы до invalidate; `get` может вернуть `None`, `require` — выбросить ошибку. Отдельно различать `catalog_card_exists`, `implementation_resolved`, `backend_environment_ready` и `component_runtime_ready`. Смена модели или reinstall не означает немедленно актуальный instance; invalidate и refresh разделены.

## CAP-INSTALL-COVER-002 — неэквивалентные операции семейств

| Family | Что означает status | Install operation | Uninstall operation | Initialize / activate |
|---|---|---|---|---|
| AI backend | Проверка managed runtime environment, путей Python и health backend | План с `required_backend`, фактическое развёртывание runtime — отдельный environment manager | Explicit noop: backend managed separately | `None` (runtime определяется через environment/topology) |
| Edge/Silero + RVC | Конкретный model id, runtime package, backend, assets | Python dependencies + RVC runtime assets, conditional patch, final validation | Per model plan на owned assets/packages | Модель загружается в AI worker при выборе; CUDA vs ONNX различаются |
| Fish Speech | `medium/medium+/medium+low`, зависимости/веса и flags варианта | Python env, модельные assets; `medium+` добавляет Triton compilation path, `medium+low` ещё RVC | Per variant plan | Отдельный compile/initialize путь, в том числе optional прогрев |
| F5 | Русский / Cross-Lingual, с optional RVC | Python env, веса модели, vocoder, optional RVC; final installed check | Per variant plan | AI runtime model initialization |
| OmniVoice | Общий `omnivoice`, артефакты + runtime requirements | pip + HF snapshot + final validation | Явный model-owned uninstall | AI worker lazy initialization |
| ASR | `is_installed` + backend health, динамическая настройка устройства и модели | `pip_install_steps`, затем `download_http` или `call_async(install)` + `is_installed` check | Per-engine uninstall packages/paths | Base initialize plan `None`; actual recognizer init отдельно |
| Beat This | Backend-specific availability/runtime paths | Pip dependencies + validation; выбор `DSP`/`librosa` существует и вне каталожной карточки | Для Beat This — pip removal; DSP/другие — noop | Runtime selection; у карточки initialize noop |
| FFmpeg | File/process-backed installed predicate | Скачать/разместить внешние executable assets | Файловое удаление собственного набора | `None` |
| OpenCV | Managed pip record или runtime `cv2` | Python package в optional managed environment | Ownership у managed environment, не удаление из общего Lib | `None` |
| `voices:<name>` | Есть ли bundle, есть ли обновление по удалённому manifest | Отдельные download ZIP + extract + stamp version | Remove owned assets | `None`: assets, а не работающая модель |
| `voices:all` | Количество установленного/обновляемого среди семи | Только missing/obsolete, либо все при clean; последовательный pipeline | Удаляет установленные из семи | `None` |
| RAG aggregate | Требуется ли model при текущих настройках; packages и HF cache отдельно | Selected model, model artifacts + optional Python packages | В поставленном коде noop; physical removal не подтверждён | `None`; фактическая готовность проверяется query worker |
| RAG explicit | HF model identity + shared kind (`embeddings`/`reranker`) | Устанавливает указанную модель, независимо от selected | Текущий noop | `None` |

В таблице статус `uninstall` обозначает **существование команды и её характер**, а не гарантию физического удаления. `build_initialize_plan` и runtime `initialize()` не одно и то же. Подробное фактическое поведение см. [ASR/RAG/Beat](asr-rag-beat-install-plans.md), [voice/media планы](installer-component-plans.md), [статусы](../03-runtime/installable-status-observation-and-invalidation.md).

## CAP-INSTALL-COVER-003 — пользовательские инварианты

1. **Identity:** статическая карточка `backend:cuda` описывает Python AI runtime, не обязательный backend Rust Core; `tts:edge_tts_rvc_cuda` и `tts:edge_tts_rvc_onnx` — разные модели с разным кодом исполнения, даже если показывают похожее название.
2. **Каталог ≠ установлено:** метаданные доступны до импорта heavy model modules. `status` может завершиться отдельно от построения самой карточки.
3. **Установлено ≠ готово:** наличие пакетов, весов, возможность инициализации и выбранность текущим персонажем — четыре самостоятельных обстоятельства.
4. **Запрос ≠ результат:** предпросмотр плана, принятие в FIFO-очередь, процесс установки, post-install check и readiness status не объединять в один boolean. См. [очередь](../03-runtime/install-operation-admission-queue-and-completion.md).
5. **Условная доступность:** CUDA/NVIDIA, ONNX/DirectML, необходимость локального RAG, optional RVC и пропуск already-installed зависят от hardware/configuration; отсутствие installed component не обязательно отключает весь продукт.
6. **Семантика управления:** `clean`, `update`, `uninstall`, `initialize`, `switch engine`, `force refresh` имеют разную область побочных эффектов.
7. **Граница AI:** требования Python distributions, CUDA и HF assets относятся к управляемому Python AI Engine; их регистрация в installable catalog не означает их обязательность для нового нативного Rust Core.

## Уточнение статуса покрытия

В этом проходе все **31 статических ID** сопоставлены с точными implementation families и operation contracts; **полный runtime E2E каждого компонента не проведён**. Это закрывает статический каталог и семейную типологию, но не закрывает критерий реальной установки/готовности. Для architecture stage требуется формальная матрица per-component fixture: machine backend, settings, artifacts, status, plan, cancel, result, runtime activation, uninstall, recovery. В данном документе нет попыток выбирать целевые библиотеки Rust.
