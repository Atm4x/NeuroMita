# Chat history projection, stream replay and действия над сообщениями

**Capabilities:** `CAP-UI-CHAT-002—004`; **Status:** ACTIVE (контракты UI), CONDITIONAL (finetune rating/context). **Audit:** static source `CodeNow.zip`, 2026-10-30; test files прочитаны как evidence, но не исполнялись. Это **проекция UI**, а не сама история/LLM persistence: [history](../01-functional/history.md), [turn lifecycle](../01-functional/llm-and-generation.md).

## Почему нужен независимый presentation contract

`src/ui/windows/app_window_base.py:176` создаёт `ChatPresentationCoordinator`; его `src/ui/chat/presentation_coordinator.py:88-112` хранит согласование между живым отображением, snapshot истории и текущими streaming-ответами. Важны: active character/surface isolation, persisted ack, identity сообщения, частичное состояние до записи в БД и исключение повторных пузырей.

`ChatRenderCommand` (`presentation_coordinator.py:10-35`) — immutable запись role/content/character_id/message_id/time/structured_data/sample_id/context_snapshot_id/delivery_error. Content клонируется через deepcopy при сохранении и выдаче, чтобы последующая модификация не изменила replay. `HistoryLoadTicket(request_id,character_id,start_revision)` и `HistoryProjectionPlan(accepted,replay,retry_after_stream,reason)` позволяют отвергать устаревшие результаты чтения.

## State machine reconciliation

1. **Live message:** `record_live:204-254` принимает event и увеличивает revision. Identity — `(casefold(character_id), message_id)`; без id запись становится bounded ephemeral (по умолчанию 256). Stable live entries — LRU max 256. События неактивного персонажа могут быть сохранены для replay, но не должны отобразиться в активном чате. Уже удалённые/показанные из snapshot значения и точные дубликаты не рендерятся повторно.
2. **Persistence acknowledgment:** `acknowledge_persisted:256-286` принимает набор message IDs и допустимые character IDs, записывает persisted revision, но это самостоятельный notification state, не подтверждение транзакции storage на основании одного render.
3. **Terminal delivery failure:** `mark_failed:287-329` помещает ошибку рядом с command user message, а не только в текущий Qt widget; refresh истории не должен терять статус «не дошло». `forget_message:333-343` помечает удалённое сообщение tombstone и убирает его из stable/persisted/projected caches, размер tombstones также bounded.
4. **History fetch:** `begin_history_load:345-352` создаёт ticket. `plan_history_projection:545-656` отвергает wrong request id, character mismatch и inactive character. Snapshot составляет signatures каждой строки, включая отдельный think-сегмент. Live commands, которые snapshot полностью покрывает, не дублируются; live newer-than-ticket и не покрытые компоненты идут в replay. Persisted до начала snapshot, но отсутствующее в полученной странице сообщение не «воскрешается» за пределами страницы.
5. **Streams:** `begin_stream`, `record_stream_chunk`, `stream_replay` (`:417-462`) хранят фазы role/speaker/concatenated chunks; разные role phases не должны слипаться. Mounted/unmounted state (`:463-479`) поддерживает пересоздание UI после смены вкладки. `plan_history_projection:569-579` может отложить history projection, если streaming пузырь уже mounted; `finish_stream:520-543` возвращает сигнал на повтор истории после завершения stream.

**Особенность identity сравнения:** `_content_signature:122-169` делает нормализованное сравнение ролей и multiset visible content components. `meta` не участвует, `image_url` учитывает URL/role, think отдельно. Сравнение `_signature_covers` может считать live part покрытой full snapshot, даже если snapshot имеет дополнительный контент. Это намеренный display-dedup, не byte-for-byte equality history rows. Согласованность при нескольких image blocks/updated text — предмет future tests.

## Контекстное меню одного сообщения

`src/ui/chat/message_widget.py:599-613,673-729` привязывает `message_id`, `sample_id`, `context_snapshot_id`; streamed bubble может получить id **после** появления. Menu: Copy selected/all; у user Edit, Regenerate from here; у assistant Regenerate, View request context, View response context, Regenerate from here; Delete при наличии message_id; если bubble помечен delivery error — Send again. Rating up/down видны при наличии finetune sample (`:615-670`), action не является изменением memory/LLM response, а обновляет training sample rating.

`src/ui/chat/message_renderer.py:215-295` конвертирует Qt actions в typed intent через `ChatMessageActionsViewModel`, а `Regenerate from here` сначала показывает modal confirmation: все сообщения **после** выбранного удалятся, будет новый ответ. `src/controllers/gui/chat_message_actions_view_model.py:50-102` маршрутизирует Delete → `UiTopic.CHAT_DELETE_MESSAGE`, Edit → `CHAT_DELETE_MESSAGES_FROM(edit_mode=True)`, Regenerate → `CHAT_REGENERATE`, RegenerateFrom → `CHAT_REGENERATE_FROM`, RetryLast → `CHAT_RETRY_LAST`; rating обрабатывает finetune adapter, context загружается отдельно через `run_latest`. Это publication intents, **не** commit-сигналы; downstream persistence/event handlers должны проверяться отдельно перед утверждением успешного удаления/регенерации.

## Просмотр request/response context и пределы доверия

`ChatMessageActionsViewModel._load_context:104-150` принимает `sample_id`. Для строго проверенного `ctx_[0-9a-f]{32}` пытается прочитать `SavedMessages/request_contexts/<id>.json`; для другого nonempty id ищет finetune sample. При отсутствии может перейти к `SavedMessages/last_request_context.json` (fallback `used_fallback=True`). **Для валидного ctx-id отсутствующий файл возвращает `None` немедленно** — без fallback на `last_request`, что является важным различием. Виды `request`/`response` — стартовая вкладка одного context viewer, а не отдельная LLM wire schema. При malformed/non-object JSON может показать unavailable; файловые ошибки приводят к error effect.

Context snapshots содержат фактические messages/prompt/response и потенциально секреты/личные данные; policy редактирования/экспорта/доступа ещё не проаудирована. New implementation должна отличать точный immutable snapshot от «последнего запроса» fallback, чтобы пользователь не принял чужой/другой контекст за выбранный.

## Риски, ownership и обратная связь

- Контекстное меню может быть показано до появления `message_id`: в этом случае нет persistent-target delete/regenerate-from, но Edit user вызов с пустым id всё ещё возможен; точную downstream реакцию нужно проверить.
- Bounded stable/ephemeral/tombstone caches вводят backpressure/eviction policy; older unpersisted live messages после превышения 256 могут потеряться из **UI replay**, даже если backend ещё их не сохранил. Это статический риск при очереди более 256, не измеренная потеря.
- Сверка history snapshot и stream presentation использует character-scoped identity и revision, но не гарантирует atomic snapshot всей БД. Нужен сценарий late ack и deleted-after-snapshot.
- Stream ID пустой нормализуется в строку `default`; при повторном неуникальном stream ID разные запросы могли бы разделить буфер. Внешний emitter, гарантирующий ids, не исследован полностью; не объявлять дефектом.
- Finetune rating (`ChatMessageActionsViewModel:91-93`) не сообщает UI outcome при исключении; ошибка может нарушить штатное Qt callback течение, в зависимости от adapter. Ошибка/сохранение training sample требуют отдельной проверки.

## Requirements и validation

`REQ-UI-CHAT-006`: live/history/stream должны сходиться по typed message identity, character scope и monotonic revision, без дублей и resurrection; `REQ-UI-CHAT-007`: render entry должен иметь явные `pending/persisted/failed/deleted` состояния с пропагацией confirmed persistence; `REQ-UI-CHAT-008`: меню user/assistant/system и modal destructive confirmation, корректные retry/edit/delete/regenerate-from semantics; `REQ-UI-CHAT-009`: context view должен точно указывать snapshot ID и источник fallback, а не показывать last-request как выбранный контекст без маркировки; `REQ-UI-CHAT-010`: streaming phases и change-of-character replay must preserve partial text with stable request/stream identity.

Тесты по кейсам: async history snapshot с новым incoming message; переключение персонажа во время generation; stream mounted при reload; duplicate user/assistant message id; errored outgoing bubble после reload; deletion mid-stream; history page excludes persisted live row; >256 pending messages; invalid `ctx_...` missing; sample-id fallback; non-JSON context; multiple think/image blocks. Текущий исходник содержит тестовые файлы `src/utils/Testing/test_chat_presentation_coordinator.py`, `test_release_history_loading.py`, однако они здесь **не запускались**.

**Незакрытый scope:** `message_renderer.py` full modality rendering, structured panel UI and all downstream ChatController action handlers; их следует проверить отдельным проходом. См. [chat composer](chat-composer-and-attachments.md), [Sandbox](sandbox-page-functional-contract.md), [history](../01-functional/history.md), [source traceability](../06-design-input/feature-traceability.md).
