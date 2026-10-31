# Обслуживание данных, редактор БД и индексы

Статус: ACTIVE/CONDITIONAL. Исследованы Python GUI entrypoints и основные реализации. Пользовательская БД не открывалась, изменения и удаление не выполнялись. Это описание возможностей и текущих ограничений, не требование воспроизводить SQL-редактор или алгоритмы в новой архитектуре.

## Редактор данных

CAP-DATA-004. Просмотр БД открывается для выбранного персонажа или всех. Отдельное Qt QSQLITE connection к Histories/world.db использует WAL и busy timeout5s. Вкладки: история, память, переменные, изображения; при наличии таблиц — embeddings, сущности, отношения и граф. Есть сортировка, фильтры по колонке, поиск, скрытие удалённых, дополнительные колонки, автоматическая высота строк, refresh/maximize и копирование ячейки.

Фильтры поддерживают равенство, contains/start и пустоту; поиск применяется ко всем доступным текстовым колонкам или одной. SQL LIKE/literal escaping реализован; NOCASE сам по себе не обещает полноценный Unicode case folding. Большие embedding/BLOB-поля ограничены для просмотра/редактирования по имени колонки.

Это также редактор: отдельная ячейка в multiline dialog, batch edit выбранной колонки, физическое удаление выбранных строк после подтверждения. Операции адресуются по id и выполняют прямой SQL, затем refresh Qt model. Они не проходят через HistoryManager/MemoryManager, не повышают history epoch и не обеспечивают обновление embedding/FAISS/summary/graph/loaded character state. Это существенное отличие от предметного удаления сообщения или памяти. Для таблицы без id соответствующая операция может быть недоступна или завершиться предупреждением.

Images tab показывает до2000 неудалённых multimodal сообщений текущего/all scope, включая сообщения без описания; есть фильтр, описание и thumbnail. Ручное описание записывается в history.meta_data.image_descriptions.manual с сохранением остальных metadata. Это не редактирование файла изображения и не генерация нового embedding. Подробнее: [изображения](images-and-capture.md).

## Обмен данными

CAP-DATA-005. GUI предлагает export/import выбранного персонажа или всех. Export dialog задаёт путь, таблицы history/memories/variables, состояния, даты и дополнительные фильтры. DatabaseManager пишет JSON потоково fetchmany500; embedding-поля исключены. Это отдельный формат обмена, не резервная копия всей world.db: граф, индексы, файловые изображения и все служебные таблицы этим путём не охватываются. Точные selected columns определяются схемой и export options.

Импорт читает JSON целиком, принимает поддержанные таблицы/колонки и исключает id/embedding. Для selected-character UI character_id принудительно заменяется выбранным. History использует INSERT OR IGNORE, memories INSERT, variables INSERT OR REPLACE. Основной import commit/rollback общий для операции; счётчики не следует приравнивать к полноте семантического восстановления истории. Нет общего идентификатора экспортированного dataset и универсальной идемпотентности повторного импорта. Автоматический rebuild производных данных в методе не найден.

Оба GUI path используют TaskWorker/progress/cancel. Export пишет сразу конечный файл; отмена/ошибка может оставить неполный JSON. Наличие кнопки cancel не означает отмену любого блокирующего вызова или rollback уже выполненных отдельных maintenance операций. Fine-tune JSONL/ShareGPT — другой экспорт: [диагностика](diagnostics-and-data-export.md).

## Переиндексация

CAP-RAG-002. Есть текущий character и all-characters операции, режимы missing/full, progress и отмена; GUI task resources ограничивают пересечение соответствующих reindex jobs. All-characters worker обходит персонажей последовательно. Это не глобальная блокировка всех writers БД.

RAGManager.index_all_missing выбирает неудалённые history/memories без embedding текущей модели, генерирует batches, обновляет legacy column и model-aware embeddings, commit по batch. Забытые memory могут попадать в этот scan. После основного прохода возможны sentence и graph этапы. По завершении с updates сбрасывает FAISS history/memories cache. Ошибка после committed batches может дать итог0 при частично обновлённой БД. Source revision перед commit не проверяется.

index_all пересчитывает embeddings всех неудалённых источников текущего персонажа и также commit по batch. В прочитанной полной реализации нет sentence/graph tail и FAISS invalidation. INDEX_CHANGED подписчики найдены в GUI counts/status, не в FAISS cache. При прежнем количестве vectors count-based cache может остаться старым; см. RISK-007. Отмена не откатывает уже committed batches. Полный и missing — разные операции, их названия не гарантируют одинаковое покрытие производных данных.

## Граф: восстановление, очистка и просмотр

CAP-GRAPH-002. Ручное извлечение текущего/all scope собирает историю и user/следующий ответ pairs, вызывает utility generation с graph preset, поддерживает число workers и skip-existing, сохраняет entities/relations; после прохода может запускать GC. В исследованном SELECT нет общего фильтра is_deleted/archive/допустимых ролей. Проверка cancel происходит между единицами работы, не как надёжная отмена уже идущего LLM запроса. Все задания могут быть заранее переданы ThreadPool.

Обработанный message_id отмечается и при exception/пустом generation result. Поэтому processed здесь означает попытку, а не успешный derivation. Следующий skip-existing может пропустить неудачные случаи. Отдельное «удалить весь граф» очищает relations/aliases/entities всех персонажей, но не graph_processed_messages; повторное извлечение с skip-existing не обязано восстановить очищенные данные.

CAP-GRAPH-003. EntityGC — собственные deterministic rules: Unicode normalization, punctuation/transliteration/synonym matching, garbage/weak orphan removal, duplicate merge и rename. Защищённые entities проверяются. Merge перевязывает relations, убирает self/duplicate relations, суммирует mentions и удаляет source. Analyze создаёт план; GUI dry run показывает summary, apply выполняет новый analyze, не утверждает прежний immutable plan. Errors отдельных actions могут логироваться с продолжением; returned action counts не гарантируют соответствующее число реально изменённых строк. GUI progress callback GC глотает exceptions, включая сигнал отмены через callback; requestInterruption не гарантирует прекращение этой операции.

CAP-GRAPH-004. Qt graph view фильтрует character/type, загружает узлы/отношения/aliases, поддерживает drag nodes, pan, zoom0.1–5 и double-click neighbourhood. ПКМ меняет тип person/place/thing/concept напрямую в SQL. Type backfill вызывает utility LLM batches40 с relation context, максимум2000 entities на character за проход; неизвестное/неудачное оставляет unchanged. Нет необходимости переносить Python или inference в core ради canvas: это представление и utility request contract. Полный painter/layout engine пока не прочитан.

## Объединение похожих воспоминаний

CAP-MEM-002. Текущий character: preview кандидатов, затем подтверждение apply. MemoryDeduplicator использует NumPy cosine, O(N²), выбирает dominant vector dimension; threshold зависит от возраста (база0.94), canonical — priority/newness/content length. Берёт active, nonforgotten memory и embeddings, fallback — legacy BLOB. JOIN model-aware таблицы не ограничен model_id: одинаковая размерность не доказывает один embedding space. Несколько моделей могут дать несколько rows одного eternal_id. Это ограничение текущего алгоритма, не требование.

Apply вызывает предметный MemoryManager.merge_memories для каждой пары, считает merged/failed; общего rollback набора нет. Отсутствие NumPy в analyze даёт пустой план, что может выглядеть как отсутствие дубликатов. Новое проектирование должно отдельно задавать exact duplicates, semantic similarity, provenance/aliases и производные данные после merge; текущие эвристики пока не утверждены.

## Источники и границы

Прочитаны основные action paths character_settings_logic (DB viewer/export/import/reindex/dedup), rag_memory_controller extraction/TTL/GC/delete, database_manager export/import, RAGManager index_all_missing/index_all, memory_dedup, EntityGC analyze/apply/merge/delete/rename, entity_typing reclassify, db_viewer filter/search/cell/batch/delete/images/connection lifecycle и graph_view_widget loading/interactions/manual type/backfill. Часть начальных rule tables EntityGC и canvas painter/layout, полная dialog/rendering реализация и все export schema edge cases остаются непокрытыми. Функциональные выводы не основаны на исполнении этих destructive operations.

Требования для проекта с нуля: явные scopes и identities; typed import format/version и outcomes; разделение source и rebuildable derivations; source/index revision; retryable derivation failures; preview/apply policy; отмена и partial completion; portable data вместе с необходимыми referenced artifacts. Конкретный DB/UI/algorithm stack пока не выбран.
