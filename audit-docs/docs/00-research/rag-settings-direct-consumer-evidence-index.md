# Матрица проверки зарегистрированных RAG/Memory setting keys в runtime-потребителях (Pass 12)

**Scope:** 99 уникальных буквальных settings-key из 100 UI descriptor (`src/controllers/gui/rag_memory_controller.py`). Для каждого ключа AST поиск `ast.Constant` со **строгим совпадением всего значения** по `src/**/*.py`, кроме `src/Lib`, `utils/Testing`, `ui/not_used`, и **без самого** `rag_memory_controller.py` (он одновременно описывает UI и выполняет отдельные служебные операции). Это исследование **source reachability**, а не запуск Core. Всего **275 literal references** на 96 ключей вне UI-builder file; из них у **95 ключей** найден прямой вызов, в котором ближайший call похож на `.get`, `.set`, `.update`, `.snapshot`, `.subscribe` либо `_get_setting`. Синтаксис `.get` сам по себе не доказывает, что это settings service, поэтому каждый случай требует контекстной проверки.

## CAP-SET-RAG-CONSUMER-001 — индекс 99 ключей

| Key | Литералов вне RAG UI builder | Пример в source:line (контекст вызова) | Уровень свидетельства |
|---|---:|---|---|
| `MODEL_MESSAGE_LIMIT` | 10 | `src/controllers/history_controller.py:940` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_CAPACITY` | 8 | `src/managers/memory_manager.py:258` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_MAX_RESULTS` | 5 | `src/controllers/model_controller.py:2021` (`self.settings.get`) | Синтаксический read/write-подобный вызов |
| `ENABLE_WORKING_STATE` | 1 | `src/services/structured_response_capabilities.py:229` (`_setting`) | Прямая строковая ссылка; тип операции требуется проверить |
| `WORKING_STATE_MAX_CHARS` | 1 | `src/controllers/model_controller.py:2356` (`self.settings.get`) | Синтаксический read/write-подобный вызов |
| `ENABLE_ACTION_MEMORY` | 2 | `src/controllers/history_controller.py:225` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `ACTION_MEMORY_RETAIN_LAST` | 1 | `src/controllers/history_controller.py:229` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `ACTION_MEMORY_EMERGENCY_MAX_RECORDS` | 1 | `src/controllers/history_controller.py:236` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `ACTION_MEMORY_EMERGENCY_MAX_CHARS` | 1 | `src/controllers/history_controller.py:243` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_DEDUP_ENABLED` | 1 | `src/managers/memory_manager.py:539` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_DEDUP_THRESHOLD` | 2 | `src/managers/memory_dedup.py:65` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_MAINTENANCE_ENABLED` | 2 | `src/controllers/history_controller.py:470` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_MAINTENANCE_EVERY_MESSAGES` | 1 | `src/controllers/history_controller.py:477` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_FORGET_USE_RETRIEVAL` | 1 | `src/managers/memory_manager.py:547` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_ENABLED` | 1 | `src/managers/memory_manager.py:1249` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_LOW_DAYS` | 1 | `src/managers/memory_manager.py:1260` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_NORMAL_DAYS` | 1 | `src/managers/memory_manager.py:1261` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_HIGH_DAYS` | 1 | `src/managers/memory_manager.py:1262` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_MODE` | 1 | `src/managers/memory_manager.py:1266` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `MEMORY_TTL_ACCESS_WEIGHT` | 1 | `src/managers/memory_manager.py:1268` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `HISTORY_TTL_ENABLED` | 1 | `src/managers/history_manager.py:1455` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `HISTORY_TTL_DAYS` | 1 | `src/managers/history_manager.py:1465` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `CURRENT_STATE_GAP_ENABLED` | 1 | `src/controllers/prompt_controller.py:594` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_TIME_GAP_MARKERS` | 1 | `src/controllers/history_controller.py:1764` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_TIME_GAP_MIN_MINUTES` | 1 | `src/controllers/history_controller.py:1767` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `ENABLE_HISTORY_COMPRESSION_ON_LIMIT` | 2 | `src/controllers/history_controller.py:533` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `ENABLE_HISTORY_COMPRESSION_PERIODIC` | 2 | `src/controllers/history_controller.py:534` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_PERIODIC_INTERVAL` | 1 | `src/controllers/history_controller.py:535` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_PROMPT_TEMPLATE` | 1 | `src/controllers/history_controller.py:1002` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_PREVIOUS_SUMMARY_MAX_CHARS` | 1 | `src/controllers/history_controller.py:1037` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_MIN_PERCENT_TO_COMPRESS` | 1 | `src/controllers/history_controller.py:531` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_KEEP_LAST` | 1 | `src/controllers/history_controller.py:532` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_OUTPUT_TARGET` | 3 | `src/controllers/history_controller.py:187` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_LAYERED_MAX_SEGMENTS` | 1 | `src/controllers/history_controller.py:1440` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_LAYERED_ROLLUP_BATCH` | 1 | `src/controllers/history_controller.py:1441` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HISTORY_COMPRESSION_LAYERED_MAX_CHARS` | 1 | `src/controllers/history_controller.py:1444` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `HC_PROVIDER` | 2 | `src/controllers/history_controller.py:1064` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_SUMMARY_CANDIDATES_ENABLED` | 1 | `src/controllers/history_controller.py:657` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `MEMORY_SUMMARY_CANDIDATES_MAX` | 1 | `src/controllers/history_controller.py:670` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `RAG_ENABLED` | 32 | `src/DSL/dsl_engine.py:651` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_SEARCH_MEMORY` | 5 | `src/managers/rag/pipeline/config.py:315` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_SEARCH_HISTORY` | 5 | `src/managers/rag/pipeline/config.py:316` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_SIM_THRESHOLD` | 2 | `src/controllers/model_controller.py:2022` (`self.settings.get`) | Синтаксический read/write-подобный вызов |
| `RAG_VECTOR_SEARCH_ENABLED` | 20 | `src/controllers/embedding_controller.py:204` (`self.settings.get`) | Синтаксический read/write-подобный вызов |
| `GRAPH_EXTRACTION_ENABLED` | 8 | `src/controllers/graph_controller.py:88` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `GRAPH_EXTRACTION_INLINE` | 3 | `src/controllers/graph_controller.py:91` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `GRAPH_EXTRACTION_REALTIME` | 1 | `src/controllers/graph_controller.py:171` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `GRAPH_PROVIDER` | 3 | `src/controllers/graph_controller.py:226` (`self._get_setting`) | Синтаксический read/write-подобный вызов |
| `RAG_SEARCH_GRAPH` | 7 | `src/managers/rag/pipeline/config.py:317` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_GRAPH_MIN_RESULTS` | 2 | `src/managers/rag/pipeline/config.py:319` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `GRAPH_GC_AUTO` | 0 | — | Нет литерала вне builder; возможен dynamic access |
| `GRAPH_EXTRACTION_WORKERS` | 0 | — | Нет литерала вне builder; возможен dynamic access |
| `MEMORY_DEDUP_AGE_DECAY` | 1 | `src/managers/memory_dedup.py:71` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `GRAPH_TTL_ENABLED` | 1 | `src/managers/rag/graph/graph_store.py:545` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `GRAPH_RELATION_TTL_DAYS` | 1 | `src/managers/rag/graph/graph_store.py:552` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `GRAPH_ENTITY_TTL_DAYS` | 1 | `src/managers/rag/graph/graph_store.py:553` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_TAIL_MESSAGES` | 2 | `src/managers/rag/pipeline/config.py:313` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_EMBED_MODE` | 2 | `src/managers/rag/rag_manager.py:292` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_WEIGHT_LAST_USER` | 1 | `src/managers/rag/rag_manager.py:302` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_WEIGHT_PREV_CONTEXT` | 1 | `src/managers/rag/rag_manager.py:303` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_TAIL_ROLE_FILTER` | 1 | `src/managers/rag/rag_manager.py:323` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_TAIL_EXP_DECAY` | 1 | `src/managers/rag/rag_manager.py:340` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_QUERY_TAIL_MAX_CHARS` | 1 | `src/managers/rag/rag_manager.py:270` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_FALLBACK_KEYWORD` | 0 | — | Нет литерала вне builder; возможен dynamic access |
| `RAG_WEIGHT_SIMILARITY` | 2 | `src/managers/rag/pipeline/config.py:300` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_WEIGHT_TIME` | 2 | `src/managers/rag/pipeline/config.py:301` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_WEIGHT_PRIORITY` | 2 | `src/managers/rag/pipeline/config.py:302` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_WEIGHT_ENTITY` | 2 | `src/managers/rag/pipeline/config.py:303` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_TIME_DECAY_RATE` | 2 | `src/managers/rag/pipeline/config.py:308` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_NOISE_MAX` | 2 | `src/managers/rag/pipeline/config.py:309` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_KEYWORD_SEARCH` | 11 | `src/managers/rag/pipeline/config.py:321` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_LEMMATIZATION` | 2 | `src/managers/rag/pipeline/config.py:326` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_RU_STEMMER_ENABLED` | 2 | `src/managers/rag/rag_utils.py:83` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_WEIGHT_KEYWORDS` | 2 | `src/managers/rag/pipeline/config.py:304` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_KEYWORDS_MAX_TERMS` | 2 | `src/managers/rag/pipeline/config.py:322` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_KEYWORDS_MIN_LEN` | 2 | `src/managers/rag/pipeline/config.py:325` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_KEYWORD_MIN_SCORE` | 2 | `src/managers/rag/pipeline/config.py:323` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_KEYWORD_SQL_LIMIT` | 2 | `src/managers/rag/pipeline/config.py:324` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_USE_FTS` | 12 | `src/managers/tools/builtin/memory_search.py:208` (`self._settings.get`) | Синтаксический read/write-подобный вызов |
| `RAG_WEIGHT_LEXICAL` | 2 | `src/managers/rag/pipeline/config.py:305` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_FTS_TOP_K_HISTORY` | 2 | `src/managers/rag/pipeline/config.py:329` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_FTS_TOP_K_MEMORIES` | 2 | `src/managers/rag/pipeline/config.py:330` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_FTS_MAX_TERMS` | 2 | `src/managers/rag/pipeline/config.py:331` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_FTS_MIN_LEN` | 2 | `src/managers/rag/pipeline/config.py:332` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_COMBINE_MODE` | 7 | `src/managers/rag/pipeline/config.py:344` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_VECTOR_TOP_K` | 2 | `src/managers/rag/pipeline/config.py:346` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_INTERSECT_MIN_METHODS` | 2 | `src/managers/rag/pipeline/config.py:348` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_INTERSECT_REQUIRE_VECTOR` | 2 | `src/managers/rag/pipeline/config.py:349` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_INTERSECT_FALLBACK_UNION` | 2 | `src/managers/rag/pipeline/config.py:350` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_TWO_STAGE_FALLBACK_UNION` | 2 | `src/managers/rag/pipeline/config.py:352` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_CROSS_ENCODER_ENABLED` | 11 | `src/controllers/main_controller.py:446` (`settings.get`) | Синтаксический read/write-подобный вызов |
| `RAG_CROSS_ENCODER_MODEL` | 4 | `src/managers/rag/pipeline/config.py:138` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_CROSS_ENCODER_MODEL_CUSTOM` | 3 | `src/managers/rag/pipeline/config.py:142` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_CROSS_ENCODER_TOP_K` | 3 | `src/managers/rag/pipeline/config.py:356` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_CE_MAX_ITEMS` | 2 | `src/managers/rag/pipeline/config.py:359` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_DETAILED_LOGS` | 2 | `src/managers/rag/pipeline/config.py:338` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_LOG_LIST_SHOW_ALL` | 2 | `src/managers/rag/pipeline/config.py:341` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_LOG_LIST_TOP_N` | 2 | `src/managers/rag/pipeline/config.py:339` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |
| `RAG_LOG_LIST_BOTTOM_N` | 2 | `src/managers/rag/pipeline/config.py:340` (`SettingsManager.get`) | Синтаксический read/write-подобный вызов |

## Три ключа, которых нет вне файла с UI descriptor

- `GRAPH_EXTRACTION_WORKERS`: **не означает отсутствие потребителя**: здесь же, в `src/controllers/gui/rag_memory_controller.py:197`, число worker читается из `SettingsService` при выполнении manual batch extraction.
- `GRAPH_GC_AUTO`: также **читается внутри того же файла** (`src/controllers/gui/rag_memory_controller.py:372`) при завершении batch extraction, чтобы решить вопрос автоматического GC.
- `RAG_FALLBACK_KEYWORD`: индекс нашёл только его UI descriptor (`src/controllers/gui/rag_memory_controller.py:1375`); по данному статическому критерию поведение за пределами UI **UNRESOLVED**. Нельзя объявлять параметр ненужным без анализа косвенных потребителей, alias/migration и manual test.

`ENABLE_WORKING_STATE` имеет внешний literal в `src/services/structured_response_capabilities.py:229`, но через helper `_setting(...)`, а не через стандартный `.get` на ближайшем вызове. Это наблюдаемый пример того, почему «нет прямого SettingsManager.get» не означает отсутствие runtime-потребителя.

## Как пользоваться этой матрицей

1. Найти UI-описание ключа, label/default/depends_on в [полном списке](../02-ui/memory-rag-registered-settings-source-index.md).
2. Открыть consumer source из таблицы и проверить, входит ли он в ACTIVE / CONDITIONAL path через зарегистрированную команду, обработчик, feature gate или фоновую задачу.
3. Различать UI default и runtime default. Даже прямой `.get` в библиотеке может принадлежать словарю payload, а не глобальным настройкам.
4. Для реальных потребителей записать side effect: prompt budget, RAG query, graph extraction, history compression, memory TTL/maintenance, model choice, progress/diagnostics.
5. Конвертировать подтверждённые key→consumer пары в source-based parity tests; не делать автоматический Rust settings schema из старой формы.

## Требования и остаток

- `REQ-SET-RAG-001`: сохранить управляемые пользователем semantic options RAG/Memory/Graph/History, отделяя labels и presentation defaults от сохраняемых domain settings.
- `REQ-SET-RAG-002`: проверить для каждого активного key конкретный downstream reader, диапазон значений, реакцию на изменение live/restart, scope и последствия для фоновых операций.
- `REQ-SET-RAG-003`: settings с несколькими consumer paths не разбивать на новые ID только из-за разного места использования, но отдельно описывать различающиеся функции.

**Остаток до полного GUI/data parity:** контекст каждого из 275 usages, динамические обращения к именам ключей, inherited defaults, алиасы, runtime Qt binding, автоматические изменения из preset/import и E2E на устройстве. Числа 96/99 и 95/99 **не** являются процентами полноты пользовательских функций.
