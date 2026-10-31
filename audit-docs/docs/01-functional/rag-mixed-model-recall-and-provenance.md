# RAG: смена модели, смешанный recall и происхождение результатов

Статус: CONDITIONAL, уточнение уже описанного RAG. Source snapshot подтверждён в [базе Pass13](../00-research/pass13-import-and-source-baseline.md). Проверка ниже использует SQLite :memory:, без пользовательской БД, app bootstrap, модели или сети.

## Путь запроса и модельный scope

`RAGManager.search` создаёт QueryState, выбирает vector/keyword/FTS/graph по конфигурации, собирает buckets, объединяет candidates, добавляет time/entity/priority, линейный и optional cross-encoder ranking, graph quota и public output. Ошибка одного retriever даёт пустой bucket с log, не общий запрет остальных. vector_only предварительно исключает остальные retrievers; поэтому сообщение «fallback FTS/keyword» не гарантирует fallback в любом combine mode. Two-stage при непустом vector set добавляет features только уже найденным IDs; новые lexical IDs входят лишь через разрешённый empty-vector fallback. RRF включается отдельным флагом выше выбора обычного combiner, но не возвращает уже исключённые retrievers.

History vector identity: `(character_id, history.id, model_name)`; memory: `(character_id, eternal_id, model_name)`. Document и sentence repositories фильтруют выбранный model key. В новых embedding presets remote key — `provider:model`, local — resolved model name; старые/совместимые config paths также существуют. Key не включает полный URL, model artifact revision, dimensions, prefix и все extras, поэтому равенство key не доказывает равенство всего embedding space.

History recall берёт inactive, nondeleted rows; активная history участвует в построении запроса/actor context, не тем же SQL scan. Memory scope исключает deleted и island types, учитывает active/forgotten mode при наличии колонки. FTS5 LEFT JOIN выбранного embedding допускает документ без vector этой модели: lexical result может иметь sim0. KeywordOnly ищет source legacy `embedding IS NULL`, а не отсутствие row для выбранного model key. После смены модели это разные множества.

## Проверка source SQL на изолированных данных

В Python-B из AST загружены только неизменённые классы HistoryRepository/MemoryRepository и вызваны их реальные SQL methods. Imports приложения не выполнялись. Fixture: персонажиA/B, одинаковый memory eternal_id7, history1 с old vector и legacy BLOB, history2 без vector, history3 другого character и history4 active.

| Вызов | Наблюдаемый результат |
|---|---|
| History vector old | `[1]` |
| History vector new | `[]` |
| FTS alpha с model new | history1 и2, оба без выбранного embedding |
| Keyword alpha | только history2; old-model history1 не входит из-за legacy non-NULL BLOB |
| Memory vector new дляA | eternal_id7 с contentA, без записиB |

Assertions прошли, exit0. Это проверка repository filtering/source identities и SQLite FTS5, не полный inference/ranking/prompt E2E. Missing schema/SQL errors в repositories могут возвращаться как пустой результат, поэтому empty result и отсутствие совпадений не всегда различимы в текущем контракте.

## Graph и итоговая provenance

GraphStore хранит одну entity embedding row по entity_id, с model_name как metadata; `find_by_embedding` фильтрует character, но не model_name. Несовпадающий размер vector отбрасывается per entity по exception; одинаковый размер не подтверждает совместимость space. Keyword entity matching остаётся отдельным additive/fallback источником, затем загружаются 1-hop relations.

Candidate key — `(source,id)`: одинаковое число у memory/history не объединяет разные источники. Graph ID вычисляется process hash triple, не является durable DB relation identity. Public output сохраняет source/text/score/features и выбранную source metadata; current pipeline не возвращает полный набор model/source revisions/всех recall methods как гарантированный provenance envelope. `source_message_id` relation сам по себе не означает, что он доходит до prompt.

После отбора access tracking выполняется асинхронно для memory IDs и graph names; это не подтверждение, что модель прочитала/использовала результат. Inline/manual/realtime ingestion и processed ledger описаны отдельно в [graph ingestion](graph-ingestion-manual-realtime-inline-and-provenance.md).

## Настройки с особой достижимостью

`GRAPH_EXTRACTION_WORKERS` читается в том же rag_memory_controller, что содержит descriptor; `GRAPH_GC_AUTO` там же запускает GC после manual extraction. Их отсутствие во внешнем literal index не означает отсутствие функции. `ENABLE_WORKING_STATE` читается через helper capabilities. Для `RAG_FALLBACK_KEYWORD` найден только descriptor: поиск по src/extra/scripts Python/JSON не обнаружил consumer. Поведение этого переключателя **не подтверждено**; реальный keyword fallback управляется cfg.kw_enabled, query keywords и combine policies. Не включать неподтверждённый переключатель как обязательное требование паритета.

Источники: embedding_presets resolve_full_config/resolve_preset_config; rag_manager search; pipeline repositories history_repo/memory_repo; vector/FTS/keyword/graph retrievers; faiss_index cache/build; types Candidate/QueryState; graph_store store_entity_embedding/find_by_embedding; rag_memory_controller197/372/1375. Подробные cache/reindex ограничения уже отражены в прежних документах и не считаются новой функцией.
