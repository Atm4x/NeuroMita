# Memory/RAG Settings: source-index of registered descriptors (Pass 12)

**Основание:** `src/controllers/gui/rag_memory_controller.py`. По AST извлечены словари с буквальным `key` из 15 сборщиков, которые вызываются через `build_memory_section`/`build_rag_section` (`:1738-1801`). Это inventory **реально собираемых UI descriptors**, а не автоматическое доказательство runtime потребителя каждого параметра или корректности опции. `widget`-фабрики и button groups в эту таблицу не входят; их надо аудировать отдельно.

**Статический результат:** 100 descriptors, 99 уникальных keys. Defaults — локальные UI defaults, не обязательно persistence defaults или настройки сервиса.

## `_build_memory_limits_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `MODEL_MESSAGE_LIMIT` | Message limit (`'entry'`) | `40` | `—` | `src/controllers/gui/rag_memory_controller.py:682` |
| `MEMORY_CAPACITY` | Active memory limit (MEMORY_CAPACITY) (`'entry'`) | `75` | `—` | `src/controllers/gui/rag_memory_controller.py:687` |
| `RAG_MAX_RESULTS` | RAG max results (`'entry'`) | `10` | `—` | `src/controllers/gui/rag_memory_controller.py:694` |
| `ENABLE_WORKING_STATE` | Enable working state (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:702` |
| `WORKING_STATE_MAX_CHARS` | Working state limit (chars) (`'entry'`) | `2000` | `'ENABLE_WORKING_STATE'` | `src/controllers/gui/rag_memory_controller.py:709` |
| `ENABLE_ACTION_MEMORY` | Enable action memory (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:721` |
| `ACTION_MEMORY_RETAIN_LAST` | Keep actions after summary (`'entry'`) | `4` | `'ENABLE_ACTION_MEMORY'` | `src/controllers/gui/rag_memory_controller.py:728` |
| `ACTION_MEMORY_EMERGENCY_MAX_RECORDS` | Emergency action limit (records) (`'entry'`) | `80` | `'ENABLE_ACTION_MEMORY'` | `src/controllers/gui/rag_memory_controller.py:738` |
| `ACTION_MEMORY_EMERGENCY_MAX_CHARS` | Emergency action limit (chars) (`'entry'`) | `8000` | `'ENABLE_ACTION_MEMORY'` | `src/controllers/gui/rag_memory_controller.py:748` |
| `MEMORY_DEDUP_ENABLED` | Deduplicate on insert (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:760` |
| `MEMORY_DEDUP_THRESHOLD` | Dedup threshold (0.5–1.0) (`'entry'`) | `0.8` | `'MEMORY_DEDUP_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:769` |
| `MEMORY_MAINTENANCE_ENABLED` | Background memory maintenance (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:778` |
| `MEMORY_MAINTENANCE_EVERY_MESSAGES` | Maintenance interval (messages) (`'entry'`) | `20` | `'MEMORY_MAINTENANCE_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:785` |
| `MEMORY_FORGET_USE_RETRIEVAL` | Retrieval-aware forgetting (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:793` |
| `MEMORY_TTL_ENABLED` | Enable memory TTL (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:805` |
| `MEMORY_TTL_LOW_DAYS` | TTL for Low priority (days) (`'entry'`) | `15` | `'MEMORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:812` |
| `MEMORY_TTL_NORMAL_DAYS` | TTL for Normal priority (days) (`'entry'`) | `30` | `'MEMORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:819` |
| `MEMORY_TTL_HIGH_DAYS` | TTL for High priority (days) (`'entry'`) | `90` | `'MEMORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:826` |
| `MEMORY_TTL_MODE` | TTL mode (`'combobox'`) | `'access_weighted'` | `'MEMORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:833` |
| `MEMORY_TTL_ACCESS_WEIGHT` | Access count weight (`'entry'`) | `0.5` | `'MEMORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:846` |

## `_build_history_ttl_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `HISTORY_TTL_ENABLED` | Enable history TTL (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:867` |
| `HISTORY_TTL_DAYS` | History TTL (days) (`'entry'`) | `0` | `'HISTORY_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:874` |

## `_build_time_awareness_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `CURRENT_STATE_GAP_ENABLED` | Report pause since last message (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:922` |
| `HISTORY_TIME_GAP_MARKERS` | Mark pauses inside history (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:931` |
| `HISTORY_TIME_GAP_MIN_MINUTES` | Minimum gap to mark (min) (`'entry'`) | `60` | `'HISTORY_TIME_GAP_MARKERS'` | `src/controllers/gui/rag_memory_controller.py:940` |

## `_build_history_compression_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `ENABLE_HISTORY_COMPRESSION_ON_LIMIT` | Compress history on limit (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:960` |
| `ENABLE_HISTORY_COMPRESSION_PERIODIC` | Periodic history compression (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:965` |
| `HISTORY_COMPRESSION_PERIODIC_INTERVAL` | Periodic compression interval (messages) (`'entry'`) | `20` | `—` | `src/controllers/gui/rag_memory_controller.py:970` |
| `HISTORY_COMPRESSION_PROMPT_TEMPLATE` | Compression prompt template (`'entry'`) | `'Prompts/System/compression_prompt.txt'` | `—` | `src/controllers/gui/rag_memory_controller.py:975` |
| `HISTORY_COMPRESSION_PREVIOUS_SUMMARY_MAX_CHARS` | Previous summary limit (chars) (`'entry'`) | `6000` | `—` | `src/controllers/gui/rag_memory_controller.py:980` |
| `HISTORY_COMPRESSION_MIN_PERCENT_TO_COMPRESS` | Compression trigger (× of limit) (`'entry'`) | `1.0` | `—` | `src/controllers/gui/rag_memory_controller.py:985` |
| `HISTORY_COMPRESSION_KEEP_LAST` | Keep last messages after compression (`'entry'`) | `10` | `—` | `src/controllers/gui/rag_memory_controller.py:992` |
| `HISTORY_COMPRESSION_OUTPUT_TARGET` | Compressed history mode (`'combobox'`) | `'layered'` | `—` | `src/controllers/gui/rag_memory_controller.py:999` |
| `HISTORY_COMPRESSION_LAYERED_MAX_SEGMENTS` | Layers: max layers before rollup (`'entry'`) | `6` | `—` | `src/controllers/gui/rag_memory_controller.py:1010` |
| `HISTORY_COMPRESSION_LAYERED_ROLLUP_BATCH` | Layers: how many old layers per rollup (`'entry'`) | `3` | `—` | `src/controllers/gui/rag_memory_controller.py:1017` |
| `HISTORY_COMPRESSION_LAYERED_MAX_CHARS` | Layers: size budget (chars) (`'entry'`) | `8000` | `—` | `src/controllers/gui/rag_memory_controller.py:1024` |
| `HC_PROVIDER` | Provider for compression (`'combobox'`) | `Current` | `—` | `src/controllers/gui/rag_memory_controller.py:1033` |
| `MEMORY_SUMMARY_CANDIDATES_ENABLED` | Extract memory facts on compression (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:1037` |
| `MEMORY_SUMMARY_CANDIDATES_MAX` | Max facts per compression (`'entry'`) | `3` | `'MEMORY_SUMMARY_CANDIDATES_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1046` |

## `_build_rag_core_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_ENABLED` | Enable RAG (requires restart) (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1061` |
| `RAG_SEARCH_MEMORY` | Search in memory (`'checkbutton'`) | `True` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1067` |
| `RAG_SEARCH_HISTORY` | Search in history (`'checkbutton'`) | `True` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1070` |
| `RAG_SIM_THRESHOLD` | Similarity threshold (Sim threshold) (`'entry'`) | `0.3` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1073` |

## `_build_embed_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_VECTOR_SEARCH_ENABLED` | Vector search (`'checkbutton'`) | `False` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1090` |

## `_build_graph_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `GRAPH_EXTRACTION_ENABLED` | Enable entity extraction (`'checkbutton'`) | `True` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1141` |
| `GRAPH_EXTRACTION_INLINE` | Inline mode (main model, no extra call) (`'checkbutton'`) | `True` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1148` |
| `GRAPH_EXTRACTION_REALTIME` | Real-time extraction (after each reply) (`'checkbutton'`) | `False` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1155` |
| `GRAPH_PROVIDER` | Provider for graph extraction (`'combobox'`) | `Current` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1164` |
| `RAG_SEARCH_GRAPH` | Search knowledge graph in RAG (`'checkbutton'`) | `False` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1172` |
| `RAG_GRAPH_MIN_RESULTS` | Min graph results (`'entry'`) | `0` | `['RAG_SEARCH_GRAPH', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1177` |
| `GRAPH_GC_AUTO` | Auto-clean graph (GC) after extraction (`'checkbutton'`) | `False` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1185` |
| `GRAPH_EXTRACTION_WORKERS` | Parallel workers (batch extraction) (`'entry'`) | `1` | `['GRAPH_EXTRACTION_ENABLED', 'RAG_ENABLED']` | `src/controllers/gui/rag_memory_controller.py:1192` |
| `MEMORY_DEDUP_THRESHOLD` | Cosine similarity threshold (`'entry'`) | `0.94` | `—` | `src/controllers/gui/rag_memory_controller.py:1226` |
| `MEMORY_DEDUP_AGE_DECAY` | Age-based threshold decay (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1234` |

## `_build_graph_ttl_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `GRAPH_TTL_ENABLED` | Enable graph TTL (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:892` |
| `GRAPH_RELATION_TTL_DAYS` | Graph relation TTL (days) (`'entry'`) | `0` | `'GRAPH_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:897` |
| `GRAPH_ENTITY_TTL_DAYS` | Graph entity TTL (days) (`'entry'`) | `0` | `'GRAPH_TTL_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:904` |

## `_build_query_tail_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_QUERY_TAIL_MESSAGES` | Query tail messages (1-3) (`'entry'`) | `1` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1334` |
| `RAG_QUERY_EMBED_MODE` | Query embedding mode (`'combobox'`) | `'weighted'` | `—` | `src/controllers/gui/rag_memory_controller.py:1340` |
| `RAG_QUERY_WEIGHT_LAST_USER` | Last user message weight (Weighted) (`'entry'`) | `0.85` | `—` | `src/controllers/gui/rag_memory_controller.py:1346` |
| `RAG_QUERY_WEIGHT_PREV_CONTEXT` | Previous context weight (Weighted) (`'entry'`) | `0.15` | `—` | `src/controllers/gui/rag_memory_controller.py:1351` |
| `RAG_QUERY_TAIL_ROLE_FILTER` | Tail role filter (Weighted) (`'combobox'`) | `'user_only'` | `—` | `src/controllers/gui/rag_memory_controller.py:1356` |
| `RAG_QUERY_TAIL_EXP_DECAY` | Tail weight exponential decay (Weighted) (`'entry'`) | `0.6` | `—` | `src/controllers/gui/rag_memory_controller.py:1362` |
| `RAG_QUERY_TAIL_MAX_CHARS` | Max chars in tail messages (Weighted) (`'entry'`) | `1200` | `—` | `src/controllers/gui/rag_memory_controller.py:1368` |
| `RAG_FALLBACK_KEYWORD` | Keyword fallback on embedding error (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1374` |

## `_build_weights_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_WEIGHT_SIMILARITY` | Similarity weight K1 (`'entry'`) | `1.0` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1389` |
| `RAG_WEIGHT_TIME` | Time weight K2 (history) (`'entry'`) | `0.3` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1392` |
| `RAG_WEIGHT_PRIORITY` | Priority weight K3 (memories) (`'entry'`) | `0.5` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1395` |
| `RAG_WEIGHT_ENTITY` | Entity weight K4 (`'entry'`) | `0.5` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1398` |
| `RAG_TIME_DECAY_RATE` | Decay rate (decay_rate) (`'entry'`) | `0.05` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1401` |
| `RAG_NOISE_MAX` | Noise (serendipity) max (`'entry'`) | `0.02` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1407` |

## `_build_keyword_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_KEYWORD_SEARCH` | Enable keyword search (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1423` |
| `RAG_LEMMATIZATION` | Enable lemmatization (`'checkbutton'`) | `True` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1427` |
| `RAG_RU_STEMMER_ENABLED` | Ru stemmer (fallback without pymorphy2) (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1432` |
| `RAG_WEIGHT_KEYWORDS` | Keyword weight K5 (`'entry'`) | `0.6` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1441` |
| `RAG_KEYWORDS_MAX_TERMS` | Max keywords (`'entry'`) | `8` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1447` |
| `RAG_KEYWORDS_MIN_LEN` | Min keyword length (`'entry'`) | `3` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1452` |
| `RAG_KEYWORD_MIN_SCORE` | Min match score (`'entry'`) | `0.34` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1457` |
| `RAG_KEYWORD_SQL_LIMIT` | SQL search limit (`'entry'`) | `250` | `'RAG_KEYWORD_SEARCH'` | `src/controllers/gui/rag_memory_controller.py:1462` |

## `_build_fts_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_USE_FTS` | Use FTS5 for search (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1477` |
| `RAG_WEIGHT_LEXICAL` | Lexical factor weight (K6) (`'entry'`) | `0.3` | `—` | `src/controllers/gui/rag_memory_controller.py:1482` |
| `RAG_FTS_TOP_K_HISTORY` | FTS Top K History (`'entry'`) | `50` | `—` | `src/controllers/gui/rag_memory_controller.py:1488` |
| `RAG_FTS_TOP_K_MEMORIES` | FTS Top K Memories (`'entry'`) | `50` | `—` | `src/controllers/gui/rag_memory_controller.py:1493` |
| `RAG_FTS_MAX_TERMS` | FTS Max terms in query (`'entry'`) | `8` | `—` | `src/controllers/gui/rag_memory_controller.py:1498` |
| `RAG_FTS_MIN_LEN` | FTS Min term length (`'entry'`) | `3` | `—` | `src/controllers/gui/rag_memory_controller.py:1503` |

## `_build_combine_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_COMBINE_MODE` | Mode (`'combobox'`) | `'union'` | `—` | `src/controllers/gui/rag_memory_controller.py:1518` |
| `RAG_VECTOR_TOP_K` | Vec TopK (`'entry'`) | `0` | `'RAG_COMBINE_MODE'` | `src/controllers/gui/rag_memory_controller.py:1533` |
| `RAG_INTERSECT_MIN_METHODS` | Min methods (`'entry'`) | `2` | `'RAG_COMBINE_MODE'` | `src/controllers/gui/rag_memory_controller.py:1543` |
| `RAG_INTERSECT_REQUIRE_VECTOR` | Require vector (`'checkbutton'`) | `True` | `'RAG_COMBINE_MODE'` | `src/controllers/gui/rag_memory_controller.py:1551` |
| `RAG_INTERSECT_FALLBACK_UNION` | Fallback union (`'checkbutton'`) | `True` | `'RAG_COMBINE_MODE'` | `src/controllers/gui/rag_memory_controller.py:1558` |
| `RAG_TWO_STAGE_FALLBACK_UNION` | Fallback union (`'checkbutton'`) | `True` | `'RAG_COMBINE_MODE'` | `src/controllers/gui/rag_memory_controller.py:1567` |

## `_build_cross_encoder_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_CROSS_ENCODER_ENABLED` | Enable cross-encoder reranker (`'checkbutton'`) | `False` | `'RAG_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1584` |
| `RAG_CROSS_ENCODER_MODEL` | Model (`'combobox'`) | `'MiniLM-L6 v2 (22M, fast)'` | `'RAG_CROSS_ENCODER_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1592` |
| `RAG_CROSS_ENCODER_MODEL_CUSTOM` | HF model name (Custom) (`'entry'`) | `''` | `'RAG_CROSS_ENCODER_MODEL'` | `src/controllers/gui/rag_memory_controller.py:1601` |
| `RAG_CROSS_ENCODER_TOP_K` | Min candidates to rerank (Top-K min) (`'entry'`) | `20` | `'RAG_CROSS_ENCODER_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1608` |
| `RAG_CE_MAX_ITEMS` | CE hard item cap (0 = off) (`'entry'`) | `0` | `'RAG_CROSS_ENCODER_ENABLED'` | `src/controllers/gui/rag_memory_controller.py:1619` |

## `_build_rag_logging_config`

| Key | Назначение (UI label) | UI default | depends_on | Источник |
|---|---|---|---|---|
| `RAG_DETAILED_LOGS` | Detailed search logs (`'checkbutton'`) | `True` | `—` | `src/controllers/gui/rag_memory_controller.py:1644` |
| `RAG_LOG_LIST_SHOW_ALL` | Show all candidates (`'checkbutton'`) | `False` | `—` | `src/controllers/gui/rag_memory_controller.py:1649` |
| `RAG_LOG_LIST_TOP_N` | Log Top N candidates (`'entry'`) | `10` | `—` | `src/controllers/gui/rag_memory_controller.py:1654` |
| `RAG_LOG_LIST_BOTTOM_N` | Log Bottom N candidates (`'entry'`) | `5` | `—` | `src/controllers/gui/rag_memory_controller.py:1659` |

## Важные ограничения чтения матрицы

1. `GRAPH_EXTRACTION_INLINE`, `GRAPH_EXTRACTION_REALTIME`, `GRAPH_PROVIDER` регулируют разные способы получения triples; сам GUI control не подтверждает успешную генерацию графа.
2. `RAG_VECTOR_SEARCH_ENABLED`, `RAG_SEARCH_GRAPH`, `RAG_USE_FTS` и keyword flags включают независимые источники. `RAG_ENABLED` — более широкий gate.
3. `MEMORY_DEDUP_THRESHOLD` встречается в двух секциях с разными UI defaults: `0.8` (лексическая дедупликация) и `0.94` (косинусная). **Это один и тот же persisted key**, который читают `src/managers/memory_manager.py:554` и `src/managers/memory_dedup.py:65`. При реконструкции поведения нужно документировать обе независимые операции и общую конфигурационную границу, а не считать эти поля двумя разными сущностями.
4. `default` в GUI надо сверять с `SettingsManager.get(..., default)` в каждом consumer. Таблица намеренно не подменяет реальную storage/runtime truth.
5. Ключи без буквального `key` (поля динамического embedding widget, RAG pipeline preset, кнопки extract/reindex/GC, provider selectors) представлены в отдельных документах: [RAG flows](../01-functional/rag-query-fusion-reranking-and-result-contracts.md), [operations](../01-functional/graph-maintenance-and-entity-lifecycle.md), [UI](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md).

## Future parity fixtures

- Рендер каждого дескриптора и зависимости от enablement/character selection; сохранение и восстановление UI state.
- Полное сопоставление каждого key с одним или несколькими Core consumers, default, scope, валидацией и live/restart policy.
- Отдельные интерактивные операции (индексация, экстракция, GC, memory dedup) должны возвращать task ID/status и не выводить success из closing dialog.

**Не выполнялось:** Qt E2E, нативный CUDA/embedding inference, сетевые provider requests. Ключи не удалялись, behavior старого кода не исправлялся.
