# Поиск контекста: RAG

Статус: основной search pipeline и core/AI boundary исследованы. Полные repositories, sentence retrieval, граф и все reindex paths ещё требуют завершения.

## Functional Capability: поиск релевантной памяти и истории

**ID:** `CAP-RAG-001`. **Статус:** CONDITIONAL: automatic RAG_ENABLED либо explicit tool/API override. **Источники:** `src/controllers/model_controller.py:2001 process_rag`; `src/managers/rag/rag_manager.py:821 search_relevant`; `src/managers/rag/pipeline/query_builder.py:16 build`; pipeline types/config/combiner/reranker; repositories memory/history; retrievers vector/keyword_only/fts/graph.

### Назначение, сценарий и данные

Восстановить подходящие старые факты и диалоги перед новым turn. Automatic query = user_input, иначе system_input. Automatic отключён для GameMaster и скрытой L1 reaction. Explicit config_overrides, включая пустой dict, обходит основной RAG_ENABLED gate, но не обязательно gates embedding helper; эти уровни доступности различаются.

Вход: query, character scope, limit/threshold, settings/per-call overrides, recent active history, provider model identity. Выход: memory/history/graph candidates с id/content/score/features/meta и готовый contextual prompt block. Memory candidate id=eternal_id, history id=SQLite row id. Empty search не означает обязательно отсутствие данных: optional stages могут отказать с fallback/no-op.

### Порядок search

1. Config snapshot; explicit overrides меняют ограниченный список flags/scope/combine modes.
2. QueryBuilder строит expanded text из recent active history+query, keywords с lemmatization и query embedding, получает recent actor context.
3. Выбирает vector, keyword-only, FTS и graph retrievers согласно настройкам/доступности. Vector-only не запускает остальные.
4. Каждый retriever вызывается последовательно; exception даёт пустой bucket, не аварийный отказ всего pipeline.
5. Combiner объединяет candidates по (source,id), merge features=max.
6. Time/entity/priority enrichers, linear scoring, sorting.
7. Optional cross-encoder second pass через AI boundary; повторная сортировка.
8. Optional minimum graph slots поднимают graph candidates в top limit.
9. Debug logging и asynchronous access tracking, public results.

### Источники и фильтры

MemoryRepository фильтрует character scope, deleted=0 и исключает island:%; memory_mode all/active/forgotten. Поэтому forgotten реально доступны search, islands предназначены для always-on prompt. HistoryRepository FTS/vector queries берут is_active=0 и not-deleted; active window не дублируется retrieval. Все остальные SQL routes ещё сверяются.

Keyword-only recall предназначен для записей без embedding; не заменяет полноценный lexical recall всего корпуса. FTS5 даёт BM25 candidates с query morphology/prefix options; может использовать expanded query, если исходный не дал MATCH expression. Морфология — pymorphy3 с fallback light ru stem; availability/normalization кешируются. Комментарии pymorphy2 устарели относительно фактического import pymorphy3.

### Query embedding

Concat mode склеивает recent history+query и нормализует vector. Expanded text ограничен 4000 chars, recent chunks отдельным cap. Weighted mode получает query vector и tail vectors отдельно, default weights .7/.3, экспоненциальный decay .6, затем normalize; tail role filter default user_only. Это core math orchestration, не перенос inference модели на Rust.

### Combine и score

Union объединяет все ids. Vector-only оставляет vector recall. Intersect требует minimum methods и optionally vector, с fallback union. Two-stage ограничивает corpus vector candidates, остальные методы добавляют features только этим ids; при пустом vector может fallback union. RRF при включении имеет приоритет выбора combiner, но vector-only ранее уже мог ограничить набор retrievers.

Обычный score = K1×sim + K2×time + K3×priority + K4×entity + K5×keyword + K6×lexical + noise; graph умножается на K7. Time=1/(1+decay×age_days). В RRF sim/kw/lex weights заменяются sum 1/(k+rank), bonuses сохраняются. Noise configurable и может быть seed-ирован. Итоговый score не обязан лежать в 0..1, несмотря на такой поясняющий header в process_rag.

Cross encoder top count=min(pool, max(configured_top_k, floor(pool×ratio))), затем hard cap max_items при >0. Alpha смешивает CE/linear, early exit может оставить часть linear scores. Конкретная inference реализация остаётся AI. Default fields/config comments не считать подтверждённой effective настройкой: from_settings и runtime выбирают реальные значения.

### Core/AI граница

Core выполняет SQL, text cleaning/keywords/morphology, candidate fusion/scoring, vector dot products и prompt formatting. RagEmbedder local route вызывает EmbeddingService либо LocalEmbeddingProvider→handlers.ai_engine.rag_client; это proxy, не импорт sentence_transformers непосредственно. Cloud embedding providers — отдельные endpoints.

CrossEncoderReranker — AI proxy с LOADING/READY/ERROR и runtime epoch. Runtime reset инвалидирует старые результаты, failed runtime требует explicit successful warmup/restart. Полные warmup/cancel/worker contracts описываются при AI audit.

rag_client отправляет engine.call('rag', method, payload), ждёт Future с ограничением; embeddings timeout default max(30,min(3600,n×20)), rerank max(30,min(3600,n×10)). Timeout ожидания здесь сам по себе не подтверждает отмену remote computation. Payload embeddings содержит model/texts/prefix/query_prefix/batch_size/priority hot/bulk.

### Vector index и derived cache

При HAS_FAISS VectorRetriever использует cached top-500 hits, иначе full blob scan. Cache содержит FAISS IndexFlatIP — точный поиск, не ANN; альтернативный _NumpyIndex в том же module есть, но обычный retriever вызывает этот cache только при HAS_FAISS. Header с обещаниями относительной скорости не является benchmark evidence.

Cache key character/model/source_table, rebuild по COUNT embeddings. Обновление vectors без изменения count не инвалидирует cache автоматически; явные invalidates найдены в index_all_missing, но не в update_memory_embedding. Это риск stale search после редактирования/переиндексации на месте. Metadata fetch всё равно фильтрует удалённые/активные rows, но score может опираться на старый vector.

### Побочные эффекты, UI и ошибки

Полученные memories увеличивают access_count и last_accessed; graph results — entity access count. Это влияет на последующее forgetting/TTL. Tracking fire-and-forget. Debug pipeline logs показывают stages/features; полный GUI search playground и settings ещё не разобраны.

process_rag рендерит memory/history/graph отдельно, clip default 700 chars, per-prompt-set templates Structural/rag_*.txt, appends graph block даже если custom wrapper его не включает. Original system_input остаётся текущей инструкцией отдельно от retrieved context. Ошибка search/formatting может вернуть пустой context и продолжить диалог.

### Требования и реорганизация

Сохранить search scopes, degraded lexical-only operation, explicit search при выключенном automatic injection, наблюдаемую provenance/features и модель-specific indexes. Все производные данные должны соответствовать source version/model/dimensions. Search relevance не тождественна достоверности факта. Rust implementation может держать search/DB/math в core, inference в Python; transport/batching boundaries проектируются отдельно, без копирования pipeline классов.

## Functional Capability: индексация embeddings

**ID:** `CAP-RAG-002`. **Статус:** CONDITIONAL: embedding capability и index operation. **Источники:** rag_manager.py:641 update_memory_embedding, :686 update_history_embeddings, :1104 index_all_missing, :1261 index_all; RagEmbedder.array_to_blob/get_embeddings.

После commit history/memory фоновые tasks вычисляют vectors. Memory embeddings source_id=eternal_id + character, history source_id=row id + character. Model identity — db_model_key/provider:model либо hf name; dimensions и float32 BLOB сохраняются рядом. Single update может записывать legacy embedding column и новую embeddings table; sentence-level optional.

Missing reindex выбирает rows без embedding для текущего model, может работать при RAG_ENABLED=False через allow_when_rag_disabled, но vector gate остаётся. Batch alignment дополняет отсутствующие vectors None; commit/прогресс требуют дальнейшей проверки всех loop branches. Прямой missing memory query не исключает islands, в отличие от обычного upsert path; это необходимо учесть в полном indexing audit.

Проверить cancellation/progress callbacks, full reindex и derived index invalidation, смену модели во время job и stale content writes. В частности, embeddings purge в MemoryManager использует SELECT id, тогда как source_id фактически eternal_id: различие зафиксировано как ISSUE-006.
