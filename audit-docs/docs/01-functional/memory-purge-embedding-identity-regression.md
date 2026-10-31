# Память: ID-инвариант и воспроизведённый конфликт embedding после purge

**Срез:** `CodeNow.zip`, 2026-10-30. **Статус:** `ACTIVE/CONDITIONAL` — память и physical purge по пользовательской операции; RAG embedding применяется при включённом поиске. **Доказательство:** статический source audit + два локальных SQLite-воспроизведения с реальным `MemoryManager` / `DatabaseManager`. Не исполнялись inference/Qt/network вызовы.

## CAP-MEM-ID-001 — две разные идентичности

`src/managers/memory_manager.py:559-650` выдаёт каждому персонажу `eternal_id=MAX(eternal_id)+1` в его собственном scope. Это **публичный ID памяти для данного персонажа**; `memories.id` — глобальная SQLite identity. `src/managers/rag/rag_manager.py:641-674` сохраняет memory embedding как `source_table='memories', source_id=eternal_id, character_id`, помимо legacy BLOB. `src/managers/database_manager.py:1179-1200` связывает memory embeddings именно с `m.eternal_id`. Следовательно отношение должно быть `(character_id, eternal_id, model_name) → embedding`. Ссылаться на `memories.id` в таком join нельзя.

`MemoryManager.purge_deleted` (`src/managers/memory_manager.py:1382-1411`) перед физическим удалением выполняет `DELETE FROM embeddings/sentence_embeddings WHERE source_id IN (SELECT id FROM memories WHERE ... is_deleted=1)` — то есть **использует SQLite id вместо eternal_id**. В случае двух персонажей значения закономерно различаются. Ошибки очистки embedding tables проглатываются, затем memory rows удаляются и метод возвращает успешное количество; отсутствие ошибки не гарантирует отсутствие orphan embeddings.

## CAP-MEM-ID-002 — локальное SQL-воспроизведение с действующим методом

Создана временная изолированная БД через `DatabaseManager._path_override`, без изменений исходников. Вставлены deleted memories: A `(id=1, eternal_id=1)` и B `(id=2, eternal_id=1)`; inserted `embeddings(source_table='memories', character_id='B', source_id=1, model_name='model')`. Запущен **реальный** `MemoryManager('B').purge_deleted(backup=False)`; RAG instance для исследования отключён.

**Результат 1:** метод вернул `{'backed_up': None, 'purged_memories': 1}`. Deleted row B исчезла, embedding `(character_id='B', source_id=1)` остался. Это подтверждённый **deterministic defect** при таких данных, не только подозрение из исходника.

**Результат 2:** затем вставлена новая активная memory B с `eternal_id=1`, новым `content='new'`. SQL join `e.source_id=m.eternal_id AND e.character_id=m.character_id` сопоставил новому факту старый embedding B (заданный как `b'old!'` для распознавания). В реальном RAG runtime вектор должен пройти модельную и размерностную проверку; это воспроизведение **не** доказывает, что LLM обязательно увидит неверный результат. Однако доказывает возможность неверного identity association до reindex при повторном использовании eternal_id.

## Прочие ветви и контракты

`HistoryManager.purge_deleted` (`src/managers/history_manager.py:1411-1442`) удаляет history embeddings через `history.id`, **что согласуется** с форматом `source_id=history row id` в `src/managers/rag/rag_manager.py:686-...`. Поэтому дефект специфичен memory identity и не должен необоснованно распространяться на всю таблицу embeddings.

`add_memory(skip_if_exists=True)` возвращает `memories.id` вместо eternal_id (`src/managers/memory_manager.py:587-605`), что образует второй, уже ранее зафиксированный, contract mismatch. Вместе они показывают необходимость различать типы идентификаторов на уровне API, а не только в SQL.

`MemoryManager.clear_memories` — soft delete (`:1369-1379`), после чего background embedding задачи могут ещё завершаться. Индивидуальные embeddings меняются после основного SQL commit; их отсутствие не должно откатывать сам факт. При purge с backup=true backup делается до delete, его error semantics отдельно документированы в maintenance docs.

## Требования

- `REQ-MEM-ID-001`: типизированная identity `MemoryId = (CharacterId, eternal_id)` должна отличаться от внутренней `SqlRowId`. В таблицах derived embeddings ключ должен быть согласован со всеми writers/readers/purge/reindex.
- `REQ-MEM-ID-002`: физическое удаление memory очищает все derived records, включая модельные и sentence embeddings, не позволяя orphan cache привязаться к новой memory с тем же видимым ID.
- `REQ-MEM-ID-003`: после bulk delete/purge/in-place update поиск не использует embedding с несовпадающими owner/content/model revision; stale worker result не может восстановить устаревший вектор.
- `REQ-MEM-ID-004`: `add_memory` и dedup/seed/update/delete/merge возвращают единообразную typed identity; `skip_if_exists` не должен менять тип ID.

## Проверки и открытые вопросы

`DONE`: два SQL-воспроизведения реального `purge_deleted`, первая orphan, вторая stale join. `DONE`: `PYTHONPATH=src python -m unittest` с `test_memory_dedup.py`, `test_memory_forget.py`, `test_memory_islands.py` — **18 tests, OK**. Это тесты других позитивных memory policies, не regression этого дефекта.

`NOT DONE`: fault-injection backup failure, SQLite foreign-key integrity `PRAGMA foreign_key_check`, настоящий FAISS memory retrieval после reindex, overlapping worker/purge, memory source id migrating from old schema, cross-process concurrent writers. Выявленный дефект подтверждён, его реальная частота неизвестна.

**Связано:** [memory](memory.md), [RAG](rag.md), [reset](character-reset-epoch-and-storage-consistency.md), [requirements](../06-design-input/functional-requirements.md).
