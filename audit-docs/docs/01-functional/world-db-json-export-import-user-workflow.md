# Пользовательский перенос World.db через JSON: export/import как отдельная функция

**Статус:** ACTIVE через настройки персонажей; `CAP-DATA-WORLD-001—003`. Это **не** fine-tune dataset export и **не** импорт старого memory JSON по directives. Sources: `src/ui/dialogs/db_export_dialog.py`, `src/controllers/gui/character_settings_logic.py:2135-2270`, `src/managers/database_manager.py:1351-1514,1515-1850`.

## Назначение и сценарий

Пользователь может выгрузить из действующей базы выбранного персонажа либо всех персонажей историю, долгосрочную память и переменные; выбрать статусы записей, диапазон дат, фильтры по столбцам и каталог JSON. Затем этот JSON можно импортировать для сохранённого character identity либо переназначить все импортируемые записи другому персонажу. В UI есть отдельные actions `export_db_for_character`, `export_db_for_all`, `import_db_for_character`, `import_db_for_all`.

## Фильтры экспортируемого набора

| Параметр | Поведение исходного интерфейса |
|---|---|
| Data categories | history / memories / variables, хотя бы один флаг обязателен |
| Scope | текущий выбранный character или все; при Character scope должен быть выбран ID |
| Status | active, forgotten, deleted; для history: `is_deleted`, `is_active`; для memories: `is_deleted`, `is_forgotten`; variables не фильтруются по этим статусам |
| Time | all, from, range; поле history.timestamp, memories.date_created; variables без date filter |
| Column filters | JSON dict по таблицам/полям; пример: `{"history":{"role":["user","assistant"]},"variables":{"key":{"like":"quest_%"}}}` |
| Output | выбранный каталог, имя с автодобавлением `.json`; default `db_export_<character|all>_YYYYMMDD_HHMMSS.json` |

Диалог валидирует наличие категории, наличие статуса при выборе history/memories, путь и имя, синтаксис JSON-фильтров. Фильтры по отсутствующим колонкам пропускаются backend; допуск JSON filter object не означает, что произвольный SQL доступен пользователю.

## Формат и обработка данных

`DatabaseManager.export_to_json_file()` записывает UTF-8 JSON с `format="world-db-export"`, `version=1`, `created_at` UTC, `scope`, `options`, `tables`. Каждая таблица передаётся как `columns` и `rows`. Данные читаются `fetchmany(500)` и пишутся в файл по мере выборки, а не целиком в память. Сначала выполняется `COUNT` для progress, затем отдельный `SELECT`; возможны отличающиеся числа при параллельных изменениях базы. Порядок строк: по `id`, по `variables.key`, иначе `rowid`.

Колонки с подстрокой `embedding` исключены при экспорте, и повторно исключаются при импорте. Следовательно **JSON переносит исходные смысловые данные, а не готовый поисковый индекс**. После переноса embeddings потребуют собственного жизненного цикла; текущая операция сама их не переносит.

`import_from_json_file()` читает объект с `tables`, определяет совместимые текущие колонки, исключает `id` и embeddings и применяет различную семантику по таблицам: `history`: `INSERT OR IGNORE`; `memories`: `INSERT`; `variables`: `INSERT OR REPLACE`. `override_character_id`, если передан, заменяет идентификатор персонажа импортируемой строки. Для всех трёх таблиц вызовы идут внутри одного DB transaction с `commit()` и rollback на исключении. `variables` могут перезаписаться, `memories` повторный импорт может продублировать, а `history` зависит от ограничений уникальности конкретной схемы. Это **не** идемпотентный универсальный merge по смыслу записей.

## UI и завершение

Экспорт/импорт запускаются через `TaskWorker` с `use_progress=True` и QProgressDialog; progress callback сообщает счётчики и последовательно обновляет индикатор. Отмена в интерфейсе вызывает `worker.requestInterruption()`, скрывает progress и подавляет последующий dialog; прерывание SQL/файлового цикла в показанных функциях через cancellation token не подтверждено. Успех возвращает текстовые counts и путь; ошибка отображается отдельным сообщением.

## Паритет для будущего Core

**Нужно сохранить функцию**, а не точную SQL-схему: выбор наборов/статусов/дат/фильтров, scopes current/all, явное переназначение character IDs, стабильный перенос содержимого, отсутствие обязательного переноса embeddings, понятную политику duplicate/replace/merge, результаты по таблицам и понятное поведение при частичном отказе/отмене. Текущий `world-db-export` version 1 является форматом, с которым пользователи могли сохранить свои данные; вопрос долгосрочной backward compatibility следует решить отдельно по фактическим образцам.

## Evidence и незакрытые вопросы

`src/ui/dialogs/db_export_dialog.py:16-345` (поля, подтверждение, словарь настроек); `src/controllers/gui/character_settings_logic.py:2138-2270` (доступность, worker/progress, scope); `src/managers/database_manager.py:1351-1514,1515-1850` (where clauses, export stream, import transaction). UI тесты/файлы пользователя и полноценный round-trip не запускались. Не проверялись table schema migrations в удалённых релизах, огромные JSON, IO во время concurrent writes, graceful cancellation и загрузка повреждённого JSON; нельзя гарантировать их по статическому аудиту.
