# RAG: сбор запроса, объединение источников, ранжирование и итог для LLM

**Тип исследования:** поведенческий контракт для полного функционального паритета без копирования Python классов. **Статус:** `CONDITIONAL`, условие основного запроса `RAG_ENABLED` или explicit search через tool overrides. Изучен pipeline исходного `CodeNow.zip`; embedding и CrossEncoder runtime не запускались.

## CAP-RAG-RANK-001 — сформировать запрос с контекстом и идентичностью персонажа

**Источник:** `src/managers/rag/rag_manager.py:821-879`, `src/managers/rag/pipeline/query_builder.py:16-81`, `src/managers/rag/pipeline/types.py:21-54`.

Внешний вызов принимает `query`, `limit`, `threshold` и optional `config_overrides`. Если overrides `None`, автоматический поиск требует `RAG_ENABLED`; переданный **пустой словарь** `{}` означает явный поиск, который можно выполнить при выключенном automatic injection. Конфигурация строится из текущих settings, после чего known overrides меняют отдельные параметры поиска, а не произвольные поля.

QueryBuilder готовит исходный запрос и expanded query из последних `RAG_TAIL_MESSAGES` активной истории; keyword retrieval использует очищенный пользовательский текст и расширенный контекст, дедуплицирует lemmatized keywords с пределом `kw_max_terms`; query embedding может отсутствовать. С последнего активного сообщения считываются `speaker`, `target`, `participants` и вводятся в поисковую `QueryState`, отделённую от текущей UI-selected identity. Если embedding отсутствует, но включены keyword или FTS, поиск может продолжиться по lexical каналам. Если отсутствуют embedding, keywords и FTS, функция немедленно возвращает пустой результат.

## CAP-RAG-RANK-002 — выбрать источники и политику комбинирования

**Источники:** `rag_manager.py:884-986`, `src/managers/rag/pipeline/combiner.py:8-224`, `types.py:41-87`.

Retriever buckets: `vector` (только при наличии query_vec и включённом vector), `keyword`, `fts`, `graph` (при включении). Ошибка одного retriever возвращает пустой bucket, не прерывая остальные. `combine_mode='vector_only'` отсекает ненужные retrievers ещё до выполнения. При объединении кандидат определяется парой `(source, id)`, в которой history и memory не могут случайно слиться при равном числовом id. `Candidate.merge_from` выбирает максимальные feature scores, заполняет отсутствующие meta/content, а не перезаписывает всю запись.

| Combiner | Семантика выбора кандидатов |
|---|---|
| `union` | Объединить все buckets, один кандидат `(source,id)`, слить признаки |
| `vector_only` | Только vector, optional `vector_top_k` по сходству |
| `intersect` | Кандидат найден минимум `intersect_min_methods`; optional require vector; пустая выборка может fallback to union по настройке |
| `two_stage` | Vector задаёт **состав ID**, lexical и graph добавляют только признаки к тем же ID; при пустом vector optional fallback union |
| `rrf` | Reciprocal Rank Fusion суммирует `1/(k+rank+1)` по позициям кандидата в buckets; `use_rrf` приоритетнее выбора combine_mode |

**Существенный функциональный факт:** пользовательский комбинированный режим определяет не только сортировку, а **право кандидата вообще войти в результат**. Поэтому одинаковые vector/lexical hits при разных presets закономерно дают различные наборы воспоминаний. Для точного паритета нужны fixtures по candidate sets, не только числовому score.

## CAP-RAG-RANK-003 — enrich, linear score, optional CE и quota графа

**Источники:** `rag_manager.py:986-1099`, `src/managers/rag/pipeline/reranker.py:8-65`, `src/managers/rag/pipeline/cross_encoder.py:188-262`, `src/managers/rag/pipeline/enrichers/common.py`.

После combiner применяются три enrichers: `time`, `entity`, `priority`. Базовый rank считает linear weighted признаки `sim, time, priority, entity, keyword, lexical` плюс optional controlled noise; в RRF mode вместо sim/kw/lex используется fused rank, но time/prio/entity остаются. Graph-кандидаты получают множитель `K7`. По умолчанию возможна случайная добавка через генератор, либо deterministic seed в настройках; новую реализацию нельзя объявлять детерминированной без проверки `noise_max` и `noise_seed`.

При разрешённом `cross_encoder_enabled` и выбранной модели первые `effective_top_k=min(pool,max(top_k,int(pool*ratio)))`, capped by `ce_max_items`, проходят дополнительный AI rerank с параметрами alpha и early-exit. Если CE не запущен или отказал, остаётся base-rank, а не безусловная ошибка всего RAG. CE — отдельная inference-граница Python AI, тогда как подготовка ID/scopes/candidates является core-поведением.

Итоговые candidates сортируются, ограничиваются `limit`. Настройка `graph_min_results` пытается поднять до N graph-кандидатов в итоговый top, **если** они присутствуют ниже cutoff; она не создаёт graph facts при их отсутствии и не является универсальной гарантией N. Поиск запускает асинхронный access tracking для возвращённых memory (`access_count`,`last_accessed`) и graph entities (`access_count`), что затем влияет на пользовательскую семантику забывания/важности. Источники response преобразуются в публичные словари `source,id,content,score,features` и source-specific meta, понятные downstream LLM/GUI.

## Пользовательские сценарии и контроль паритета

1. В выключенном auto-RAG вызвать explicit memory tool; получить search, не меняя глобальную опцию автоматического RAG.
2. Два сообщения одинакового текста от разных персонажей; search учитывает owner character, actors последних реплик и source IDs.
3. Vector отсутствует, FTS и keywords доступны; lexical-only не считается исключением из нормального сценария.
4. `intersect` и `two_stage` с разными комбинациями buckets возвращают разные source-id sets; `rrf` учитывает порядок внутри каждого bucket.
5. CE installed but not loaded / failed — recoverable optional second-stage, base results доступны.
6. Graph candidate имеющий низкий базовый score, но попавший в available graph-min reservation, появляется в итоговом result; при отсутствии graph ниже cutoff ничего не добавляется.
7. Возвращённый result имеет provenance и наблюдаемый score; чтение памяти может обновить её статистику асинхронно, не блокируя ответ модели.

**Требования:**

- `REQ-RAG-RANK-001`: сохранять явное различие auto и explicit search, preset overrides и context-aware QueryState.
- `REQ-RAG-RANK-002`: реализовать функциональные semantics selectable union/vector/intersect/two-stage/RRF и identity `(source,id)` без потери атрибуции.
- `REQ-RAG-RANK-003`: enrichers/time/prio/entity/graph и CE stage — независимые наблюдаемые свойства retrieval, которые могут быть конфигурируемы и fallback при недоступности optional модели.
- `REQ-RAG-RANK-004`: limit, available graph quota, public source meta и access statistics не теряются при дальнейшей миграции storage.

**Не подтверждено:** точные GPU vector/CE scores, соответствие всех продуктов model preset, полная latency/perf стоимость, scoring quality, real-world time dependent selection; реальные inference/DB/GUI интеграционные тесты не запускались. Подробности [corpora/indexing](rag-storage-retrieval-and-indexing-modes.md), общий [RAG](rag.md) и [tool search](tools-and-web.md).
