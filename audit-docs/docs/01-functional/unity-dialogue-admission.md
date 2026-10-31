# Unity: очередь диалогов и приём голосового ввода

Статус: ACTIVE, исследована локальная Unity revision e7c7ae42; это продолжение [transport](../03-runtime/unity-transport.md). Часть правил здесь принадлежит игровому клиенту и не должна автоматически переезжать в Rust core.

## Очередь turn

DialogueTurnCoordinator имеет одну общую active request и stages Idle/Dispatching/WaitingForTask/PresentingResponse. Это глобальная сериализация Unity turns, отличная от per-character lock Python. Pending queue выполняет semantic admission:

- Idle того же character не принимается при active request либо queued non-idle; старый queued idle заменяется новым.
- Collectable react — только без frames/manifest. Он поглощается queued required turn того же character как runtime event либо объединяется с queued react batch.
- React batch≤24 уникальных reason type/content, case-insensitive duplicate увеличивает occurrences/max duration; HighestLevel повышается. При превышении удаляется oldest event.
- Required turn удаляет idle того же character и поглощает queued reactions. Новый player answer удаляет старые **ещё queued** player answers того же character, сохраняя attached runtime events; прежний player text этим методом не переносится.
- Attached runtime events≤64, dedup case-insensitive; request seal при dequeue запрещает дальнейший merge. Общего queue length cap не видно.

Это наблюдаемая policy, не доказательство желаемого продукта. В новой системе явно решить coalescing пользовательских реплик, bounded overload и UI outcome вытесненного запроса.

Dispatcher проверяет connection/actor, готовит TV observation/continuous camera и snapshot runtime context перед send. Pending tracker связывает req_id с server task uid; Unity retry context сохраняется для task с unity_retry_message_id. Source runtime batch capture не удаляет события, commit делает validated final response. На dispatch failure attached events возвращаются в buffer, player draft пытается восстановиться в input.

После socket write coordinator переходит WaitingForTask. На final начинает ожидать presentation activation≤0.75s и idle≤30s, затем двигает queue; это ожидание локального presentation, не точная remote acknowledgement. Completion sequence защищает late callback. ConnectionLost снимает Dispatching/WaitingForTask и продвигает queue. Scene transition cancel очищает tracker/context buffer/speaker order/continuations. Отдельной remote cancel generation не отправляет.

## ASR capture session

ASR player input использует session id и возрастающий command generation. Unity renew раз в1s поддерживает Python lease3s. Begin awaiting acceptance, release сохраняет pending recognition; cancel отправляет cancelled и очищает captures. Capture ACK deadline5s; live connection response deadline5s; released pending recognition120s. Text и status revisions учитываются независимо, capture_id закрепляется при первом совпадении. Stale session/press/capture/revision отвергаются.

AsrPushToTalkController установлен BeforeSceneLoad, переживает смену сцен, регистрирует state handler и connectivity. Mode change/mic disabled/disconnect/pause/focus loss отменяют capture/automatic submission; external speech bridge имеет отдельные разрешения. CanReceive требует connection+input ownership, не death, focus либо external, и при обычном вводе отсутствие pause/menu. Manual capture требует gameplay/no menu/no editing либо готового external bridge.

Radio toggles по кнопке, PTT hold/release. Draft editing прекращает обычную capture и autosend. Защита от речи персонажа ставит resume tail0.5s; external speech может release и resume radio, обычный режим cancel/reset recognition. Capture errors показываются один раз по press generation, draft раскрывается для ручного использования.

Полученный текст применяется к player draft. Autosend включается только по final, пока draft не adopted и нет capture error. AsrAutoSubmission хранит text/delay/due: изменение current draft отменяет; блокировка сбрасывает due, так что после разблокировки задержка начинается заново. Tick перед submit очищает pending; submit failure сам по себе не возвращает auto job. Условия блокировки: speech active, capture pending/requested, focus/menu/pause/edit policy. Отключение instant send отменяет pending submission.

UI indicator показывает starting/listening/recognizing/error и confirmed state. ASR input gate ACK, text acceptance в draft и player turn submission — три разные ступени. Ни одна не подтверждает Python outbox delivery в обратном направлении.

## Проектные выводы и остаток

Разделить игровой input ownership, draft lifecycle, generation admission и presentation scheduling. Сохранить различие release/cancel/adopt/edit, renew и stale-result fencing. Автоматическая отправка должна иметь понятный outcome при blocked/edited/submission rejected. Новый Rust core не обязан знать Unity UI focus/death screen, но контракт должен передавать enough identity/outcomes для соответствующей policy владельца.

Прочитаны DialogueTurnAdmissionPolicy полностью, Workflow tracker/DispatchAsync/coordinator/lifecycle основные методы, AsrCaptureSession/State/AutoSubmission/PushToTalkController/InputPolicy полностью. Не закрыты PlayerMessageDraftService/Submission, continuous camera/TV preparation, speaker auto-order/GM cadence/continuation, ResponsePlanExecutor и presentation/audio lifetime. Это не полный Unity dialogue audit.
