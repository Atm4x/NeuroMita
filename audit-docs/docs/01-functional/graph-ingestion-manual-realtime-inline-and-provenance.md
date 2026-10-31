# Граф знаний: четыре пользовательских варианта пополнения и происхождение данных (Pass 12)

**Назначение:** описать именно доступные способы построения графа для новой NeuroMita, независимо от `GraphController` и нынешнего Qt. Источники — `CodeNow.zip`, `src/controllers/graph_controller.py`, `src/controllers/gui/rag_memory_controller.py` и `src/managers/rag/graph/*`. Статусы: `ACTIVE` для зарегистрированного GUI/ответного event path, `CONDITIONAL` по флагам, провайдеру и включённому RAG. LLM вызовы и Qt не запускались.

## CAP-GRAPH-INGEST-001: откуда появляются сущности и связи

| Trigger | Условия/источник текста | LLM запрос и данные на выходе | Жизненный цикл |
|---|---|---|---|
| Inline из *structured response* | `MESSAGE_COMPLETED` после записи ответа, `inline_graph_json`, `from_structured_output=True`; RAG/Graph включены | дополнительного вызова генерации нет; JSON уже получен основной моделью | `GraphController._on_message_completed:117-171` → `_store_inline:323-370` |
| Inline из старого `<graph>` блока | Тот же post-message event + `GRAPH_EXTRACTION_INLINE=True` | graph JSON встроен в текстовый ответ, парсится отдельно | `graph_controller.py:133-163,323-370` |
| Realtime после каждого ответа | `GRAPH_EXTRACTION_REALTIME=True`, нет допустимого inline JSON и ответ не помечен `from_structured_output` | отдельная `GenerationService.generate_utility(kind='graph_extract', request_timeout=30.0)` с выбранным `GRAPH_PROVIDER` | `graph_controller.py:165-199,208-321` |
| Manual batch из сохранённой history | четыре команды в Settings `current/all × only-new/redo-all`; RAG enabled; `GRAPH_PROVIDER`, `GRAPH_EXTRACTION_WORKERS` | отдельные utility requests для текстовых пар `Player`/`Character`; timeout 60 секунд; операции по выбранным персонажам | `rag_memory_controller.py:139-439,1136-1245` |

**Порядок выбора:** при подходящем inline payload система отправляет задачу сохранения и возвращается. Structured output без inline payload **не** запускает дополнительную realtime-экстракцию. Если иной inline source отсутствует, realtime разрешён отдельным флагом. Batch — самостоятельное действие пользователя над уже сохранённой историей; оно не запускается автоматически при обычном событии окончания ответа.

## CAP-GRAPH-INGEST-002: идентичность, тегирование и источник факта

1. Source scopes: `character_id` определяет пространство графа; в realtime используется конкретная `character_ref` из завершённого turn (`graph_controller.py:117-145`). В manual batch список персонажей — выбранный в Settings либо все уникальные `history.character_id` (`rag_memory_controller.py:139-171`). Выбранный в Settings персонаж может отличаться от собеседника Sandbox.
2. Realtime text собирается из последней пары `user_input`/`assistant_output` как `Player:` и `Character:`; пустой turn не экстрагируется (`graph_controller.py:130-145`). Batch проходит сохранённые history rows в порядке `history.id`, по возможности объединяет user с следующим non-user, обрабатывает отдельно несовпадающие пары (`rag_memory_controller.py:232-263`). Это не одинаковые гарантии pairing.
3. `parse_extraction_response` → `store_extraction` формирует graph entities и relations. После realtime сохранения имена извлечённых сущностей привязываются к source history и новым фактам памяти через `_tag_history_messages`/`tag_with_entities` (`graph_controller.py:267-319`). При inline пути теги memory могут уже присутствовать (`memories_already_tagged`) и повторную работу пропускают (`:323-370`).
4. Manual batch `only-new` исключает сообщения, уже отмеченные в `graph_processed_messages`, либо являющиеся источником `graph_relations`, по `history.id` и `character_id`; `redo-all` отключает этот фильтр (`rag_memory_controller.py:202-228`). Следовательно **источник графового факта и статус обработки исходного сообщения — разные данные**.
5. Пользовательский граф RAG не равнозначен фактам memory: самостоятельные UI actions `RAG_SEARCH_GRAPH`, `RAG_GRAPH_MIN_RESULTS` выбирают quota и включение графа в результирующий поиск (`rag_memory_controller.py:1167-1185`; [retrieval](rag-query-fusion-reranking-and-result-contracts.md)).

## CAP-GRAPH-INGEST-003: batch и live — разные операционные состояния

**Manual:** подтверждены четыре кнопки + progress dialog; если worker уже работает, вновь открывается progress окна **той же** задачи, не запускается вторая (`rag_memory_controller.py:351-440`). `mode=current` требует выбранного персонажа; `all` enumerates `history` characters. `GRAPH_EXTRACTION_WORKERS` выбирает последовательное исполнение либо `ThreadPoolExecutor` по истории; `stop_event` даёт cooperative stop. По finish возможен автоматический запуск GC при `GRAPH_GC_AUTO`, иначе показывается processed count (`:350-390`). Это completion обработки batch, не гарантия, что у каждого input появились сущности.

**Realtime:** один pending Future на персонажа ограничивает параллельную post-response экстракцию; задачи отправляются в bounded background pool, при насыщении возможен пропуск (`graph_controller.py:165-205`). Состояние ready provider и наличие реальной model capacity должны проверяться отдельно; это не та же очередь, что пользовательский installer.

**Inline:** принимает уже извлечённое содержимое LLM и не требует отдельной GenerationService-операции. Inline/Realtime и manual batch могут порождать одинаковые типы entities, но имеют разные источники, ссылки на сообщения и частоту. Не переносить current Python controller decomposition в целевую Rust domain model.

## Контракт функций, не баги старого кода

- **REQ-GRAPH-INGEST-001:** моделировать три источника (`inline structured`, `inline legacy`, `utility request`) и четвёртый manual batch orchestration; не сводить всё к одному cron job.
- **REQ-GRAPH-INGEST-002:** сохранить `character_id`, `source message`, entities, relations, source/provenance tagging и отличать request accepted / extraction performed / data persisted / RAG visible.
- **REQ-GRAPH-INGEST-003:** поддержать четыре batch selection modes, независимые progress/cancel, bounded concurrency и режим only-new; факт наличия placeholder/settings не считать работой Graph AI.
- **REQ-GRAPH-INGEST-004:** отдельное пользовательское решение о включении в RAG, quota и обслуживании TTL/GC; граф не должен автоматически заменять обычную память/историю.

**Future validation:** structured inline → tags/history/memory; legacy inline; provider realtime успешный/пустой/недоступный; быстрое последовательное завершение двух ответов одного персонажа; different character concurrently; batch selected/all only-new/redo; access to RAG quota; закрытие и повторное открытие progress; отмена. В текущем проходе это **планы проверки**, не выполненные интеграционные тесты.

**Связанные документы:** [граф](knowledge-graph.md), [обслуживание](graph-maintenance-and-entity-lifecycle.md), [RAG source rendering](rag-context-injection-and-source-rendering.md), [Settings keys](../02-ui/memory-rag-registered-settings-source-index.md).
