# История и память: пользовательские операции, хранение, подготовка к генерации

**Цель:** собрать сквозной функциональный контракт данных персонажа без повторения структуры Python-контроллеров. Исследованы entrypoints сценариев, API чтения/записи и UI maintenance. Источник — локальный `CodeNow.zip`, static source review. Отдельные документы: [история](history.md), [память](memory.md), [сжатие](history-compression.md), [RAG](rag.md), [UI действия](../02-ui/character-library-and-maintenance-actions.md).

## CAP-STORE-LIFE-001 — четыре разных состояния диалога

| Слой | Как появляется | Что используется при генерации | Как виден пользователю | Исходник |
|---|---|---|---|---|
| Активная история | Успешно сохранённые сообщения/вложения | Recent window, role/speaker, LLM context | Chat history, delete/edit/regenerate, snapshot | `src/managers/history_manager.py:1082-1138,1273-1319,1518-1559`; `src/controllers/chat_controller.py:1309-1685` |
| Архивированная история | TTL или компрессия переводит `is_active=1 → 0` | Не обычная active window, но может участвовать в RAG search | Maintenance и RAG provenance | `src/managers/history_manager.py:1447-1500,1564-1603` |
| Long-term memory | Manual/LLM-derived facts/islands/seeds | Отдельные system blocks с active memory и islands | Memory manager, prompts, RAG/graph; отдельные maintenance actions | `src/managers/memory_manager.py:559-653,987-1115,1424-1520` |
| Summary/working context | Post-response compression, layered summaries, текущий task state | Сжатое описание старых turn и текущий пользовательский context | Context viewer/status; не равен истории SQLite | `src/controllers/history_controller.py:112-224,516-651,771-860,1306-1525`; [compression](history-compression.md) |

В отдельном измерении — `forgotten` память (не постоянный prompt, но может участвовать в поиске) и `deleted` память (soft-delete). История использует также `is_deleted`, поэтому `is_active=0` **не** значит «удалено». Игровой Unity world state и события также не являются пользовательским сообщением истории: они имеют собственные provenance и lifecycle.

## CAP-STORE-LIFE-002 — загрузка, пагинация и UI-проекция

`HistoryManager.load_history()` загружает **для одного `storage_key`** все активные не удалённые сообщения по `id ASC`, плюс сохранённые variables; возвращает shape `{fixed_parts:[],messages:[...],temp_context:[],variables:{...}}` (`history_manager.py:1082-1138`). `get_total_messages_count` считает такой же active set; `get_recent_messages(limit,offset)` читает `id DESC` с limit/offset и разворачивает итог для UI в хронологический порядок (`:1505-1559`). Следовательно, важны оба API: полный контекст для domain logic и постраничное отображение для пользовательского scrollback.

`HistoryUiProjector.project_for_ui()` (`src/managers/history_ui_projector.py:44-138`) преобразует роли по speaker/sender/target, оставляет роль player для сообщений игрока, отображает реплики других персонажей как assistant с меткой speaker, а TV observation вставляет как отдельную content part. `event` проецируется в `system`; когда segments имеют несколько targets, не дублирует единственный `speaker → target` заголовок — дальнейшая разбивка выполняется renderer. Это **presentation projection**, не изменение storage role. Реализация Rust не должна навязывать историю из UI-пузырей в БД.

Мультимодальность хранится через `content` и `meta_data`; исторические base64 images могут выноситься в файлы, при восстановлении представлены content parts и hints (`history_manager.py:265-327,418-650`). Сохранение snapshot JSON и отдельное сохранение variables — независимые операции, не универсальный backup всех доменов.

## CAP-STORE-LIFE-003 — операции над историей

| Сценарий | Действие пользователя/триггер | Изменение данных | Runtime effect |
|---|---|---|---|
| Добавить turn | Завершение LLM/game ответа | Batch user + assistant per recipient, message identity/provenance, commit event | Отдельно доставка в Unity и озвучка; multi-recipient transaction отсутствует |
| Удалить одно сообщение | Context action | `is_deleted=1`/inactive for selected ID in текущем character scope | Убирает retry/cache, перезагрузка UI |
| Редактировать | Message context action | Delete selected-and-after, исходный text переносится в composer | Новая отправка — отдельная операция |
| Regenerate last/from | Chat action | Удаление suffix, повторная отправка user/system payload | Новая генерация; прежние effects не отменяются автоматически |
| Export snapshot | GUI save | JSON видимой active history + variables в `Histories/.../Saved/` | Сохраняется путь экспортированного файла |
| Import snapshot | GUI load | Merge variables + sync messages, не полный reset приложения | Reload текущей истории |
| TTL history | Maintenance button/config | Старые active rows переходят в архив `is_active=0` | Архив можно искать через RAG, не показывать в active scrollback |
| Compression | Context overflow/post-response | Old prefix archived, summary committed, optional memory candidates | Более короткий prompt window, фоновые статусы |
| Purge deleted | Explicit maintenance | Физический delete soft-deleted + optional backup JSON + derived embeddings | Не путать с «clear conversation» |
| Clear history | Explicit reset | Scope rows помечаются inactive/deleted | Дополнительные character variables/memory/graph reset через orchestrated route |

**Источники:** `src/controllers/chat_controller.py:1309-1685,1790-1870`; `src/managers/history_manager.py:1140-1242,1394-1500,1564-1717`; `src/controllers/gui/character_settings_logic.py:894-1039,1525-1668`; `src/controllers/history_controller.py:394-516,771-860`.

## CAP-STORE-LIFE-004 — долговременная память и обслуживание

1. **Fact insertion / updates:** факт имеет `character_id`, `eternal_id`, содержание, приоритет, timestamps и состояние `active/forgotten/deleted`; additions могут объединяться по лексической близости (`src/managers/memory_manager.py:559-653,968-1115`). Его `eternal_id` — domain identity внутри персонажа; SQLite row id — другая сущность.
2. **Memory islands:** `relationship`, `opinion`, `preferences`, `commitments_conflicts`, `language` — отдельные карточки с инвариантом одной актуальной записи на тип/персонажа, не обычные capacity-bound facts (`memory_manager.py` island helpers; [memory](memory.md)).
3. **Capacity and TTL:** бюджет фактов, авто-забывание, старение/частота использования, ручной TTL; `forgotten` остаётся в хранилище для retrieval (`memory_manager.py:1126-1367`; GUI `rag_memory_controller.py:442-469`).
4. **Maintenance:** dedup/merge пользовательских и extracted facts, backup-before-purge по запросу (`memory_manager.py:1038-1236,1382-1411`), отдельно graph extraction/GC. Не воспринимать «почистить память», «очистить историю», «переиндексировать embeddings» как один и тот же use case.
5. **Prompt rendering:** `get_memory_message_blocks()` отдельно строит `<memory_islands>` и `<active_memory>`, использует templates `Structural/memory_*.txt`, excludes deleted/forgotten (`memory_manager.py:1413-1499`); RAG retrieval — дополнительный условный контур.
6. **Indexes:** embedding для сообщения асинхронно планируется **после** SQL commit; reindex missing/full и модельные ID не являются транзакционной частью обычного insert. В GUI `rag_memory_controller.py:56-99,133-136` виден separate missing count и ручной reindex.

## CAP-STORE-LIFE-005 — явные maintenance операции GUI

В `src/controllers/gui/character_settings_logic.py:894-2294` доступны: purge deleted history/memory (per-character либо bulk), clear history per-character/all, migrate old histories, restore legacy memory, migrate DB→structured and back, history dedup per-character/all, reindex missing per-character/all, full reindex per-character/all, export DB per-character/all, import DB per-character/all с optional remap character identity. В `src/controllers/gui/rag_memory_controller.py:133-590` отдельно доступны reindex missing, extraction current/all, skip-existing, TTL memory/history/graph, graph GC preview/apply. Наличие этих отдельных кнопок и режимов означает сохранение раздельных **пользовательских возможностей**, хотя новый UI не обязан воспроизводить текущие виджеты.

Модель состояния фоновой задачи: scheduled → running → progress/status → stop requested → completed/failed/cancelled, с самостоятельным владением задачей, UI может закрыть окно. Это наблюдение контракта, не предложение переносить `TaskWorker`.

## Условия, инварианты и критерии паритета

- Per-character scope важен для каждой data operation; multi-character batch не обязан быть одной SQL transaction, но пользователь должен видеть частичный исход.
- Message ID, row ID, sender/target, actor session ID, memory eternal ID и embed source ID — независимые идентичности; нельзя бездоказательно объединять.
- Активный UI scrollback, LLM prompt window, архив для RAG, memory/islands, derived embeddings и graph — разные представления одних либо связанных событий, с разными lifecycle.
- Restore/snapshot и full-app backup — разные операции; новая реализация должна явно описывать охват import/export, compatibility и подтверждение destructive operations.
- Обновление derived index не должно трактоваться как успешная запись первичного сообщения; status «индекс не готов» не должен скрывать сохранённые данные.
- Нужны проверяемые сценарии загрузки истории, пагинации, user edit/regenerate, auto/manual compression, TTL, delete vs archive vs purge, cross-recipient fanout, memory islands, GUI reindex/export/import.

**Не закрыто динамически:** cross-storage fixture тесты, Windows file locks, Qt reload, реальные LLM summaries и model embeddings. Этот документ не исследует дефекты старого кода отдельно, не выбирает архитектуру и не предлагает исправления.
