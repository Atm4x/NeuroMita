# AI Hub: компонентные probes, различие ассетов и движков, допустимые операции

**Статус:** source-grounded обзор выбранных действующих семейств из `CodeNow.zip`; **не** GPU/Windows E2E. Дополняет [общую матрицу каталога](installable-catalog-and-runtime-readiness-matrix.md) деталями отдельных `status()` / `build_*_plan()`.

## Что считается компонентом

Один пользовательский пункт AI Hub — идентифицированный `category:item_id`, metadata, status и доступные операции. **Наличие карточки ещё не означает**, что ее runtime импортирован, окружение готово или модель уже выполняет inference. Эти состояния разделены как по типам, так и по владельцам (`src/core/installables/types.py:11-157`, `src/services/installable_catalog_service.py:206-316,371-614`).

| Семейство / ID | Что проверяет `status` | Что запускает install / uninstall | Граница ответственности |
|---|---|---|---|
| `backend:cpu`, `backend:cuda`, `backend:onnx` | `get_backend_service().get_status` на managed Python runtime paths; `ok` → `READY` | Пустой component plan с `required_backend`; создание среды выполняет общий installer/backend orchestrator; uninstall здесь no-op | Python AI runtime, не Rust inference |
| `dependency:ffmpeg` | Наличие `ffmpeg.exe` в resolved working root | Download/extract через `utils.ffmpeg_installer.install_ffmpeg`; clean сначала удаляет файл; uninstall удаляет exe | Внешний исполняемый media tool; есть и startup auto-install |
| `dependency:opencv` | Managed environment record **или** доступность `importlib.util.find_spec('cv2')` | Managed pip action `opencv-python==4.11.0.86 --no-deps`; uninstall требует управление optional environment layer, не удаляет core-installed cv2 | Camera capture/device enumeration, optional Python dependency |
| `voices:<short_name>` | Локальные voice files + manifest update flag | HTTP voice ZIP, распаковка в assets, stamp версии; clean/updating отличаются; uninstall remove assets | Данные конкретного персонажа, не TTS inference backend |
| `voices:all` | Агрегат числа установленных из фиксированного набора и доступных updates | Install только missing/outdated (или все при clean), отдельные progress spans; remove all | Пользовательская batch-команда; partial progress имеет значение |
| `beats:beat_this` | Beat backend snapshot `installed/available` и предпочтительный torch backend | Специальные beat install/uninstall plans | Нейросетевой backend анализа музыки; может работать CPU |
| `rag:embeddings:<slug>` / `rag:reranker:<slug>` | `model_install_status(kind,hf_id)` и required backend | Требования runtime + скачивание HF snapshot + финальная проверка | Concrete model artifact для embeddings / reranker |
| `rag:embeddings` / `rag:reranker` | Статус выбранной **эффективной конфигурацией** модели, либо «не требуется» | Install config-selected model; uninstall в текущем snapshot no-op | Active RAG settings, в т.ч. custom provider/model |

Источники: `src/core/backends/installable_component.py:18-105`; `src/installables/ffmpeg_component.py:19-145`; `src/installables/opencv_component.py:20-132`; `src/installables/voice_assets.py:40-57,140-352`; `src/game_connections/services/beat_install.py:151-199`; `src/managers/rag/install_spec.py:121-165,646-761`.

### Capability: `CAP-INSTALL-PROBE-001` — пользователь видит реальный тип ресурса

В новом приложении необходимо сохранить отличие **engine**, **model weights**, **voice asset** и **system dependency**. Установленный голос CrazyMita не означает наличие/инициализацию F5/RVC; установленный Python runtime не означает наличие HF weights; наличие файла `ffmpeg.exe` не подтверждает выполнение внешней команды (текущий status проверяет только существование). Документирует различия нынешнего поведения, не утверждает желаемый будущий probe quality.

### Capability: `CAP-INSTALL-PROBE-002` — отдельные по компоненту статусы

- **Backend component:** перезапрашивает backend через managed runtime paths, `strict_target=True` и возвращает `details` реальной проверки; runtime может быть установлен, но недоступен из неподходящего Python environment (`installable_component.py:49-88`).
- **FFmpeg:** `installed=ready=exists(ffmpeg.exe)`, `BackendKind.NONE` (`ffmpeg_component.py:58-69`). Отображение статуса доступно без запуска приложения с media payload.
- **OpenCV:** `installed=ready=managed_record OR find_spec`, без фактического импортирования cv2. Если cv2 находится в core и не управляется optional layer, отдельный uninstall недоступен (`opencv_component.py:24-36,73-129`).
- **Per-character voice:** installed files + optional remote manifest; `details.update_available` не эквивалентен `ready`. Для `voices:all` `ready=true` только если установлен **весь** набор; UI дополнительно получает `installed/total/updates` (`voice_assets.py:170-190,270-291`).
- **RAG dynamic:** concrete model card имеет уникальный ID, но `item_id` задаёт тип (`embeddings`/`reranker`) и разделяемое runtime; выбранная конфигурация допускает remote embedding provider и отсутствие локальной embedding модели при таком выборе (`install_spec.py:646-711,712-761,121-165`).
- **Beat This:** status основывается на `get_backend_status_snapshot` (installed/available) и машинно-зависимом preferred torch backend, а metadata фиксирует CPU как допустимую основу (`beat_install.py:159-195`).

### Capability: `CAP-INSTALL-ACTIONS-001` — preview/clean/update/uninstall/initialize

Общий UI предлагает предварительный план до запуска и репортит progress/result. Реализация конкретных операций различается:

| Путь | Последовательность и инвариант | Источник |
|---|---|---|
| Voice first install | `download_http` → `extract` → stamp локальной версии; затем status refresh | `voice_assets.py:68-99,192-212` |
| Voice update | Удаление archive cache, повторная загрузка, распаковка с заменой и отметка версии | `voice_assets.py:120-137,192-212` |
| Voice clean reinstall | Удаление кеша **и** имеющихся assets перед загрузкой | `voice_assets.py:101-118,192-212` |
| `voices:all` | Список `pending` только missing/outdated или все при clean; каждому голосу выделяется диапазон progress; uninstall обходит установленные | `voice_assets.py:294-348` |
| FFmpeg repair | Если существует, обычная установка no-op; clean запускает fresh install | `ffmpeg_component.py:71-139` |
| OpenCV install | Отдельный optional layer с pip и `--no-deps`, потому что NumPy/общие пакеты принадлежат core | `opencv_component.py:86-129` |
| RAG local model | Required torch/runtime requirements; HF `snapshot_download` запускается child Python subprocess с переданными paths и HF_TOKEN, process supervision с timeout/cancel, затем `model_install_status` | `rag/install_spec.py:326-425,434-643` |
| RAG aggregate status | `required_model_targets` учитывает `RAG_ENABLED`, `RAG_VECTOR_SEARCH_ENABLED`, local provider и cross encoder; конкретная модель для download берётся из эффективной конфигурации | `rag/install_spec.py:121-178,734-761` |

**User-visible различия:** «установлено», «готово», «доступно обновление», «не рекомендуется на этом GPU», «идёт загрузка», «ошибка» и «процесс модели запущен» нельзя сливать в единый флаг. Однако конкретная допустимость каждого действия должна следовать проверенному component policy, а не из предположения о «модели» как универсальном объекте.

## Обязательные функциональные требования

- `REQ-INST-PROBE-001`: разделять каталог metadata, actual component status, backend compatibility, AI worker readiness и user action; поддерживать обновление snapshot после изменений.
- `REQ-INST-PROBE-002`: поддерживать как individual voice asset selection, так и aggregate «все голоса», независимо от выбора voice engine.
- `REQ-INST-PROBE-003`: clean reinstall, update и обычный install иметь разный план; partial batch states не считать атомарной установкой всего набора.
- `REQ-INST-PROBE-004`: поддерживать активную и custom RAG model identity без hard-code всех downloadable IDs.
- `REQ-INST-PROBE-005`: ресурсы inference остаются отдельным Python AI Engine; core управляет процессами, установкой и диагностикой.
- `REQ-INST-PROBE-006`: условные требования модели определяются настройками (local/cloud vector, CE и пр.), а не всем `requirements.txt` без различия.

### Открытые функциональные проверки

Не исследованы E2E всех TTS/ASR install-plans, readiness после реального Windows restart, все контексты `status_from_installed` и error recovery install workers. FFmpeg «ready» и OpenCV «ready» в нынешних predicates являются **проверкой присутствия**, не воспроизведённым доказательством функционального запуска. Не делался выбор Rust-библиотек и не переписывались Python installers.

Связанные документы: [installable-catalog-lazy-registry-and-status.md](installable-catalog-lazy-registry-and-status.md), [installer-component-plans.md](installer-component-plans.md), [asr-rag-beat-install-plans.md](asr-rag-beat-install-plans.md), [voice-asset-distribution.md](voice-asset-distribution.md), [AI Engine](../03-runtime/ai-ipc.md).
