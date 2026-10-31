# История: запись, исправление и повтор

Статус: исследованы операции вокруг chat turn и storage methods. Ранний срез дополнен [compression](history-compression.md), [paging/live replay](../02-ui/history-page-fencing-and-live-replay.md), [identity](dialogue-actor-and-message-identity-contracts.md), [миграциями](compatibility-imports.md), [RAG storage](rag-storage-retrieval-and-indexing-modes.md). Актуальные оставшиеся gates — в [Pass 13 baseline](../00-research/current-functional-baseline.md), а не в старых формулировках «ещё не исследовано».

## Functional Capability: сохранение разговора с несколькими участниками

**ID:** `CAP-HIST-001`. **Статус:** ACTIVE. **Источники:** `src/managers/conversation_event_writer.py:28 ConversationEventWriter`, `:61 _history_recipient_ids`, `:119 _append_history_messages`, `:177 _fanout_turn`, `:362 write_turn`; `src/managers/history_manager.py:1273 add_messages`; `src/controllers/model_controller.py:775 _publish_history_commit`.

### Назначение и сценарий

Записать завершённый turn в истории персонажей, которые участвовали в разговоре, сохранив идентичность speaker/target и происхождение сообщения. Входы: responder/sender/participants, dialogue actor roster, текст/изображения/TV observation, ids и structured metadata. Выход ConversationWriteResult содержит message ids, committed и failed recipient ids.

### Данные и правила

Recipients определяются по dialogue participant roster, если он есть, иначе по participants; responder добавляется. Player и GameMaster исключаются из history owners. Aliases приводятся к canonical ids, дубликаты удаляются case-insensitively. Для локальной истории role assistant соответствует собственному speaker, иначе user; TV observation остаётся user.

Turn_id строится из task_uid/req_id. Если non-player отвечает на существующий origin_message_id, новый user event не создаётся. Whitespace-only user input без изображений/TV observation тоже не создаёт user event. Assistant metadata различает source_actor_id и speaker_actor_id responder, сохраняя conversation/turn identity.

### Согласованность и lifecycle

User+assistant пишутся одним batch на recipient. Ошибка batch откатывает его SQL transaction и даёт HistoryBatchWriteError. Между recipients нет общей transaction: часть историй может сохраниться, часть fail. `_append_history_messages` дополнительно проверяет полноту row ids и превращает ошибку в False. Writer возвращает failed recipients, а ModelController в проверенном generation path не прекращает выдачу ответа из-за этого списка; commit event публикуется только для committed recipients.

Следовательно: атомарность одного history batch подтверждена, атомарность всего multi-character turn не подтверждена. Успешный LLM result не гарантирует сохранение во всех историях.

### Хранение и эффекты

SQLite history + variables по storage_key. HistoryManager сериализует запись per-character lock. add_messages выполняет dedupe и планирует embeddings после commit, исключая rejected/deleted rows. Multimodal content разделяется на text и meta parts, base64 images могут выноситься на диск; реконструкция возвращает content и UI image hints. Image descriptions поддерживают несколько detail levels и старое строковое поле.

Easel drawing отдельно сохраняется в Drawings до записи turn; filesystem images не являются частью SQL rollback. Metadata сохраняет дополнительные поля, включая structured_data и thinking; `_raw_json` из structured_data не удаляется в проверенных writer/history serialization methods. Это уточняет противоречащий коду комментарий в ModelController.

### UI, ошибки, требования

MESSAGES_COMMITTED содержит ids и список сохранённых character ids. UI может показывать уже streamed ответ до этого события. Новая система должна формально разделить generated/committed/delivered, определить partial history failure и область атомарности, сохранить participant semantics и ids. Возможная реорганизация: owned conversation operation + явный storage result; отдельный Rust controller на каждый нынешний класс не требуется. Rust storage alternatives исследуются после schema/contracts audit.

## Functional Capability: удаление и редактирование истории

**ID:** `CAP-HIST-002`. **Статус:** ACTIVE. **Источники:** `src/controllers/chat_controller.py:1309 _on_delete_message`, `:1334 _on_delete_messages_from`; `src/controllers/gui/chat_message_actions_view_model.py:50 dispatch`; `src/managers/history_manager.py:1613 delete_message`, `:1680 delete_messages_from`, `:1685 delete_messages_after`.

Пользователь удаляет одно сообщение либо выбирает «редактировать»: текст извлекается до удаления, выбранное сообщение и последующие удаляются, текст возвращается в input. Для multimodal input извлекается первый text item; изображения и прочие metadata в редактор этим path не восстанавливаются.

Удаление одиночного сообщения также убирает соответствующий Unity retry record и UI request cache; при любом найденном объекте UI reload. Range deletion работает по insertion row id, не timestamp. Используется soft-delete, исключённый из active history; exact `_soft_delete_set_clause` и поведение индексов проверить в storage/RAG audit. Сообщение выбирается в scope текущего storage_key, с active/not-deleted фильтром.

Состояние: persisted history плюс transient input и retry cache. Побочные эффекты: SQL update, outbox rewrite, reload/input events. Неизвестный character/id даёт warning/no-op. Cancellation текущих generation перед edit/delete в этих methods отсутствует; concurrent generation consistency требует проверки.

Требования: stable message ids, явный порядок range operation, различие удаления/архивации, понятный результат отсутствующего сообщения. Нельзя считать редактирование rollback всего мира, переменных или памяти: такого общего отката здесь нет. UI intents должны оперировать message ids, а не количеством widgets.

## Functional Capability: перегенерация ответа

**ID:** `CAP-HIST-003`. **Статус:** ACTIVE. **Источники:** `src/controllers/chat_controller.py:1524 _on_regenerate`, `:1663 _on_regenerate_from`, `:1605 _count_widgets_for_slice`.

Regenerate-last находит последний assistant и предшествующий user, удаляет историю начиная с user (или assistant, если user отсутствует), пересылает user text. Если user имеет префикс `[Системное]:`, он сохраняется, удаляется assistant и далее, отправляется пробел.

Regenerate-from для выбранного user удаляет его и далее, отправляет текст снова; для assistant находит предшествующий user и повторяет с той точки; для system сохраняет его, удаляет только после. System-as-user распознаётся по русскому текстовому префиксу. В этой ветви trigger пустой для as-user и пробел для обычного system.

В текущем пути resend содержит user_input/character_id, без исходных изображений, participants, dialogue snapshot или source metadata. Это факт реализации и вопрос ожидаемого паритета, не обязательное ограничение новой системы. Видимые widgets удаляются по вычисленному количеству, зависящему от structured panels/segment targets/images и локализованной SHOW_STRUCTURED_IN_GUI. Presentation bookkeeping находится в core orchestration path.

Отказ новой генерации не восстанавливает удалённую часть истории автоматически. Удаление текста не откатывает ранее применённые character effects. Для новой реализации отдельно определить desired regenerate semantics, не переносить случайную связанность с widgets или localized strings.

## Functional Capability: snapshot и системная вставка

**ID:** `CAP-HIST-004`. **Статус:** ACTIVE. **Источники:** `src/controllers/chat_controller.py:1790 _on_insert_system_message`, `:1831 _on_save_snapshot`, `:1848 _on_load_snapshot`; `src/managers/history_manager.py:1082 load_history`, `:1140 save_history`, `:1242 save_history_separate`; `src/controllers/gui/app_shell_controller.py:448 insert_debug_message`, `:460 save_snapshot`, `:465 load_snapshot`.

Вставка сохраняет system message либо user message с `[Системное]:`, вызывает reload и generation с пробелом. Новая domain operation должна передавать semantic kind отдельно от отображаемого префикса.

Snapshot export — JSON активной видимой истории и variables в Histories/{storage_key}/Saved/chat_history_{timestamp}.json, timestamp до секунд. Snapshot import принимает dict либо старый bare list (оборачивается messages + пустые variables). Это не полный snapshot приложения/AI/Unity/памяти.

save_history транзакционно upsert-ит переданные variables, синхронизирует сообщения, повторно использует подходящие row ids, помечает отсутствующие active rows deleted/inactive (или удаляет при старой схеме), commit, затем embeddings. Отсутствующие в snapshot variables не удаляются: это merge variables, не полная замена. Ошибка SQL логируется и method возвращает без error result; вызывающий import затем всё равно reload/log success. Это доказанная потеря информативности результата, фактический сбой не воспроизводился.

UI показывает success export только при непустом path; import exceptions логируются. Отмена/фон/validation JSON payload и обновление in-memory character variables после import ещё требуют проверки. Новая система должна явно определить формат/version, область snapshot, merge/replace semantics, validation, failure result и реакцию live state.

## Неясности первоначального среза

Перечень первоначального среза (storage/schema, dedupe, archive/summary, sessions, concurrent edits, images, indices, snapshot identity, destructive UX) уточняется связанными документами и Pass 13 ниже. Не трактовать весь этот список как до сих пор непрочитанный source. Runtime concurrent/storage/GUI fixtures остаются самостоятельной границей.

## Pass 13: точная identity-policy snapshot restore

Дочитаны `HistoryManager._history_row_belongs_to_character_tx` (750), `_reserved_snapshot_row_ids_tx` (831), `_resolve_snapshot_row_id_tx` (798), `_find_existing_history_row` (858), `save_history` (1140–1240), ChatController snapshot handlers и `Character.load_history` (1073–1092).

Выбор row для каждого snapshot message идёт в следующем порядке:

1. Положительный `_history_row_id`, ещё не использованный этим restore, и **принадлежащий текущему storage_key**; deleted rows исключены, если колонка существует.
2. Найденный по message_id неудалённый row того же character, ещё не использованный; SQL выбирает самый новый id, active либо archive.
3. Первый свободный active row, не зарезервированный явной ссылкой другого snapshot message.
4. Если такого row нет, вставка новой строки без dedupe.

Предварительный reserve-pass учитывает `_history_row_id` и message_id всех messages, чтобы новая строка в начале списка не заняла старую identity последующей строки. `used_row_ids` не позволяет повторно использовать одну SQL row для двух snapshot messages. Чужой character row ID не позволяет обновить его напрямую: ownership проверяется до выбора и в UPDATE. При fallback **позиционное переиспользование** всё ещё возможно; восстановление не является replay исходных SQL IDs или append-only импортом.

У update сравнивается content; при его изменении очищается legacy embedding и удаляются history-source rows из embeddings/sentence_embeddings с теми же row_id/character. Новые embedding tasks собираются и планируются **после commit**. Неиспользованные active rows помечаются deleted+inactive либо физически удаляются при старой схеме. Общего в этом методе graph/relation/processed-ledger rebuild не обнаружено. Variables только upsert; отсутствующие keys не удаляются.

`ChatController._on_load_snapshot` вызывает history_manager.save_history и GUI reload, а не Character.load_history. Последний — отдельный метод, который действительно переносит persisted variables в live Character через set_variable. В основном SQL UI paging ModelController читает history_manager напрямую; явного немедленного live-variable refresh в исследованном snapshot chain нет. Не считать изменение JSON/SQLite variables атомарным восстановлением всего live character state, памяти, reminders, графа или Unity.

Случаи для дальнейшей acceptance: вставка в начало перед explicit ID, duplicate references в одном snapshot, foreign/deleted/archived row IDs, одинаковый message_id у разных characters, absent variables, content changed без смены row ID, restore во время generation/compression и проверка derivations/live state. Эти cases описаны по source; отдельного snapshot DB/GUI fixture в Pass 13 не выполнялось. Случайные ограничения restore не обязаны переноситься как желаемая новая policy.
