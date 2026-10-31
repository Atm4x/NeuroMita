# Установленные AI-окружения и runtime activation

**Capability:** `CAP-AI-002`. **Статус:** CONDITIONAL: установка/активация optional AI components. Исследованы environment records/transaction/composition и worker switch, ещё не все installer plans/download/recovery/cleanup ветви.

**Источники:** `src/core/runtime_environments.py:362 CoreLayerSpec`, `:418 EnvironmentRecord`, `:453 EnvironmentTransaction`, `:534 commit`, `:631 rollback_commit`, `:673 RuntimeEnvironmentManager`, `:1674 runtime_composition`, `:1872 promote_runtime_selection`; `src/controllers/ai_engine_controller.py:1155 _switch_to_composition`, `:2139 activate_environment`, `:2369 maintenance_session`, `:2404 switch_topology`.

## Назначение и данные

Устанавливать AI dependencies отдельно от native/application core, выбирать совместимые backend layers, проверять новый runtime до публикации и восстанавливаться при неудаче. Различать installed record, selected revision, backend candidate/profile, live worker и loaded model. Их нельзя заменить одним installed=True.

Environment logical_id/category/item_id определяет компонент, revision_id — состав Python packages/layers/probes/backend/platform. RuntimeSelectionRef указывает logical+revision, слот выбирает активный компонент по назначению. CoreLayer здесь означает базовый слой AI Python (например torch/ONNX), а не будущий Rust Core — термин документации должен учитывать этот контекст.

## Физическое размещение

Lib/core — нынешние dependencies главного Python процесса. Lib/environment/bases — immutable shared backend layers; overlays/{logical}/{revision} — model/feature packages; .staging/.locks/registry.json — подготовка/синхронизация/registry. Пути override из env. Одни данные могут использоваться несколькими selected components.

Layer id зависит от group/packages/capabilities/args/Python/platform. Manifest ready не равен live model READY. Overlay содержит packages/probe modules/required_backend/capabilities. Backend-owned distributions не должны дублироваться в AI overlay; commit проверяет пересечение и отвергает его.

## Transaction и активация

EnvironmentTransaction создаёт isolated staging/site-packages, installer наполняет его, commit сканирует packages и вычисляет revision, пишет manifest, перемещает в final root через os.replace либо переиспользует existing same revision, register_installed, сохраняет snapshot для rollback. Abort удаляет staging; rollback_commit восстанавливает registration и может удалить новую revision; finalize разрешает cleanup superseded.

Transaction filesystem/registry и runtime promotion — разные стадии. Full crash recovery и гарантии cleanup ещё исследуются; нельзя объявлять весь install атомарным только из названия класса.

## Composition

Выбранные AI records формируют required capabilities по backend families. Candidate profile имеет приоритет при удовлетворении требований, затем preferred profile, затем declared layers; отсутствие compatible layer — MissingBackendLayer. Multiple authoritative layers одной family отклоняются. Paths упорядочены base layers→overlays. Probes bootstrap только для известных backend modules; произвольные overlay modules не импортируются заранее, model init проверяется service-specific validation.

## Live switch

activate_environment повторно проверяет installed record под runtime_switch_lock, строит selection_with slot, собирает composition и candidate validation set. Одновременная активация embeddings/reranker сериализуется, чтобы одна selection не затёрла соседнюю. При неизменном paths/probes и живом worker переиспользует runtime и запускает только requested validations, не перегружает все модели.

Shared switch останавливает прежний worker, создаёт candidate, проверяет readiness/model validations, promotes registry, публикует worker, очищает superseded artifacts. При отказе пытается восстановить прежний worker с прежними paths и validations; восстановление process не гарантирует восстановления всех models, UI получает model-lost signals.

Split composition создаёт candidates для изменившихся service paths, проверяет, promotes/publishes, затем останавливает заменённые workers. В отличие от shared, часть old/new процессов может существовать одновременно. Это влияет на device/VRAM management; измерений нет.

Switch gate waitable для конечной пересборки, nonwaitable для maintenance. Calls в первом случае ждут через отдельный dispatcher Future в пределах budget default60 s/не больше call timeout; owner switch не может ждать сам себя. Maintenance calls fail сразу. Shutdown aborts deferred waiters. Требуется дочитать propagation cancellation outer→inner.

## Device scheduling внутри worker

`src/handlers/ai_engine/gpu_scheduler.py` сериализует тяжёлые секции в пределах worker event loop. Priority HOT0→RERANK1→TTS2→BULK3, FIFO внутри priority через sequence. Slots default1, env override. Native function запускается to_thread с удержанием slot. Split workers имеют отдельные scheduler instances; единой межпроцессной координации эта реализация не даёт. Нельзя обещать глобальную сериализацию GPU по этому semaphore.

## Lifecycle, UI, ошибки и требования

AI Hub показывает/управляет installation/model state, runtime reset должен инвалидировать cached readiness. Конкретные actions/dialogs/plans пока не завершены. Ошибки composition/validation/registry publication различаются; rollback тоже может fail. Requirements: versioned installed identity, readiness stages, сохранение работающей selection при отказе candidate, bounded switch waiting, maintenance exclusion, explicit model-loss notifications и безопасная cleanup referenced layers.

Новая архитектура может сохранить Python env manager в самостоятельном AI runtime agent либо реализовать package supervision в Rust; сравнить после full installer audit. Требование — управляемость и независимость core от inference, не перенос текущего manifest/controller API буквально.
