# Fatal CUDA context: изоляция и повторное создание AI worker

**Статус:** CONDITIONAL / ACTIVE при запущенном Python AI worker и CUDA. Источники `src/handlers/ai_engine/runtime_failure_policy.py:8-76`, `worker_process.py:389-447,623-660`, `src/utils/Testing/test_runtime_failure_policy.py:1-115`. Это **не перенос inference на Rust**.

## Контракт и действия

Выполняемый AI service может оставить CUDA context в неисправимом состоянии после device-side assert, illegal memory access, misaligned address, illegal instruction, invalid program counter, launch failure, destroyed context. `is_cuda_context_poisoned` анализирует текст цепочки `__cause__`/`__context__` с защитой от циклов (`runtime_failure_policy.py:10-37`). CUDA OOM специально не включён в смертельные markers (test `:24-33`).

`probe_cuda_context():40-62` не импортирует torch и не создаёт CUDA runtime заново: ищет уже импортированный модуль в `sys.modules`, проверяет `torch.cuda.is_available`, затем делает `cuda.synchronize()` только на ошибочной ветке. Возвращает fatal exception или None. Отсутствие torch/неуспех availability не трактуется автоматически как poison.

`worker_process.py:410-446`: service response с результатом `None`/`False` вызывает CUDA probe; success hot path не синхронизируется. При исключении сначала анализируется само исключение, затем probe на потенциально скрытую native ошибку. Fatal result логируется, worker немедленно завершает процесс `os._exit(70)`; **обычный result/error response в очередь клиенту до выхода не отправляется**. Остальные ошибки оформляются `ok=False` queue response, отмена имеет отдельную ветвь `CancelledError`. При `restart_service` failure действует такой же fatal path (`:637-659`).

## Тесты и уровень уверенности

`test_runtime_failure_policy.py:16-111` содержит проверку fatal markers против OOM, fake torch sticky failure и обеих веток `_dispatch` с mocked hard exit. **Это подтверждённые тестовые сценарии, но тесты не запускались в текущем аудите и не являются доказательством GPU/driver recovery на машине пользователя.** Parent supervision/replay был описан в `ai-ipc.md`; необходимо отдельно проверить, как parent классифицирует exit 70, какие запросы считаются lost и сколько раз допускается reincarnation.

## Обязательные требования будущего host

REQ-AI-FAIL-001: poisoned CUDA нельзя лечить повтором inference в той же process address space. Worker process owner обязан выявлять abrupt exit, инвалидировать pending correlations и создавать новый worker, если policy разрешает.

REQ-AI-FAIL-002: отмена и обычная OOM сохраняют отдельную семантику; безусловный kill на любой `None` запрещён — `None` лишь запускает проверку.

REQ-AI-FAIL-003: readiness после restart заново проверяется; no-response до exit нельзя ошибочно записывать как успешное исполнение. Тестировать lost requests, queued jobs, restart loops, native cleanup и отсутствие бесконечного recycle.

## Граница Core / AI

Собственно CUDA detection/synchronize остаются внутри Python AI Engine, поскольку исполняемый модуль и контекст принадлежат этому процессу. Rust host будущей NeuroMita должен знать только стабильный worker failure/restart protocol, без Python-specific torch/CUDA imports. `os._exit(70)` — факт legacy contract, не требование фиксировать такой код навсегда. Прямая замена worker на in-process вызов противоречит требованию изоляции.
