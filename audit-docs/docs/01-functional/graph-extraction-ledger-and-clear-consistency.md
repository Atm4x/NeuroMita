# Граф знаний: журнал обработки, повторная экстракция и согласованность очистки

**Срез:** `CodeNow.zip`, Python releases snapshot из предыдущего прохода; дата 2026-10-30. **Метод:** статическая проверка точных вызовов плюс одно локальное воспроизведение на временной SQLite-БД с реальными `DatabaseManager` и `GraphStore`. Внешний LLM и GUI не запускались; не следует считать это полноценным UI E2E. **Классификация:** `CONDITIONAL` (ручная пакетная экстракция, очистка графа и optional realtime); фактический GUI entry подтверждён.

## CAP-GRAPH-LEDGER-001 — журнал обработки истории

**Назначение.** При пакетной экстракции пользователь может включить пропуск уже обработанных сообщений. `GraphStore._ensure_schema` создаёт `graph_processed_messages(character_id, message_id, processed_at)` с `PRIMARY KEY(character_id, message_id)` (`src/managers/rag/graph/graph_store.py:90-98`). `mark_messages_processed` пишет `INSERT OR IGNORE` даже если извлечение не породило сущностей (`:140-150`).

**Основной путь:** `_do_extract` (`src/controllers/gui/rag_memory_controller.py:222-253`) при `skip_existing` исключает `history.id` из множества идентификаторов, которые уже содержатся в `graph_processed_messages` **ИЛИ** `graph_relations.source_message_id`. При отсутствии `skip_existing` эта защита не применяется. После LLM-вызова `_process_item:274-299` маркирует текущий `hid` как обработанный, даже когда `result.ok` ложен, response пуст, parser не вернул сущности или произошло исключение внутри `try`. Если срабатывает ранний `stop_event` до `try`, отметки нет. Возможна семантика «попытка завершена, а не экстракция успешна»; её надо явно отразить в новом продукте.

**Границы трассировки.** Выборка берётся из `history`, где `content` not null/not empty. В запросе нет `is_active=1` и `is_deleted=0` (`:236-253`): при полном переизвлечении потенциально участвуют и архивные/soft-deleted строки. Пары собираются соседством user→non-user в уже отфильтрованном списке (`:255-272`), не по `turn_id`/`message_id`: такой pairing нельзя считать формальным session join. В режиме нескольких worker задачам разрешено завершаться в любом порядке (`:323-348`); `GraphStore` отдельно создаёт SQLite connections.

**Состояния:** `UNSEEN` → `ATTEMPTED` (ledger) и независимо `GRAPH_DATA_PRESENT`/`ABSENT`; DB хранит две независимые части. Отметка о результате не кодирует provider, model/prompt version, content hash и графовую revision. Пользовательское «повторить после изменения модели/промпта» требует явного `skip_existing=False` или новой политики invalidation.

## CAP-GRAPH-LEDGER-002 — воспроизведённая несогласованная очистка

**Наблюдаемый дефект.** GUI `_delete_all_graph_data` (`src/controllers/gui/rag_memory_controller.py:600-656`) считает `graph_entities/graph_relations`; после подтверждения выполняет `DELETE FROM graph_relations`, `graph_entity_aliases`, `graph_entities` (`:641-649`). `graph_processed_messages` не очищается. При пустом графе операция вообще завершается до удаления ledger (`:619-624`). Между тем `GraphStore.clear_for_character` явно удаляет processed ledger (`src/managers/rag/graph/graph_store.py:115-138`). Значит, два пути очистки имеют **разную семантику** при одинаково пустом графе.

**Воспроизведение, локальное без GUI:** в уникальной временной SQLite-базе создан `GraphStore(db, 'Mita')`, добавлены две сущности и relation с `source_message_id=42`; записан `mark_messages_processed([42])`. Выполнены точно те же три `DELETE`, что и в GUI. Подсчёт до: `entities=2`, `relations=1`, `processed=1`; после: `entities=0`, `relations=0`, `processed=1`. SQL-predicate, эквивалентный `skip_existing`, вернул `eligible=False` для history row `42`. Источники приложения не изменялись. Это доказывает несогласованность для такой начальной конфигурации, но не успешность сетевого восстановления графа в реальном пользовательском сценарии.

**Дополнительная граница:** графовая схема содержит `graph_entity_embeddings` с `ON DELETE CASCADE` (`graph_store.py:72-77`), а `DatabaseManager.get_connection` включает `PRAGMA foreign_keys=ON` (`database_manager.py:89-120`). Поэтому удаление сущности должно каскадно удалить её embedding при штатной SQLite-конфигурации; нельзя утверждать, будто этот GUI путь гарантированно оставляет embedding. Однако processed ledger не зависит от foreign key на entity и точно переживает этот SQL.

**Реальные последствия:** после удаления пользователь получает успешное сообщение об удалении сущностей/связей. Последующая пакетная экстракция с `skip_existing=True` исключит ранее помеченные `history.id` и может не создать новый граф даже при наличии исходной истории. Это **CONFIRMED** для SQL+predicate, сценарий целого GUI остаётся `INFERRED` до E2E.

## CAP-GRAPH-LEDGER-003 — concurrent extraction и versioning

`GraphController.handle_turn` (`src/controllers/graph_controller.py:145-197`) сохраняет inline extraction в фоне или запускает realtime LLM extraction при включённой настройке; на персонажа допускается одна pending realtime задача (`:175-196`). `_extract_and_store:208-309` после внешнего `generate_utility` создаёт новый `GraphStore` и сохраняет graph rows. Ни история `history_epoch`, ни graph generation id здесь не передаются в persisted write. При удалении графа одновременно с выполняющимся extraction старый ответ **может** вставить данные после очистки; это статически подтверждённый отсутствие fencing, **риск**, не runtime-воспроизведённая гонка. `Character.clear_history:1100-1155` сам увеличивает epoch и вызывает `GraphStore.clear_for_character`, но `GraphController` не проверяет эту эпоху перед записью.

**Существующие преимущества:** GraphStore `upsert_entity/upsert_relation` умеют принимать общий sqlite connection (`graph_store.py:166-215,299-358`), что позволяет транзакционно объединять extraction writes. Однако эта локальная атомарность не заменяет graph-version fencing, журнал обработки и единый контракт reset.

## Требования к полной реализации с нуля

- `REQ-GRAPH-LEDGER-001`: различать **отправлено на обработку / успешно извлечено / сохранено**, вести явную identity и версию content/prompt/model; retry не должен терять неудачную попытку по ошибочному `processed`.
- `REQ-GRAPH-LEDGER-002`: `ClearGraph(all|character)` должен согласованно управлять entities, relations, aliases, embeddings, processed ledger и активными jobs; после очистки `skip_existing=True` не должен блокировать намеренное восстановление.
- `REQ-GRAPH-LEDGER-003`: ясно определять, входят ли архивные и удалённые history rows в bulk extraction; не смешивать archival lifecycle и retrievable/valid dialogue semantics.
- `REQ-GRAPH-LEDGER-004`: привязать отложенный extraction result к версии исходного контекста/графа; пользовательская очистка либо вытесняет старые pending writes, либо явно показывает, что они продолжаются.
- `REQ-GRAPH-LEDGER-005`: source-message pairing должен учитывать настоящие `turn_id`/speaker, если применимо; проверить пользовательскую семантику merge соседних строк.

## Validation (что реально сделано и что осталось)

`DONE`: временная SQLite-контрольная проверка `2/1/1 -> 0/0/1`, статически подтверждены journal schema, GUI SQL и skip predicate. `NOT RUN`: PyQt GUI E2E (PyQt6 не установлен); удаление одновременно с realtime LLM; полный rebuild старых rows; импорт snapshot и reindex в нескольких персонажах; SQL fault injection; prompt/model changes. Результат нельзя расширять за доказанные границы.

**Связано:** [entity lifecycle](graph-maintenance-and-entity-lifecycle.md), [character reset](character-reset-epoch-and-storage-consistency.md), [RAG](rag.md), [traceability](../06-design-input/feature-traceability.md).
