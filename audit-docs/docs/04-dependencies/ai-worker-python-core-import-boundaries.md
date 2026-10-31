# AI Engine → Python Core: реальный import graph и будущая граница Runtime

**Ревизия:** локальный `CodeNow.zip` (история говорит `origin/releases`, точный SHA без `.git` независимо не подтверждён). **Статус:** `ACTIVE/CONDITIONAL` — service `rag` лениво запускается при обращении; headless/inprocess путь отдельный. Здесь исследуется текущая Python-import зависимость, а не Rust architecture design. AI inference по условию проекта остаётся Python.

## CAP-AI-BOUNDARY-001 — worker RAG исполняет не только AI-only Python код

`src/handlers/ai_engine/worker_process.py:786-804` динамически загружает зарегистрированный сервис `rag` из `handlers.ai_engine.services.rag_service`. `RAGService.handle` (`services/rag_service.py:13-83`) обслуживает `ping`, `warmup_embeddings`, `warmup_reranker`, `get_embeddings`, `rerank`, `get_reranker_status`, используя приоритетный scheduler. Это подтверждённый путь вызова через AI worker, а не просто мёртвый импорт.

Внутри `RAGService._warmup_embeddings_sync` / `_get_embeddings_sync` (`rag_service.py:112-153`) выполняются **динамические** импорты `handlers.embedding_handler.EmbeddingModelHandler` и `managers.rag.install_spec.ensure_runtime_ready`, а `WorkerCrossEncoderReranker._ensure_loaded` (`src/handlers/ai_engine/rag_runtime.py:90-136`) импортирует `managers.rag.install_spec`, `managers.settings_manager.SettingsManager`, `torch`, `transformers`. `managers.rag.install_spec:1-28,76-137` сам импортирует `core.backends`, `core.events`, `core.install_requirements`, `core.install_types`, `core.installables`, `handlers.embedding_presets`, `managers.rag.pipeline.config`, `utils`, а также optional SettingsManager; значит, worker dependency closure шире `torch/transformers/inference`. В текущем Python layout эти модули доступны, но при переходе core на Rust нельзя механически удалить их все из Python процесса.

`src/handlers/embedding_presets.py:11-28,130-...` получает `core.app_paths.settings_path` и пытается импортировать `managers.settings_manager.SettingsManager`, а при недоступности определяет fallback returning defaults. Это **не** доказательство правильной runtime конфигурации без менеджера: default path и фактический выбор модели в таком случае могут отличаться. Настройки и resolved model id должны стать явными данными на границе.

## CAP-AI-BOUNDARY-002 — два противоположных пути зависимостей

- `Core → AI` (`src/handlers/ai_engine/rag_client.py:6-23,39-96`): клиента через `core.services.use(AIEngineService)` и `engine.call('rag', method, payload)` ожидает `future.result(timeout)`. Это broker/adaptor текущего Core, не обязательная часть Python AI нового приложения. Payload содержит texts, model_name, prefixes, batch_size и hot/bulk priority; `rerank` — query/candidates/top_k/alpha/early_exit_score/total_candidates.
- `AI → legacy Core helpers` (выше): worker использует Python `install_spec`, `settings_manager`, `embedding_presets`, `core.app_paths`, GPU/provider checks и logger. Здесь требуется решить, какие из них inference-local pure helpers, а какие используют настройки/установки нового Rust Core.
- `Headless in-process` (`src/handlers/ai_engine/inprocess_engine.py:105-127`): отдельно регистрирует `InProcessAIEngine` в process-wide `core.services` для headless и выполняет те же sync RAGService methods внутри текущего процесса. Это доказанный альтернативный runtime mode, который нужно отдельно классифицировать, а не автоматически переносить на Rust. Динамическая reachability через test helpers возможна; production entrypoint для каждого сценария требует дополнительных подтверждений.

## Статусы, side-effects, риски

RAG workers пользуются управляемым runtime layer и `site.addsitedir` / `.pth` activation (`src/handlers/ai_engine/worker_process.py:65-135`), а `get_embeddings` может выбирать hot приоритет. `ensure_runtime_ready` — локальный readiness check AI model/runtime; текущий код может читать файловую систему, системные настройки, installables. Простое сохранение wheel `torch` и Python inference source не гарантирует сохранение init/paths/settings и модели.

Источники различаются: `_checkpoints_dir` в `rag_runtime.py:24-31` зависит от `NEUROMITA_CHECKPOINTS_DIR`, `NEUROMITA_BASE_DIR` и `sys.executable`; `install_spec.py:76-85` использует похожие правила, но независимая функция. Нельзя объявлять `sys.executable` нового worker эквивалентом каталога нового Rust exe без явной передачи root. Текущий worker может использовать legacy config fallback при ошибке import — проверить на чистом AI environment.

**Предварительные решения для dependency matrix:** `torch/transformers/embedding inference` — `KEEP IN PYTHON AI`; `handlers.ai_engine.rag_client`/service locator — `REMOVE FROM PYTHON AI` либо переписать host-facing adapter на Rust (решение после архитектурного ревью); `managers.rag.install_spec` — `SPLIT CONTRACT`: AI-local readiness/model import обязан остаться доступным, а UI installer/settings policy должна стать явным cross-boundary contract; `embedding_presets/SettingsManager/app_paths` — `REQUIRES RESEARCH` на переносимость конфигурации и pure subset, **не** равнять с прямым Python Core dependency нового продукта.

## Требования и валидация

- `REQ-AI-BOUNDARY-001`: для каждого worker метода зафиксировать input/output/error, priority/cancellation/deadline и локальные required Python imports.
- `REQ-AI-BOUNDARY-002`: worker должен получать effective model/config/paths без зависимости от UI/Host global service locator и иметь независимую проверяемую загрузку AI-only окружения.
- `REQ-AI-BOUNDARY-003`: модель readiness различает installed, model downloaded, loadable, warmed, healthy и failed. Отделить installer policy от inference binding.
- `REQ-AI-BOUNDARY-004`: сохранить `hot`/`bulk`/`rerank` priority semantics, не допуская cross-loop blocking/UI dependence.

**NOT DONE:** отдельный запуск AI subprocess в стерильном Python environment, coverage всех services TTS/ASR/Beats, динамические imports внутри внешних моделей, Rust crate/license selection. Это ещё не доказательство, что требуется весь текущий `managers/` Python-каталог; это доказательство, что граница нуждается в декомпозиции по контрактам.

**Связано:** [Python imports](python-import-reachability.md), [IPC](../03-runtime/ai-ipc.md), [AI env](../03-runtime/ai-environments.md), [RAG](../01-functional/rag.md).
