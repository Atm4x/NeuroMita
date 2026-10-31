# Импорт старых сохранений и изменение формата

Статус: CONDITIONAL, действующие GUI actions. Старые форматы — входные данные текущих функций, а не основание переносить прежнюю архитектуру. Файлы пользователя не открывались, импорты не запускались.

## Восстановить старое сохранение

CAP-DATA-006. Character settings предлагает ZIP/один JSON, папку или список JSON. inspect_legacy_backup читает без изменения БД, находит *_history.json и *_memories.json, проверяет структуру и соответствие одного исходного персонажа. Показывает исходный/целевой character, количество истории/памяти/переменных/system parts, ожидаемое восстановление и warnings. Цель — выбранный в settings персонаж; она может отличаться от имени источника и активного собеседника.

ZIP JSON читаются в память, имена absolute/.. отклоняются, отдельный JSON ограничен _MAX_JSON_BYTES. Общий budget числа/суммы entries этим guard не задаётся. Directory рекурсивно собирает JSON. Source digest зависит от имён и содержимого, а не расположения выбранной папки; file/item ledger также хранит отдельные hashes history/memories. Повторный импорт в тот же character блокируется с отдельным подтверждением принудительного повторения. Это ledger конкретного recovery workflow; обычный DB JSON import имеет другой контракт.

recover_legacy_memories воспроизводит +/#/- memory directives в порядке записей, включая повреждённые closing tags и незакрытый delete. Прямой текст до directives сохраняется, orphan update может стать восстановленным фактом; удалённые результаты не активируются. Duplicate/отсутствующие исходные номера получают новые номера внутри импортируемого набора; это не доказательство отсутствия конфликта с уже существующими eternal_id цели: used_ids строится из импорта. Исходник сохраняется в legacy_import_archives вместе с labels; fixed system prompts архивируются, не включаются в активный prompt.

Import перед записью делает копию основного DB файла, создаёт bookkeeping tables, затем BEGIN/commit для истории, памяти, variables и ledger/archive. При exception rollback. История получает legacy provenance/message_id; старые теги нормализуются. Variables — INSERT OR REPLACE. Memories — новые INSERT с import tags. Ошибка последнего progress callback после commit уже не откатывает данные. Снимок через SQLite backup API/checkpoint здесь не выполняется: используется shutil.copy2 основного файла, полнота относительно WAL/конкурентных writers не доказана. Нельзя обещать recovery backup как проверенную online backup.

TaskWorker ограничивает одновременные recovery одного character собственным task resource, но не все прочие mutations этого персонажа. Cancel cooperative через progress callbacks. По успеху GUI запрашивает character reload и INDEX_CHANGED; это не вычисление отсутствующих embeddings. Есть counts attempted/applied/noop/orphan, однако основной success dialog показывает только часть.

## Перенос старых локальных папок в SQLite

CAP-DATA-007. Другая кнопка мигрирует Histories/<id> выбранного/all character: активные memories, missed memories как deleted, variables, активную history и missed_history как inactive. Старые файлы сохраняются. Перед началом best-effort copy в world.db.pre_migration_backup; ошибка backup только логируется.

HistoryManager нормализует multimodal content и может создать image artifacts до commit SQL. Дубликаты memory определяются character/date/content, history — character/role/content/timestamp/is_active; это не тот же ledger, что у recovery. Memory eternal_id берётся из N. Variables перезаписываются. Ошибки rows собираются с продолжением; commit per character, его failure может оставить counters attempted завышенными. Cancel между rows не откатывает уже завершённых персонажей. Автоматического общего rebuild/source revision здесь не найдено.

## Structured формат: два разных действия

CAP-DATA-008. «Обновить формат» меняет старый *_history.json на месте, создавая best-effort соседний backup. Assistant messages, а также user-role fanout с тегами конвертируются в clean text и structured_data.segments; flat JSON также поддержан. Известные animation/emotion/command/etc поля извлекаются, memory tags удаляются из представляемого текста. Это преобразование представления, не повторное исполнение игровых/памятных effects. Запись конечного JSON не atomic; backup failure не блокирует запись. При отсутствии изменений возвращается success0.

Отдельная DB migration выбирает assistant rows с пустой structured_data column, сначала переносит structured_data из metadata, иначе парсит старые content tags. Обрабатывает выбранного/all character, errors отдельных rows накапливаются, SQL commit в конце. Уже заполненная колонка пропускается. Она не имеет такого же покрытия user-role fanout, как file migration. GUI обеих операций запрашивает reload, но они не равнозначны и не гарантируют обновления всех производных данных.

CAP-DATA-009. History dedup доступен current/all. При наличии message_id оставляет MIN(id) для character/message_id среди неудалённых; пустые IDs не дедуплицирует. Только при отсутствии самой колонки используется character/content/timestamp fallback. Это физическое SQL DELETE, не semantic dedup текста и не memory cosine merge. Commit failure логируется; returned count не является надёжным durability outcome. Связанные derivations автоматически не очищаются в методе.

## Что сохранять в проекте с нуля

Решение о поддержке старых форматов требует отдельного продуктового выбора. Если поддерживаем: однозначная цель импорта, preview и warnings, повторяемость/ledger, сохранение исходника и provenance, безопасное назначение новых identities, валидируемый backup, понятная атомарность/частичный результат, пересоздание derivations и отсутствие повторного исполнения исторических команд. Потребности в Python-only core библиотеке эти paths не выявили: фактически используются JSON/ZIP/hashes/regex/files/SQLite и собственные правила. Реальные Rust варианты и их пределы теперь исследованы по первичным источникам в [dependency report](../04-dependencies/core-library-alternatives-and-native-costs.md); совместимость конкретного recovery формата всё равно требует собственных правил и fixtures.

Источники: character_settings_logic restore_legacy_memory/_start_legacy_memory_recovery_worker/migrate_*; utils/legacy_memory_recovery inspect/recover/import/backup; utils/migrate_json_to_sqlite migrate; utils/history_migration migrate_content/migrate_history_file; utils/migrate_tags_to_structured_in_db migrate; DatabaseManager.dedupe_history. Основные перечисленные workflows прочитаны; не все timestamp/helper edge cases, tag tables и malformed input combinations исследованы. Никаких исправлений source не делалось.

## Pass 13: read-only recovery inspection fixture

На синтетических JSON/ZIP во временной папке выполнены неизменённые функции `inspect_legacy_backup` и `recover_legacy_memories`. Для изоляции AST module исключён только top-level import DatabaseManager; mutating `import_legacy_backup` не вызывался. Dataclasses/helpers/regex/parsing/inspection/replay оставлены неизменёнными. Python `-B`, без приложения, пользовательских файлов, SQL и сети.

| Проверка | Фактический результат |
|---|---|
| Один набор через folder, file list, nested ZIP и перемещённую копию папки | Одинаковый source_digest; counts history/memories/variables/fixed_parts/recovered совпали |
| Duplicate memory N и fixed system prompts | Preview содержит соответствующие warnings; fixed prompts не активируются inspection |
| Только memories file | Успешный partial preview с предупреждением об отсутствующей history |
| History одного character + memories другого | LegacyBackupError до DB mutation |
| ZIP с ../Crazy_history.json | LegacyBackupError; содержимое ZIP не извлекается в рабочую файловую систему |
| Memory update → незакрытый delete по номеру | Directive replay соблюдает порядок, удалённая запись отсутствует в recovered result; counters соответствуют двум применённым действиям |

Все assertions **PASS**, exit code 0, временный каталог удалён. Это проверка перечисленных inspection/replay случаев, не всего legacy parser corpus, не DB import ledger/backup/WAL и не настоящих сохранений пользователей. Проверять реальные образцы, import collisions с target eternal_id, multimodal attachments и derived-index reconstruction по-прежнему необходимо; synthetic digest equality их не доказывает.
