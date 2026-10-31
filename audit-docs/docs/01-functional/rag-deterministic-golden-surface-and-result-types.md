# RAG: воспроизводимая цепочка поиска, идентичность результатов и границы golden tests (Pass 12)

**Статус:** ACTIVE/CONDITIONAL source path и адресная offline validation без настоящих ML-моделей. Исходники `src/managers/rag/rag_manager.py`, `src/managers/rag/pipeline/types.py`, тесты `src/utils/Testing/test_rag_search_golden.py` и `test_rag_units_golden.py`. Не проектирует Rust query engine и не требует побайтного копирования текущих эвристик.

## CAP-RAG-GOLDEN-001 — что действительно работает в зафиксированном сценарии

В тесте `test_rag_search_golden.py` создаётся **временная SQLite БД** с 8 сообщениями истории и 3 фактами памяти для одного `character_id='GOLDEN'`. Вместо реальных embedding-сервисов в `AIEngineService`/`EmbeddingService` регистрируются детерминированные fake векторы: token hash bag размерности 256, нормализованный по L2; фоновые сообщения доступа выключены. Через действующий `RAGManager.update_history_embedding` и `update_memory_embedding` создаются 11 vector rows. Затем четыре запроса проходят настоящий путь `RAGManager.search_relevant` с `limit=5`, `threshold=0.0` и проверкой сохранённой последовательности `(source,id)`.

Тест также проверяет невозрастание `score`, наличие обязательных полей `history`/`memory` в результатах и детерминированный порядок при повторном вызове на неизменённом состоянии. **Это не доказательство семантической релевантности**: fake hash bag построен не для качества поиска, а для фиксации shape/order pipeline и устранения ML jitter.

## CAP-RAG-GOLDEN-002 — публичный результат и тип источника

`Candidate` в `src/managers/rag/pipeline/types.py` возвращает `to_public_dict()` с общей частью `source`, `id`, `content`, `score`, `features` и source-specific metadata. Для `history` фиксированы `role`, `date`, `message_id`, `speaker`, `target`, `participants`; для `memory` — `type`, `priority`, `date_created` (`test_rag_units_golden.py:57-128`).

`Candidate.key` — пара `(source,id)`: одинаковый числовой ID из истории и памяти не равнозначен одинаковой сущности. `merge_from` объединяет признаки с `max` по совпадающим feature keys, заполняет пропущенный текст и бережно соединяет metadata; эта функция служит основой объединения кандидатов из разных стратегий.

`_blob_to_array` проверяет float32 бинарный формат и размерность эмбеддинга; некорректная длина, NaN, несовместимая размерность приводят к отклонению кандидата. `_split_sentences` обрабатывает знаки пунктуации, новые строки и минимальную длину сегмента. Это форматные свойства данных, отдельные от качества embedding inference.

## Результат адресной проверки

`PYTHONPATH=src python -m pytest -q src/utils/Testing/test_rag_units_golden.py src/utils/Testing/test_rag_search_golden.py` → **18 passed, 8 subtests passed** (2026-10-31 UTC). Использованы fake AI services, временная БД и deterministic settings. Не было внешней сети, загрузки реальных checkpoint, GPU, графового поиска, cross-encoder reranking или пользовательского Qt.

## Обязательное функциональное значение для новой NeuroMita

- `REQ-RAG-GOLDEN-001`: retrieval должен возвращать источник, стабильный ID внутри его пространства, текст, объяснимые score/features и нужные исходные метаданные; не терять идентичность истории/памяти при одинаковых числах ID.
- `REQ-RAG-GOLDEN-002`: хранение и чтение embedding согласованы по размерности/типу данных, и unavailable/invalid vectors не превращаются молча в fake semantic results.
- `REQ-RAG-GOLDEN-003`: deterministic fixtures должны проверять форму результата, порядок при одинаковом состоянии, отсутствие двойного учёта идентичного источника, границы лимитов и provenance. Конкретный hash-derived golden ordering исходного Python теста — **контроль прежней эвристики, а не необходимая математическая спецификация Rust-поиска**.

**Остаток:** реальные векторные модели, cross-encoder, граф, FTS lexical morphology, mixed query/ranking profiles, изменение модели embedding и конкурентная перестройка индекса; их acceptance нельзя вывести из 18 offline unit tests. См. [RAG pipeline](rag-query-fusion-reranking-and-result-contracts.md), [index](rag-storage-retrieval-and-indexing-modes.md), [source consumer matrix](../00-research/rag-settings-direct-consumer-evidence-index.md).
