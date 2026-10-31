# Хранение: первичный контракт SQLite

Статус: частичный schema/storage audit. Источники `src/managers/database_manager.py:17 DatabaseManager`, `:70 __init__`, `:89 _apply_sqlite_pragmas`, `:112 get_connection`, `:273 _ensure_fts5_schema`, `:619 _init_db`, `:715 _upgrade_schema`; [история](../01-functional/history.md).

## Физическое размещение

DatabaseManager process singleton. По умолчанию Histories/world.db, root из NEUROMITA_HISTORIES_DIR, иначе cwd/Histories. При обычном bootstrap env установлен относительно base; отдельные entrypoints должны проверяться отдельно. Тестовый path_override допустим до первого создания.

Соединение создаётся на операцию: sqlite3 check_same_thread=False, timeout 5 s, PRAGMA busy_timeout 5000 и foreign_keys ON. WAL пытается включиться один раз до подтверждённого journal_mode=wal; failure логируется и не делает старт фатальным. Context manager connection только закрывает соединение; он не реализует автоматический transaction commit.

## Подтверждённые сущности схемы

| Таблица | Смысл/ключ |
|---|---|
| history | Integer row id, character_id/storage scope, role/content/timestamp, active/deleted, message/speaker/target/participants/turn correlation, structured/thinking/usage metadata |
| memories | Row id + character-local eternal_id, content/priority/type/date, deleted/forgotten, tags/participants/entities, legacy embedding fields |
| variables | Primary key character_id+key, JSON value text |
| embeddings | UNIQUE source_table/source_id/character_id/model_name, dimensions/blob/created_at |
| sentence_embeddings | source identity + model + sentence index, blob; полный unique tuple уточнить |
| history_fts/memories_fts | FTS5 indexes с rowid исходной строки |
| migration bookkeeping | Именованные применённые миграции; точную схему сверить при полном migration audit |

Это не полный набор таблиц приложения: graph/other managers могут создавать свои. Основной CREATE дополняется upgrade, поэтому исходный CREATE не отражает всю текущую схему.

## Миграции и совместимость

Upgrade добавляет отсутствующие колонки best-effort, допускает прежние DB layouts. History metadata при отсутствии отдельных columns может сохраняться в meta_data. Named migrations: timestamp normalization, уникальность message id и dialogue sender identity repair. Вторая удаляет дубликаты непустого message id в character scope и создаёт partial unique index, исключая deleted rows. Index не ограничен is_active: архивная недалённая строка тоже занимает identity.

HistoryManager `_find_existing_history_row` ищет nondeleted message id независимо от active. Повторная запись возвращает прежний row id и при необходимости меняет active/deleted; content не обновляет. Поэтому duplicate message id — identity dedupe, а не edit. Range deletion следует row insertion order, не timestamp.

Timestamp migration использует SQL GLOB с шаблонами `_`; GLOB использует Unix wildcard syntax, в отличие от LIKE. [SQLite expressions](https://www.sqlite.org/lang_expr.html#the_like_glob_regexp_match_and_extract_operators). Изолированная проверка в sqlite3 `:memory:`: для `30.10.2026 12:34:56` шаблон `__.__.____ __:__:__` даёт 0, а `??.??.???? ??:??:??` даёт 1. Поэтому указанная ветвь миграции не распознаёт такой старый timestamp. Проверка не открывала пользовательскую БД и не изменяла исходники. Полные последствия для migration marker/данных ещё проверить.

## FTS

FTS capability проверяется отдельно. При отсутствии поддержки/невозможности создать tables sync triggers удаляются, чтобы базовые записи не ломались. Existing FTS columns берутся фактические, согласуются с base columns. Insert/delete/update triggers синхронизируют indexed content; backfill только если FTS table пустая.

FTS содержит rows независимо от active/deleted flags; filtering обязано выполняться search query по base tables. Soft-delete сам по себе не удаляет content из FTS: UPDATE trigger пересоздаёт index row. Нужно подтвердить все search paths при RAG audit. Наличие foreign_keys ON не означает наличие declarative FKs: они не обнаружены в просмотренных CREATE history/embeddings.

## Требования к новой системе

Сохранить различие active/archived/deleted/forgotten, identity message ids и model-specific embeddings. Выбрать единицу transaction по функциональным операциям, не по нынешним methods. Отдельно определить import существующего world.db, версионирование схемы и производных индексов, поведение при недоступном FTS, image assets consistency и backup.

SQLite — текущий факт, кандидат для новой реализации ещё требует сравнения с альтернативами. Единая БД и единый объект доступа — разные решения; не переносить singleton как следствие выбора формата хранения.

## Продолжение

Проверить весь schema/migrations, graph tables, embedding serialization и sentence embeddings, QtSql readers, export/deletion/backup/reindex functions, transaction boundaries memory/variables/history и migration tests. Данные пользователя не открывались.
