# DB Viewer / Graph View — пользовательские действия и состояние

**Capability:** `CAP-UI-GRAPH-001`. **Статус:** CONDITIONAL (доступен в основном DB Viewer при наличии таблицы `graph_entities`; код создания зарегистрирован). **Проверка:** source-only `CodeNow.zip`; никакого запуска PyQt, открытия реальной БД или измерений FPS. **Scope:** именно UI projection и действия, а не выбор Rust/Slint/QML фреймворка.

## Вход и функциональное назначение

`src/ui/dialogs/db_viewer.py:1526-1541` регистрирует табличные страницы `graph_entities`/`graph_relations` по наличию таблиц и в `Graph: Visual` создаёт `GraphViewPage` (`src/ui/dialogs/graph_view_widget.py:627+`), если присутствует `graph_entities`. Неуспех создания графического виджета логируется без падения остальных вкладок. `character_id` передаётся как optional: при наличии — выборка ограничена конкретным персонажем; при отсутствии показывается общий граф всех персонажей. Этот режим не гарантирует, что разные персонажи имеют независимые совпадающие имена при визуальной поисковой фильтрации.

## UI действия и их эффекты

| Точка UI | Исходник | Состояние и эффект |
|---|---|---|
| `Filter type` All/person/place/thing/concept | `graph_view_widget.py:644-648,749-752,782-803` | Перезапрос SQLite, замена canvas nodes/edges, сброс раскладки и локальных фильтров |
| `Show all` после выбора node neighbourhood | `:180-205,654-658,739-746` | Возвращает полный набор узлов из уже загруженных данных; не делает новый SQL-запрос |
| `Refresh` | `:668-670,749-752` | Считывает таблицы заново, реконструирует визуальное состояние, сбрасывает positions/zoom-related focus частично (см. код) |
| `Re-layout` | `:672-674,754-760` | Переинициализация позиций, запуск layout timer и счётчика итераций |
| `Reset view` | `:676-679,762-765` | Zoom=1, pan=(0,0), **не** сбрасывает реальное расположение узлов |
| `Ctrl+F`, ввод или закрытие поиска | `:682-698,717-738,208-230` | Подстрока имени или aliases, highlight matching nodes, pan к одному совпадению; без записи в БД |
| ЛКМ drag по узлу / по пустому фону | `:540-548,560-593` | Локальное изменение positions или pan; позиции не сохраняются в SQLite |
| Колесо мыши | `:604-615` | Zoom вокруг курсора в диапазоне 0.1–5.0 |
| Double-click node | `:550-558,180-205` | Фокусный узел и one-hop соседи, повторное двойное на нём выходит из режима |
| ПКМ node → `Type` | `:595-602,855-888` | UPDATE `graph_entities.entity_type` по integer id; немедленное обновление node projection при SQL success |
| `Detect types (LLM)` | `:660-666,937-1054` | Owner-scoped worker, utility provider из GRAPH_PROVIDER, progress/cancel, частично сохраняемые типы; подробности в [graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md) |

## Модель данных и отрисовка

`graph_view_widget.py:767-853` получает nodes через `QSqlQuery`, затем aliases из `graph_entity_aliases` (необязательная таблица), затем edges из `graph_relations` при условии, что **оба** endpoint уже присутствуют в загруженных nodes. Поэтому фильтрация по типу **не показывает** ребро к узлу другого типа; это projection filter, не удаление relation. Toolbar показывает количество загруженных nodes/edges, не полное количество всех DB rows.

`graph_view_widget.py:100-165,233-306` реализует force-directed canvas на `QPainter`: repulsion всех пар узлов внутри distance cutoff, attraction по связям, damping и слабое притяжение к центру. Timer ~30 ms и число iterations ограничено по количеству узлов. Верхняя оценка одного layout step имеет квадратичный перебор пар (`O(V²)`); это **статическое свойство алгоритма**, не измеренный FPS. Независимый Rust GUI должен сохранить перечисленные взаимодействия и визуальную семантику, **не** обязан копировать QPainter или физический layout алгоритм побайтно.

`_GraphCanvas` хранит `_zoom`, `_pan`, dragged/hovered node, neighbor focus, search matches, velocity/layout iterations как presentation-only state. Из кода `set_data` следует, что refresh не просто перерисовывает, а сбрасывает текущую локальную выборку, search matches и neighbor view; при смене типа в SQL локальная node projection обновляется без полного reload.

## Риски/неясности

1. `GraphViewPage._load_from_db` формирует фильтр SQL через собственную `_sql_esc` для `character_id` и выбранного типа (`:785-792`); значения предварительно экранируются, но для нового Core нужен параметризованный query contract. Это не объявление exploitable SQL injection.
2. `Filter type` скрывает cross-type edges; users могут воспринимать отсутствие связи как отсутствие данных. В UI нужно различать full DB relation set и visible graph.
3. Значения `Graph: Visual` и table editing используют разные виджеты; фоновая retyping/GC/TTL может менять SQLite без немедленного обновления уже открытого canvas. Очевидная точка ручного `Refresh` существует, automatic subscription не подтверждена.
4. Search matches берётся из `set` и выбирает `next(iter(matches))`; если совпадений несколько, конкретный узел первого focus не определён устойчивым сортировочным контрактом (`:215-227`).
5. Требуется QA для больших графов, self-loops, длинных имён, high-DPI, клавиатуры и screen reader; source просмотр не подтверждает результат accessibility.

## Требования и будущая валидация

`REQ-UI-GRAPH-001`: стабильный semantic graph projection с optional character scope, type filter, counted visible nodes and edges; `REQ-UI-GRAPH-002`: navigation (drag/pan/zoom/reset/focus one-hop/search aliases) и graph tooltip/legend; `REQ-UI-GRAPH-003`: manual type edit и LLM backfill с error/cancellation/progress outcomes; `REQ-UI-GRAPH-004`: отделение долговременных graph mutations от ephemeral view state и явное обновление после внешнего изменения graph.

Проверки после реализации: tabs при отсутствующих таблицах, фильтр смешанных типов, оба режима character filter, search по alias, поиск без совпадений, multiple matches, Ctrl+F, zoom bounds, drag while layout running, self-loop, interrupted backfill и external GC while viewer open.

**Связи:** [knowledge-graph](../01-functional/knowledge-graph.md), [graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md), [settings UI](settings-navigation-and-lazy-pages.md), [traceability](../06-design-input/feature-traceability.md).
