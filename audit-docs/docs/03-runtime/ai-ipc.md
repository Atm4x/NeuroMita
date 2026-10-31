# AI IPC и supervision

**Capability:** `CAP-AI-001`. **Статус:** ACTIVE: AIEngineController создаётся обязательным backend. Реальная загрузка inference services/models lazy/conditional. **Источники:** `src/controllers/ai_engine_controller.py:180 _Worker`, `:257 start`, `:306 call`, `:457 _deadline_loop`, `:581 _heartbeat_watch_loop`, `:695 stop`, `:786 _result_loop`, `:897 AIEngineController`, `:1699 call`; `src/handlers/ai_engine/worker_process.py:341 run_worker_process`, `:474 _worker_loop`, `:747 _LazyService`. Состав services по handle methods, не аудит математики inference.

## Назначение и граница

Core управляет отдельными Python workers, ожидает ответы по request id, отслеживает здоровье, меняет окружения/топологию и восстанавливается после сбоев. Тяжёлые inference алгоритмы остаются Python. Нынешний транспорт — multiprocessing spawn + Queue, а не независимый language-neutral server.

Это принципиальная граница для новой Rust-системы: Python worker entrypoint должен запускаться как самостоятельный процесс с новым wire contract. Python multiprocessing queues передают Python-объекты; сохранение их API не даёт Rust IPC автоматически. Требования к операциям/health/recovery можно сохранить отдельно от механизма сериализации.

## Топология и процессы

Services: tts, asr, rag, beats. AI_ENGINE_MODE default shared; env NEUROMITA_AI_ENGINE_MODE выше settings. auto сейчас выбирает shared. Split создаёт worker на service с соответствующим composition category. Shared использует общий composition, все services в одном процессе. В обоих режимах workers daemon=True и запускаются при AIEngineController initialization.

_Worker владеет process, command/result/log queues, pending Futures/deadlines/meta, per-service ready/quarantine/recovery, admission lock, result/log/watch/heartbeat/deadline threads. Queue command default 64 (minimum 8), result/log вдвое больше. Это bounded IPC buffers, не доказанный общий bound всех application requests.

## Сообщения

| Направление/тип | Поля и смысл |
|---|---|
| Core→worker request | req_id UUID, service, method, payload dict |
| Core→worker control | control=cancel_request/quarantine_service/restart_service/shutdown, req_id/service/payload где нужны |
| Worker→core ready | type=ready, service |
| Worker→core response | type=response, service, req_id, ok + result либо error string |
| Worker→core event | type=event, service, event, data |
| Worker→core heartbeat | type=heartbeat, worker |
| Log queue | level/message, optional detail; формат логов отдельный канал |

Явного protocol version/handshake schema в просмотренном envelope нет. Payload/results могут содержать numpy arrays, audio metadata и другие Python values; exact service schemas предстоит завершить. Runtime IPCRegistry с @ipc_allowed — другой контур доступа к core administration, не этот worker transport.

## Admission и correlation

call создаёт UUID/Future и deadline до command enqueue. Проверка process alive/stopping/quarantine, регистрация pending и put_nowait защищены admission lock. Unsupported service, dead/stopping worker, quarantine или full queue возвращают failed Future. Ready event не является обязательной проверкой в самом call.

Result loop сопоставляет req_id и снимает pending; поздний ответ без pending игнорируется. Future.cancel снимает pending/deadline/meta и best-effort отправляет cancel_request. Response error превращается в RuntimeError строки: структурированная типизация service error на этой границе теряется.

## Readiness и worker execution

Worker настраивает managed dependency paths, .pth/DLL policy/compile caches и probes до asyncio loop. Создаёт lazy service wrappers и сразу публикует ready для каждого. READY значит доступность endpoint wrapper после bootstrap, не модель в GPU/CPU.

Default concurrency: tts1/asr2/rag4/beats2; semaphores per service, max inflight=max(default global8,sum service limits). При заполнении inflight worker ждёт FIRST_COMPLETED до чтения следующей command: control messages разделяют очередь и могут ждать вместе с работой.

LazyService инициализирует underlying service в to_thread, async handlers await напрямую, sync — через to_thread. Heartbeat default 2 s, parent watch default 1 s, parent death→os._exit(1). Это различает живой event loop и занятый native backend, но heartbeat сам по себе не гарантирует прогресс конкретного request.

## Cancellation и timeout

cancel_request в worker намеренно no-op: native CUDA/to_thread нельзя безопасно считать физически остановленным после cancellation asyncio task. Caller отказывается от ответа; вычисление может продолжаться.

Parent deadline monitor default request_timeout300 s, tick .2 s. Expired request завершается TimeoutError, service quarantine, ready сбрасывается, приходит service_quarantined event и планируется recovery. Worker quarantine блокирует новые dispatch, уже admitted tasks могут ещё жить.

Service restart пытается drain без отмены native task, default30 s + grace5 parent. Не drain-ится — parent force terminate worker. Heartbeat watchdog default180 s с startup grace300 s. Неподвижный worker terminate-ится; process watcher инициирует recovery.

Важно различать timeout ожидания у клиента (например rag_client.future.result) и собственный deadline _Worker.call. Если client ждёт 30 s, а worker deadline300 s, клиентский TimeoutError сам не вызывает Future.cancel: вычисление может остаться до своего deadline.

## Crash recovery

Default restart limit3, exponential backoff base.5 s, lifetime≥60 s сбрасывает предыдущий restart streak. Candidate worker стартует с прежними paths/probes, проходит process/model validations, заменяет crashed только если ownership ещё актуален. Process-ready recovery может иметь failed_services; UI получает model-lost signals для этих services. После исчерпания circuit открывается, worker_restart_exhausted event. Это не автоматическое повторение всех уже упавших inference requests.

Fatal CUDA context policy может завершить worker при exception либо failure-shaped result; ordinary OOM/ошибки не автоматически приравниваются poisoned context. Точная классификация ещё требует отдельного просмотра runtime_failure_policy и тестов.

## Shutdown

Под admission lock устанавливается stopping, expected_exit предотвращает recovery. Отправляется shutdown command, worker drain/shutdown services; parent ждёт timeout, затем terminate/join/kill. На Windows timeout≤0 использует taskkill tree без окна перед terminate. После физической остановки пробуждает result/log threads sentinel, join threads, close queues/cancel_join_thread, fails pending. Если process остаётся alive — error.

Timeout — на worker, не общий deadline всех workers. В shared отказ/рестарт затрагивает все services; в split зона отказа меньше, но больше процессов и возможное дублирование моделей/runtime. Потребление памяти не измерялось.

## Подтверждённые связи Python AI с нынешним core

- worker_process импортирует core.error_utils, core.torch_compile_runtime и runtime failure policy, опирается на environment manifests/env roots.
- ASR service импортирует handlers audio capture/input gate, domain.audio_input и infrastructure.audio.selection_wire: в worker живёт не только inference, но и live device capture orchestration.
- TTS service lazy импортирует LocalVoice, который дальше связан с model/install/runtime machinery; полный граф ещё исследуется.
- beats service импортирует game_connections.services.beat_backend_spec и main_logger.
- RAG service использует shared gpu_scheduler и rag_runtime.

Следовательно, Python AI не является полностью самостоятельным distributable package сейчас. Для нового core требуется выделить самостоятельные DTO/config/runtime helpers и narrow control surface. Это не требует переписывания inference algorithms.

## Начальный service inventory

| Service | Подтверждённые methods | Дальнейший аудит |
|---|---|---|
| tts | ping, set_language, list_models, check_installed, check_initialized, select_model, init_model, synthesize, get/refresh_triton_status | Payload/results/warmup/output file lifetime/RVC |
| asr | ping, get_status, set_input_gate, start_live, switch_input, stop_live | Audio devices, VAD/PTT/events, recognizer lifetime |
| rag | ping, warmup_embeddings, warmup_reranker, get_embeddings, rerank, get_reranker_status | Types, batching, model management, priority |
| beats | ping, warmup, get_backend_status, initialize_backend, extract_beats | Source media/artifact/timing contracts |

## Требования и альтернативы

Новая boundary должна явно задавать version, request/attempt id, capability/model readiness, payload types/large binary transfer, terminal outcomes, cancellation semantics, error taxonomy, ownership temporary files, deadlines, queue admission, parent death и recovery epochs. До сравнения named pipes/TCP/local sockets/shared memory нужно завершить payload inventory и размеры потоков. Один транспорт не обязан одинаково переносить control commands, PCM и model files.

Не копировать _Worker в Rust буквально. Рассмотреть owned process host с tasks/channels и typed lifecycle; отдельно решить процессы по service/device/environment. История inference и installation activation связаны через model loss/validation, а не через общий mutable GUI controller.

## Пробелы

Полный runtime composition switch/rollback, deferred calls cancellation, candidate validation semantics, all service payloads, GPU scheduler, environment installation/update/removal, external core IPC auth и exact worker package dependencies. engine_process старый entrypoint не имеет найденных callers вне definition; inprocess_engine найден в rag tester, не основном production headless host.
