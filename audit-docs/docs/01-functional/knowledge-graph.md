# Граф знаний

**Capability:** `CAP-GRAPH-001`. **Статус:** CONDITIONAL: RAG_ENABLED + GRAPH_EXTRACTION_ENABLED; retrieval дополнительно RAG_SEARCH_GRAPH. **Источники:** `src/controllers/graph_controller.py:117 _on_message_completed`, `:208 _extract_and_store`, `:323 _store_inline`, `:373 _tag_history_messages`; `src/managers/rag/graph/graph_store.py:26 GraphStore`; `entity_extractor.py:22 parse_extraction_response`, `store_extraction`; `pipeline/retrievers/graph.py:21 GraphRetriever`. GUI/manual extraction/GC ещё не исследованы полностью.

## Назначение, сценарий и данные

Сохранять именованные сущности и связи из беседы, связывать их с историей/памятью и извлекать подходящие triples в последующий context. Вход: основной structured output, inline graph JSON/tag либо отдельный utility LLM result. Выход: entities/relations, tags, retrieval candidates и визуализируемый граф.

## Источники извлечения

MESSAGE_COMPLETED содержит character ref/id, user/assistant texts, created_memory_ids и optional inline JSON. Пустой turn пропускается. Structured output entities сохраняются без отдельного extraction call; при structured event и отсутствии inline payload realtime extraction не запускается. Plain inline требует GRAPH_EXTRACTION_INLINE. Отдельный utility path требует GRAPH_EXTRACTION_REALTIME.

Работы ставятся в BACKGROUND_LLM pool. Для realtime, если прошлый Future персонажа ещё pending/running, новый extraction пропускается; inline path этого guard не имеет, хотя обновляет latest future. Pool saturation логируется, graph extraction может быть потеряно. Это best-effort derived data, не гарантированная обработка каждого сообщения.

Realtime utility kind graph_extract, timeout 30 s, preset GRAPH_PROVIDER (current/id/display name). Template зависит от prompt set/config; exact loading precedence ещё проверить. Parser терпимо обрабатывает clean JSON/fences/несколько объектов/доступные arrays. Это отдельный parser от основного structured response trust pipeline.

## Schema и правила

graph_entities: id, character scope, normalized unique name, type, mention count, timestamps, protected/access count. graph_relations: subject/object FKs, predicate, confidence, source message id, created_at, protection. aliases с cascade delete по entity; entity embeddings одна запись на entity с model_name; processed_messages character+history-row bookkeeping.

Entity upsert lower/normalization, повторное упоминание увеличивает count и last_seen; explicit non-thing type уточняет прежний. Relation upsert ищет exact character/subject/predicate/object, обновляет confidence/source/protected либо вставляет. В просмотренной schema UNIQUE relation tuple отсутствует; конкурентный dedupe не гарантирован одним check-before-insert.

store_extraction поддерживает entities dict либо `name:type`, relations dict либо `s|p|o`, отбрасывает пустые/generic/blocked names/predicates, type ограничен person/place/thing/concept. Missing endpoints добавляет. Каждая запись может commit-иться отдельно; ошибка одной entity/relation не откатывает весь extraction. Blocklist — эвристика качества данных, не доказательство истинности extracted facts.

## Correlation и reset

History tagging ищет самое новое точное content совпадение в scope персонажа; комментарий упоминает substring, но SQL использует equality. Не использует message id и не фильтрует deleted/active. Повторяющийся текст может получить неоднозначную привязку, лог tagged_count не доказывает фактическое обновление каждого запроса.

В realtime/inline background path не обнаружен history_epoch guard перед store. Следовательно, позднее извлечение после clear/reset может снова создать graph data старой беседы. Это архитектурный риск с конкретным missing check; воспроизведение не выполнялось. Не переносить его как требуемое поведение.

## Retrieval и содержание результата

GraphRetriever объединяет keyword exact/prefix match по первым до 1000 entities и optional entity-vector names (threshold .55, top10). Получает one-hop relations, обновляет matched_entities для boosts памяти/истории, dedupe triples по тексту. Candidate id формируется из process hash строки — не stable persistent relation id.

Retriever первоначально задаёт confidence×keyword overlap score, но общий LinearReranker затем заново вычисляет score из sim/time/prio/entity/kw/lex features; graph confidence/kw_overlap напрямую в эту формулу не входят. Поэтому нельзя описывать финальный graph rank как confidence score. Graph multiplier K7 и minimum graph slots дополнительно влияют на выдачу.

## Maintenance и UI

GraphStore TTL при GRAPH_TTL_ENABLED удаляет старые relations (created_at), затем старые orphan entities (last_seen), protected сохраняются. Explicit UI callsite rag_memory_controller.py:484. Clear персонажа hard-delete relations/entities/processed messages, aliases/embeddings cascade. Entity GC analyze/apply и retyping найдены через GUI, но их правила и все controls ещё требуют прохода. Графический viewer/редактор выделяется отдельно в UI audit.

## Core/AI и требования

Storage, normalization, graph queries и rendering projections относятся к core; extracting/retyping text запросы — LLM use case, entity embeddings — inference proxy. Graph DB не требует отдельного graph server по текущей семантике. Новая модель должна сохранять provenance/source IDs, типизированную relation identity, conditional commit по source version, protection/TTL и best-effort status. Отдельно решить, является ли каждый extraction обязательным и нужен ли durable backlog.

Rust graph/storage alternatives исследуются после полного GUI/maintenance inventory. Не превращать текущую GraphController/GraphStore пару автоматически в два целевых сервиса.
