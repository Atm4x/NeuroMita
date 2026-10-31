# История в UI: начальная страница, догрузка и живые сообщения

Pass 13, 2026-10-31. Дополнение к [raw events](../00-research/raw-string-event-reachability-and-ui-bridges.md), [истории чата](chat-stream-history-and-message-actions.md) и [identity](../01-functional/dialogue-actor-and-message-identity-contracts.md). Здесь функциональный контракт; live Qt/SQLite интеграция не запускалась.

## Начальная загрузка

`AppWindowBase.load_chat_history` (549–584) ждёт монтирования chat_window; до него ставит pending. Получает текущий character ID, создаёт HistoryLoadTicket с UUID и start_revision, посылает shell action с captured character/request ID. 15-секундный watchdog отменяет только соответствующий ticket и сохраняет живое представление, не очищая чат по timeout.

`ModelController._on_load_history` (794–853) берёт **захваченного запросом** персонажа, сбрасывает paging counters и возвращает request_id/character_id/messages/total_messages/loaded_offset. SQL путь читает recent active rows; fallback проецирует tail локальной history. Отсутствующий character даёт пустой результат с identity запроса.

Qt bridge из ViewEventController передаёт payload в `_on_history_loaded` (638–713). Если UI ещё не готов, payload сохраняется. До планирования отображения асинхронно добавляются записи Unity retry store текущего response character с policy latest; неудача этого дополнительного чтения продолжает обработку исходного payload.

`ChatPresentationCoordinator.plan_history_projection` (545–665) принимает snapshot только при active ticket и совпадающем request ID. Непустые character IDs нормализуются casefold. Причины отказа различаются:

| Условие | Outcome |
|---|---|
| Нет ticket или другой request_id | stale_request |
| Ticket character и response character различаются | response_character_mismatch; ticket сбрасывается |
| Текущий выбранный character отличается от snapshot target | inactive_character; ticket сбрасывается |
| Есть mounted active stream нужного character | active_stream, retry_after_stream=True; refresh откладывается |
| Snapshot принят | Возвращается упорядоченный replay живых commands, ещё не покрытых snapshot |

Stable сообщения сопоставляются по `(character,message_id)` и content signatures. Уже durable до начала запроса, но отсутствующие в этой странице/фильтре сообщения не воскресают из live cache. Не покрытые snapshot новые/ещё не persisted commands переигрываются. Ephemeral commands replay только после start_revision. Это логика представления, не повторное исполнение игровых effects.

При accepted plan UI очищает только представление без reset coordinator, рисует snapshot и replay, обновляет debug, прокручивает вниз. Ошибка рендера логируется; флаги inflight и updates восстанавливаются finally. Наличие accepted плана не доказывает успешный render каждого виджета.

## Старые страницы

`load_more_history` (1143–1149) посылает current character. `ModelController._on_load_more_history` (855–912) сравнивает character с `_history_character_id`, использует loaded offset и увеличивает его на прочитанные строки. Ответ more_history_loaded имеет character_id/loaded_offset/messages, **без начального request_id**.

`_on_more_history_loaded` (1151–1205) отбрасывает пустую страницу и несовпадение непустых response/current IDs; проверяет tombstones через coordinator.is_message_deleted. Рисует prepend в обратном обходе и восстанавливает положение scroll с учётом изменения maximum. Для этой ветки нет вызова plan_history_projection: нельзя приписывать ей весь ticket/revision/stream policy начальной загрузки. Пустая identity ослабляет проверку; сценарий повторной загрузки того же персонажа и запоздавшей older-page требует отдельной интеграционной проверки.

## Выполненная проверка

Неизменённый `presentation_coordinator.py` загружен отдельно через importlib; его зависимости — stdlib. Python `-B`, без Qt, Core bootstrap, пользовательской БД, файловых mutations или сети. Assertions: stale ID, response mismatch, inactive character, casefold identity + replay нового live message, superseded ticket и принятие нового ticket. **PASS, exit code 0.** Это не запуск существующего полного Qt test module.

## Требования и оставшийся gate

`REQ-HIST-PAGING-001`: начальная загрузка и older-page имеют явную identity/generation, не заменяют чужой разговор и не восстанавливают удалённые сообщения. Переключение A→B→A, новый reload, поздние ответы и stream проверяются отдельно.

`REQ-HIST-PAGING-002`: refresh истории сохраняет ещё не попавшие в storage живые сообщения без повторных effects и дубликатов; timeout не уничтожает live UI. Нужен согласованный контракт пагинации при параллельных вставках/удалениях и bounded retention.

Source gate «первый Qt receiver неизвестен» закрыт для этих двух events. Live Qt+DB/scroll, старые response с пустыми IDs, limit/offset при конкурентных изменениях и межпоточная доставка остаются **NOT RUN**, не скрываются данным изолированным результатом.
