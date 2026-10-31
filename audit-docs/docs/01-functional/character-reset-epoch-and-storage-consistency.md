# Очистка истории персонажа: epoch, транзакции и границы последствий

**Срез:** `CodeNow.zip`, 2026-10-30. **Статус:** `ACTIVE` для явной очистки загруженного персонажа; `CONDITIONAL` для фонового summarizer/graph/memory. Аудит кода + существующих unit tests; полный межсервисный reset end-to-end не запускался.

## CAP-RESET-001 — почему «очистить историю» не равно DELETE chat

`src/characters/character.py:1100-1158` выполняет последовательность: `history_epoch += 1` под `character_lock(char_id)`; `HistoryService.on_history_reset` отменяет timers/cooldowns; resets sticky core-memory triggers/working_state; восстанавливает BASE_DEFAULTS + subclass overrides + config; удаляет stale variable keys, делает `flush_variables`; `memory_system.clear_memories()` soft-deletes memories; `history_manager.clear_history()` soft-deletes историю; `GraphStore.clear_for_character()` удаляет отношения/узлы/processed ledger физически. Сбой при удалении переменных или graph очистке логируется и проглатывается, но ошибки memory/history могут прервать функцию. Это **не общая транзакция** между несколькими хранилищами и in-memory состояниями.

В `src/managers/history_manager.py:1394-1410` clear history выставляет `is_active=0, is_deleted=1`, чтобы обычный RAG не нашёл даже архивные reset rows. `src/managers/memory_manager.py:1369-1379` выставляет `is_deleted=1`; graph clear (`src/managers/rag/graph/graph_store.py:115-138`) удаляет relations, entities и journal в одной sqlite transaction. Старые пользовательские snapshots и внешние файлы этими методами отдельно не удаляются. Всю операцию нельзя называть необратимым уничтожением всех данных, учитывая soft-delete и snapshots.

## CAP-RESET-002 — epoch защищает старое фоновое сжатие, а не все writers

`src/controllers/history_controller.py:112-223` читает history+summary под character lock; background compression сохраняет capture epoch; `_commit_summary_state:1306-1361` одним `flush_variables` под тем же lock пишет summary text/count/anchor/segments, если epoch совпал. `_add_memory_for_epoch:1276-1304` проверяет epoch и выполняет add памяти под lock. `on_history_reset:139-158` отменяет deferred timers. Тесты `src/utils/Testing/test_history_epoch_guard.py:132-383` подтверждают на stubs отказ от stale summary/facts и единый variable flush.

**Граница гарантии:** `Character.clear_history` освобождает `character_lock` сразу после увеличения epoch (`character.py:1106-1107`), перед очисткой memory, variables, history и graph (`:1108-1155`). Следовательно синхронизация старых callbacks сама по себе не является глобальным mutex для reset; новый turn потенциально пересекается с частично выполненным reset. Это **INFERRED concurrency risk**, для конкретного воспроизведения нужен adversarial test. `GraphController._extract_and_store` не использует `history_epoch` при сохранении графа (`src/controllers/graph_controller.py:208-309`); запись от старого graph task после reset — отдельная проблема generation fencing.

## CAP-RESET-003 — identity истории и UI snapshot

`HistoryManager` хранит внешние `message_id`, SQL insertion `id`, `turn_id`, `task_uid` раздельно (`src/managers/database_manager.py:33-61`). Range-delete основан на row id и scope character (`src/managers/history_manager.py:1634-1694`); flush/reset — не просто очистка видимых QWidget. `src/ui/chat/presentation_coordinator.py:345-370,545-640` привязывает историю к `HistoryLoadTicket(request_id, character_id, start_revision)`, отвергает late snapshots другого/неактивного персонажа, откладывает refresh при mounted streaming и воспроизводит live commands, которых snapshot ещё не содержит. Это protection презентационной проекции, не storage transaction.

История может иметь расхождение между UI и durable persistence при частичном fan-out turn или поздней generation: тесты `src/utils/Testing/test_history_manager_atomicity.py:47-411` проверяют **single-character batch** rollback и row identity, но не атомарность across recipients. `src/managers/history_ui_projector.py:52-138` по actor identity переназначает отображаемый role для multi-Mita; хранить только старый `role=user/assistant` недостаточно, чтобы восстановить правильного speaker.

## Проверка тестами в этом проходе

`PYTHONPATH=src python -m unittest src/utils/Testing/test_history_manager_atomicity.py src/utils/Testing/test_history_epoch_guard.py -q`: **23 tests, OK**, 2026-10-30. Тесты используют stubs и временные SQL базы; не доказывают Unity/GUI/inference parity. В частности, test проверяет atomicity summary variable flush, отказ stale epoch, idempotency merge/preserve SQL identity, batch history commit/rollback, deferred compressor reset. Логи намеренного `RuntimeError('boom')` являются частью fault-injection теста, не признаком общего провала.

## Требования и открытые вопросы

- `REQ-RESET-001`: назвать точную область команды reset и storage states (active, deleted, archived, retained snapshots, variable defaults, graph/ledger, timers/working state).
- `REQ-RESET-002`: защитить **все** delayed producers (history, memories, derived embeddings, graph, UI) от записи старой ревизии после подтверждённого reset; не считать защиту summarizer достаточной.
- `REQ-RESET-003`: define and test cross-storage partial-failure policy; durable outcome должен сообщать, какие шаги committed/failed, в отличие от молчаливого логирования.
- `REQ-RESET-004`: сохранить scoped message/actor/turn identity и reconciliation stream/snapshot, не превращать GUI состояние в источник истины.
- `REQ-RESET-005`: однозначно различать `ClearHistory`, `ForgetMemory`, `DeleteGraph`, `ClearAllCharacterState`, `PurgeDeleted` и `RestoreSnapshot`; full parity не сводится к одному SQL DELETE.

**Ещё проверить:** сброс незагруженного персонажа; одновременные reset+new generation+embedding task; поздняя graph extraction; deleted history reindex; rebuild после full graph clear; ошибку между `memory.clear` и `history.clear`; persisted summary после процесса с crash. При этом конечную Rust-архитектуру здесь не выбираем.

**Связано:** [history](history.md), [compression](history-compression.md), [graph ledger](graph-extraction-ledger-and-clear-consistency.md), [character state](characters.md).
