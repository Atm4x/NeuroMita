# Повтор Unity turn и сохранённая доставка

**Capability:** `CAP-DELIVERY-001`. **Статус:** CONDITIONAL: Unity-originated player turn + retry workflow. **Источники:** `src/managers/unity_retry_store.py:17 UnityRetryStore`; `src/controllers/chat_controller.py:1366 _on_retry_last`, `:1406 _retry_unity_request`; ServerController delivery и оба конца transport дополнительно исследованы в [Unity transport](unity-transport.md).

Уточнение гарантии: complete_delivery вызывается по socket send/drain Future, без Unity application ACK. Unity может отвергнуть task context/response version либо ещё не закончить presentation. Локальный Unity AcknowledgeDelivered не посылает подтверждение серверу. Поэтому delivered в store означает успешную отправку в transport, не доказанное применение результата игрой.

## Назначение и сценарий

После ошибки генерации повторить исходное обращение, а после ошибки доставки отправить уже полученный ответ без нового вызова LLM. UI failed message id выбирает сохранённый request; сначала используется transient UI request cache, при отсутствии — persistent Unity outbox.

## Данные и хранение

На персонажа Histories/{safe-character}/unity_retry_outbox.json. Version 1, до 100 records, до 64 MiB сериализованного файла, срок 30 дней от created_at. Bytes в запросах кодируются специальной JSON обёрткой и восстанавливаются со strict base64 validation. Состояние защищено process RLock; межпроцессный lock в проверенном store отсутствует.

Запись через temporary sibling file, flush/fsync и os.replace. Corrupt/неподдерживаемый файл карантинируется; если quarantine не удалось, path помечается unreadable и overwrite запрещается. Повреждённые images/результаты делают record unretryable. Generated result должен содержать непустой response string. Prune использует возраст создания, не последнего retry.

Record содержит message id, request/task_data, active task uid, status/result/error, process session id. Producer _dispatch_task дополнительно проверен: player game chat с req_id пишет request context/images/policy/dialogue и task_data с пустым client_id; persistence failure не останавливает generation. add duplicate message id возвращает True, не перезаписывая payload.

## Состояния и crash recovery

Retryable только needs_generation и generated_pending_delivery. Atomic claim переводит первое в generating, второе в delivery_retrying. Другие active попытки не claim-ятся повторно. Transition может проверять expected status и expected_task_uid, чтобы старый callback не переписал новую попытку.

При старте ChatController вызывает recovery старых session records: generating/pending→needs_generation; delivery_retrying/generated_pending_voiceover→generated_pending_delivery. Уже полученный ответ сохраняется. Read сам по себе не запускает recovery: обычное чтение не должно обрывать активный retry.

## Retry workflow

1. Найти/claim record. Нет данных, unretryable или невозможность записать claim — отдельные UI errors.
2. Найти текущего player_turn_owner GameLinkService. Без подключённого owner вернуть claim в retryable status и показать ошибку.
3. Создать новую task, подставить текущий client_id и связать active_task_uid с record.
4. Для generated_pending_delivery выставить новой task SUCCESS с сохранённым result, не пересылать generation request.
5. Для needs_generation отправить task update и исходный SEND_MESSAGE с новым task uid, images_shown=True и event_type=chat.
6. Exception abort-ит созданную task и освобождает claim. Release сохраняет generated_pending_delivery, если исходный статус был таким; остальные возвращаются в needs_generation.

mark_voiceover_failed переводит generated_pending_voiceover в generated_pending_delivery при совпадении task. finish_failed_attempt сохраняет полученный текст, если он уже есть. complete_delivery удаляет только matching active task record; при ошибке записи in-process set скрывает повтор в текущей сессии, но дисковый record остаётся. Это не подтверждение exactly-once после crash.

## UI, зависимости и эффекты

UI RetryLastChat очищает error на выбранном bubble; уже показанные user/images не должны дублироваться. Зависимости: TaskService, GameLink owner, Chat admission, persistent outbox, server delivery callbacks. Изменения: files, tasks, provider request либо retransmission. Wire критерий дополнительно установлен: successful socket drain, без application ACK. Cancel/timeout и все stale presentation outcomes ещё не проверены runtime.

## Требования и реорганизация

Сохранить разницу retry generation/retry delivery, crash recovery и защиту от stale attempt. В новой модели task id, message id, attempt id и delivery id должны иметь разные роли. Определить acknowledgement и idempotency вместе с Unity; fsync outbox не заменяет подтверждение игрового эффекта. Хранение может быть единым transaction store либо отдельным outbox — решение после общего storage/Unity audit. Rust alternatives пока не выбраны.
