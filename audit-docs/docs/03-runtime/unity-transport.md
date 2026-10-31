# Unity transport и lifecycle доставки

Статус: ACTIVE, основной transport изучен с двух сторон. Это не полный аудит Unity features/intents/dialogue scheduler. Python baseline38172493; Unity локальный e7c7ae42. Network scripts Unity чистые и идентичны fetched origin/codex/card-game-portability-audit1e02a70c2; совместимость остальных областей этим не доказана.

## Сессия и framing

ChatServerNew слушает TCP default127.0.0.1:12345; env/settings могут заменить адрес. Собственный asyncio loop в supervised thread, start ожидает ready≤5s. Network authentication/TLS нет; role self-declared. Framing UTF-8 JSON object + newline. Python inbound default8MiB, env override minimum1KiB. Malformed JSON/UTF8 получают error, connection продолжается; oversized frame закрывает connection. Dispatch последовательный на connection. Общей inbound deadline/connections cap здесь не обнаружено.

Outbound Python writer.write(JSON), write newline, await drain; нет application ACK. Per-writer bounded output queue/общая send deadline в просмотренном коде отсутствуют. client_id=peer ip:port + connection sequence; disconnect очищает role/task mappings/participants/echo state и сообщает core. Очистка mappings сама по себе не отменяет generation.

Hello необязателен; роль может прийти полем любого request, затем менять нельзя до reconnect. hello_ack: protocol_version1/session_id/client_role/owns_player_input. Самая свежая role=game получает input; если явных game нет, единственный anonymous client допускается как старый мод. Несколько anonymous не получают input автоматически. Это compatibility policy, не authentication.

## Unity client

NetworkBootstrapStep→NetworkRuntime.Initialize регистрирует handlers и connection. NetworkController имеет socket/NetworkStream, lifetime generation/CTS, receive/writer loops и перевод connection events на main thread. Hook disconnect при quit/destroy, subsystem registration сбрасывает static state/queues/events. Fault catch reconnect backoff1..10s; обычное завершение loops возвращает к connect без этого catch delay.

Receive ReadLineAsync→JSON parse background→main-thread router; явного bound размера строки Unity не найдено. Writer ConcurrentQueue без maxsize + SemaphoreSlim, один serialized writer. Future завершается после Write/Flush. Cancellation после write может сообщить cancelled, хотя request ушёл; отдельного cancel_task action нет. Disconnect отклоняет pending outgoing. Unity endpoint фиксирован127.0.0.1:12345, Python host/port settings его не изменяют.

GameConnectionSession отправляет hello на connectivity true и хранит session/owns flag. Hello protocol_version1 и result response_protocol_version3 — разные contract layers. Общей negotiation совместимых возможностей не видно.

## Actions и request mapping

Registry: hello/create_task/get_task_status/get_settings/get_music_beats/speech_state/asr_ptt_state. create_task поля: type/character/sender/participants/origin_message_id/data/context/req_id. Python→Unity: task_update с uid/status/body, loaded_settings, hello_ack, asr_text, asr_capture_state, error, beats messages.

Подтипы create_task: answer, continue, idle_timeout, game_master_observe/command, system_info_flush, react, camera_snapshot_result, tv_reaction, easel_drawing. Unknown/blocked возвращает synthetic ABORTED с req_id. IGNORE_GAME_REQUESTS блокирует все либо idle_timeout. До block check уже обновляются game fallback state и dialogue target: запрет generation не означает отсутствие mutations.

Context: distance/rooms/world identities, world state, runtime rules/static catalog/capabilities/intent rules, consumable events/TV observation, изображения. Persistent fallback исключает runtime_events/TV observation, сохраняет остальные поля. Player answer обновляет Unity target character; sender проходит identity resolver, пустые participants могут взять последний список сессии.

Shared dispatch создаёт task; для player game chat с req_id сохраняет retry request, но failure persistence не блокирует generation; затем initial task_update и Chat.SEND_MESSAGE. Общая строгая schema validation всего payload не найдена. req_id обеспечивает correlation, общего idempotent create admission здесь не видно.

React проверяет L1/L2 settings, batch≤24 событий, count1..1000. Duration не показывается LLM из-за неустойчивого Unity contract. Camera/easel/TV имеют отдельные source labels. Idle дедуп только последний PENDING по character; это не Unity scheduler. GM принудительно выбирает GameMaster/policy. Continuation/auto dialogue admission принадлежит Unity, Python исполняет уже разрешённый turn.

## Delivery и consumer

ServerController дополняет task stats, обновляет persistent retry state и schedule_send_task_update. Для SUCCESS/FAILED_ON_VOICEOVER успешный Future вызывает UnityRetryStore.complete_delivery. Future означает send_json→drain, **до принятия Unity**.

Unity router→TaskOrchestrator deserialize body→DialogueTaskTracker.TryResolve по uid/req_id→UI sync→final processor. Неизвестный context может быть отброшен. Tracker final statuses: SUCCESS/FAILED_ON_GENERATION/FAILED_ON_VOICEOVER/ABORTED/CANCELLED; generic FAILED в этом перечне нет, сопоставить с Python transitions отдельно.

Unity требует response_protocol_version==3; отсутствие/неверная версия/нет text response приводят к reject. После validation commits runtime event batch, schedules presentation/intents и вызывает локальный AcknowledgeDelivered. Этот метод очищает dictionaries, не отправляет сетевой ACK. Presentation fire-and-forget, acknowledgement не ждёт audio/команды. При generation failure runtime events остаются для следующего turn.

FAILED_ON_VOICEOVER может показать warning и применить готовый текст с muted audio; ABORTED/CANCELLED могут быть тихими. Success transport недостаточен для этих consumer outcomes.

## Audio и ASR

Audio передаётся как local filesystem path. Unity читает bytes, decode/normalize/fade-in background, создаёт AudioClip main thread; затем best-effort удаляет source **после загрузки**, до проигрывания. Ошибка load возвращает null, cancellation пробрасывается, error file может остаться. Decoder форматные ограничения ещё не проверены.

SpeechStateReporter хранит один tracked source/character/global active. Повторный start обновляет tracked state без нового active event; end poll0.1s ждёт source до120s. Producer не передаёт speech_id/duration, хотя Python consumer поддерживает leases по ним. Перекрывающаяся речь и lease tail требуют дополнительного прохода.

ASR_TEXT содержит utterance id и optional capture id/generation/revision/autosend/delay. Unity dedup64 ids; captured text идёт PTT controller, ordinary final — auto submission либо ShowRecognizedText. ACK распознанного текста нет. Python desktop fallback только при failed socket send, позднее Unity rejection не подтверждается обратно. ASR capture-state ACK подтверждает **команду записи**, не создание диалогового хода.

## Требования с нуля

Различать transport acceptance, task admission, result acceptance и presentation outcomes. Выбрать durability/reconnect/idempotency и единственного input owner независимо от GUI. Outbox complete должен соответствовать объявленной гарантии. Versioned schemas/capability negotiation, remote cancellation, frame bounds/overload, source revision и ownership media artifacts — самостоятельные проектные решения.

## Доказательства и остаток

Python server.py основной файл; registry и hello/get_settings/get_task_status/asr_ptt_state/speech_state/create_task полностью. ServerController lifecycle/delivery/ASR, settings body не весь. Unity NetworkController transport/context/send/audio entry+cleanup, GameConnectionSession/router/TaskOrchestrator/runtime/bootstrap/AsrTextHandler/SpeechStateReporter. Workflow tracker/DispatchAsync и ResultProcessor final/default/react/version/presentation диапазоны.

Не закрыты full scheduler/admission, ASR PTT controller, settings mapping, image transfer, beats, intents/tools/gameplay. Unity/tests/dotnet build не запускались.

Продолжение: scheduler/admission/ASR и auto-dialogue рассмотрены в отдельных документах; media/settings также описаны отдельно. Полный intents/executor/presentation audit остаётся открытым.

Дополнительно TaskManager/TaskController Python прочитаны полностью. Tasks in-memory, UUID, deep-copy data/snapshots, update повышает revision; result dict merge, error сохраняется, если новый не указан. Ограничения допустимых state transitions нет: status можно переписать после terminal. Cleanup запускается при create не чаще1h, удаляет всё старше24h от created_at, независимо от status. GetTaskStatus отдаёт snapshot без проверки принадлежности client; доверие local protocol. Unity TaskData revision не хранит, generic FAILED в enum отсутствует. Production emit FAILED по текущему rg не найден, поэтому несовместимость enum условная, а не доказанный ежедневный сбой. Stale/out-of-order task snapshots и late voice update требуют явной policy в новой реализации.
