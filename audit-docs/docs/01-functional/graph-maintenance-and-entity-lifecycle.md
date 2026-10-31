# Граф знаний: очистка, слияние, типизация и удаление

**Срез:** локальный `CodeNow.zip`, 2026-10-30. **Тип проверки:** статический source audit; ни одна destructive операция не запускалась. **Статус:** `CONDITIONAL` — ветви доступны через RAG settings / DB Viewer при наличии базы, нужных таблиц и сервисов. `ACTIVE` для точного GUI входа только при выполнении этих условий. **Границы:** здесь рассматривается maintenance семантика; extraction/retrieval см. [knowledge-graph](knowledge-graph.md), все окна БД/навигация целиком ещё не закрыты.

## CAP-GRAPH-MAINT-001 — правила и операции GC

**Назначение.** Удалить шумовые сущности и пустые orphan nodes, нормализовать названия и объединить дубли в knowledge graph, не превращая это в обычную очистку истории. Входы: таблицы `graph_entities`, `graph_relations` в SQLite для каждого `character_id`; выходы: `GCPlan`, после подтверждённого применения — изменённые строки графа и счётчики.

**Доказанный reachability:** `src/controllers/gui/rag_memory_controller.py:1214-1219` регистрирует кнопки GC и Preview GC; `_run_entity_gc:515-597` собирает список **всех** персонажей с сущностями, для каждого выполняет `EntityGC.analyze()`, затем `EntityGC.apply(plan)` кроме preview; команда работает через `TaskWorker`. `src/controllers/gui/rag_memory_controller.py:368-378` также вызывает `_run_entity_gc(gui)` **после окончания ручной batch-extraction**, если установлен `GRAPH_GC_AUTO`. Текст настройки (`:1185-1190`) обещает «после каждой экстракции», но подтверждённая реализация в данном UI callback — завершение **batch**; автоматическая GC после realtime graph extraction через `GraphController` этим источником **не подтверждена**.

**План:** `src/managers/rag/graph/entity_gc.py:301-379` загружает узлы и связи отдельно; исключает защищённые `is_protected` от удаления, rename/merge и orphan processing. `:90-125` распознаёт мусор по длине, чисто числовому имени, stop-word, префиксу-предикату и фрагментам предложения. `:325-337` удаляет хвостовую пунктуацию. `:237-297` вычисляет normalized identity через lowercase/NFC, очистку знаков, whitespace и кириллическую транслитерацию, а также hardcoded synonyms. Канонический узел выбирается по `mention_count`, затем предпочтению `person`. `:361-377` считает orphan только узлы с <=1 упоминанием и без связей. Это **эвристическое решение о данных**, не гарантия истинной семантической эквивалентности разных имён.

**Исполнение:** `entity_gc.py:383-427` проходит каждое действие одного плана, ловит и логирует **отдельные исключения**, затем коммитит изменения, сделанные до/после ошибки. Возвращаемые `counts` — число действий без исключения, **не** строгая сумма реально изменённых строк. `_do_delete:429-448` фильтрует по персонажу и protection; `_do_merge:450-489` перенаправляет subject/object relation, убирает дубли и self-loops, суммирует упоминания, удаляет старый entity; `_do_rename:491-505` либо переименовывает в lower-case, либо вызывает merge при конфликте имени. Merge и rename изменяют identity/relations; read projections/derived embeddings или alias references в этих методах явно не обновляются: состояние внешних индексов **требует отдельной проверки**, не объявлять подтверждённой порчей данных.

**Отказы и гонки, выведенные статически:**

- `analyze` и `apply` используют **разные** соединения/времена (`:301-308` против `:383-389`), между ними план может устареть. `apply` не сверяет исходную ревизию объектов и не перепроверяет protected для `_do_merge`/`_do_rename`. Риск относится к concurrent writes, не воспроизводился.
- `_do_delete` возвращает `None` и может пропустить protected, но caller всё равно увеличивает `counts["delete"]` (`:393-395,429-447`); аналогично no-op `UPDATE` не проверяет `rowcount`.
- Исключение одной операции не отменяет остальные, то есть «GC завершён» не означает атомарное выполнение всей очистки (`:391-416`). Ошибка SQL уровня whole-plan пытается rollback только в outer handler.
- `progress.canceled → worker.requestInterruption()` зарегистрирован (`rag_memory_controller.py:590`), но `_do_gc` не опрашивает interruption; исключения прогресса проглатываются (`:547-552`). Из кода **не следует** надёжная отмена GC по нажатию Cancel.

**Requirements для новой реализации (не проектирование архитектуры):** `REQ-GRAPH-MAINT-001` — preview и commit должны работать с одной проверяемой identity/version графа или повторной проверкой защищённых объектов; `REQ-GRAPH-MAINT-002` — результаты действий отделяют `attempted`, `changed`, `skipped`, `failed`, а UI не объявляет частичный commit полным; `REQ-GRAPH-MAINT-003` — определить явную семантику cancellation и whole-graph vs character-local scope; `REQ-GRAPH-MAINT-004` — после merge/rename согласованно инвалидировать или перестроить все производные данные, если они зависят от entity id/name.

**Validation (не исполнялось):** protected в момент preview и изменённый protected до apply; два concurrent GC; успешный merge с alias/embedding/processed-ledger; SQL error на середине плана; отмена в многоперсонажном цикле; idempotent повтор; collision после rename, orphan filter, self-loop handling.

## CAP-GRAPH-MAINT-002 — TTL graph prune

`src/managers/rag/graph/graph_store.py:536-599` — условная cleanup по `GRAPH_TTL_ENABLED`, `GRAPH_RELATION_TTL_DAYS`, `GRAPH_ENTITY_TTL_DAYS`: сначала удаляются незашищённые relations с `created_at` старше порога; затем незашищённые узлы с `last_seen` старше порога **и** без remaining relations. `0` или невалидные настройки ничего не делают. Protected узлы/ребра не удаляются этим путём; отсутствие даты исключает удаление. SQLite `julianday('now')` — политика времени базы. Операция персонаж-локальная; `src/controllers/gui/rag_memory_controller.py:471-492` вызывает её кнопкой для **выбранного** персонажа. SQL/transaction ошибки логируются и метод возвращает counts, а не бросает ошибку; следовательно UI может показать числа без отдельной ошибки при storage failure. Сведения о scheduler автоматического TTL здесь не доказаны.

`REQ-GRAPH-MAINT-005`: сохранить отдельность защищённости, возрастных условий, orphan eligibility и per-character scope; операции должны давать честный committed outcome и explicit error status. Проверить дату NULL, ровно порог, отсутствие связей, protected relation/vertex, I/O exception.

## CAP-GRAPH-MAINT-003 — LLM-классификация типов `thing`

**Reachability:** `src/ui/dialogs/db_viewer.py:1526-1541` добавляет графический tab при наличии таблицы; `src/ui/dialogs/graph_view_widget.py:660-666,937-1054` кнопка Detect types запускает owner-bound `TaskWorker` и `GenerationService.generate_utility(kind="graph_typing", request_timeout=60.0, preset_id=GRAPH_PROVIDER)`. Если Viewer открыт для персонажа, рассматривает только его; без filter собирает всех персонажей, у которых есть `thing`. `GraphStore.get_untyped_entities:432-453` сортирует по упоминаниям и ограничивает максимумом 2000 **на персонажа**. Контекст relation hints ограничен пятью.

`src/managers/rag/graph/entity_typing.py:38-141`: батчи по 40, LLM возвращает JSON `entity_name → person/place/thing/concept`; parser извлекает JSON и отбрасывает остальные типы; валидный не-`thing` приводит к `set_entity_type` в DB. Исключения LLM проглатываются как пустой batch result (unchanged), ошибки отдельной DB update также логируются. Progress вызывается после batch, cancellation передаётся через exception и удерживает уже сделанные изменения (не rollback). `:54-73` ключи сопоставляются по lower-case имени, не по entity ID: одинаковые написания разных сущностей в одном батче получают одну классификацию. В GUI `:1056-1063` закрытие вкладки отменяет только её worker, не внешние переиндексации.

**Manual type editing:** `graph_view_widget.py:855-888` контекстное меню узла (`person/place/thing/concept`) обновляет таблицу по id напрямую через QSqlQuery и затем только локальную node projection. Это отдельный путь, не зависящий от LLM.

`REQ-GRAPH-MAINT-006`: сохранять manual type edit, batch type inference, persona scope, progress, partial cancellation, provider selection; явно декларировать критерий сопоставления model output и ent identity, а не переносить неоднозначное имя как обязательный контракт. Validation: дубли имен, mixed-case, schema-invalid response, missing GenerationService, cancelled after batch, смена персонажа, закрытие tab.

## CAP-GRAPH-MAINT-004 — полное удаление графа

`rag_memory_controller.py:600-656`: GUI проверяет наличие table/row count, требует `Yes` с default `No`, после чего исполняет `DELETE FROM graph_relations`, `graph_entity_aliases`, `graph_entities` **без character_id**; интерфейс подчёркивает удаление **для всех персонажей** и необратимость. Это отдельный destructive use case от GC и TTL, его нельзя заменить на очистку только выбранного персонажа. Требование `REQ-GRAPH-MAINT-007`: explicit all-characters scope и подтверждение должны быть неизменными пользовательскими гарантиями; также требуется предусмотреть identity/process ledger consistency после clear и fencing активных extraction jobs (открытый вопрос).

## Открытые вопросы и ограничения подтверждения

1. Есть ли гарантированная invalidation graph embeddings / aliases / processed messages при merge и full clear с concurrent extraction? Нужен точный schema/DB trigger audit и runtime fixtures.
2. Исполняется ли `GRAPH_GC_AUTO` где-либо после **realtime** (а не batch) extraction? Прямой поиск `GRAPH_GC_AUTO` показывает только UI callback и setting declaration, но dynamic calls полностью не исключены.
3. Корректно ли все UI-операции подтверждают storage outcome при SQL errors? Требует fault injection.
4. Как политика «canonical by mentions» ведёт себя при homonyms/synonyms и protection, не противоречит ли user-edited type?
5. Неполная проверка `GraphViewPage` UI canvas: graph layout/event controls/large graph performance ещё остаются для отдельного UI audit.

## Связанные документы

[Граф знаний](knowledge-graph.md), [обслуживание данных](data-maintenance.md), [состояния GUI](../02-ui/settings-navigation-and-lazy-pages.md), [матрица паритета](../06-design-input/feature-traceability.md), [исследовательские пробелы](../00-research/open-questions.md).
