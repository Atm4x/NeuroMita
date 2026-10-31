# Диалог и генерация: основной turn

Статус исследования: основной orchestration path восстановлен; providers wire formats, prompt DSL, history transactions, UI admission и все retry/regenerate ветви ещё не завершены. Источники — Python releases `38172493fa0d1caf1a5225bc1c559f095f18bb7a`.

## Источники

| Источник | Проверенный участок |
|---|---|
| `src/controllers/chat_controller.py:209 ChatController` | Создание, semantic API, activity, subscriptions |
| `src/controllers/chat_controller.py:486 _run_request` | Generation, streaming, task output, TTS handoff, errors/finally |
| `src/controllers/chat_controller.py:1080 _submit_request` | Bounded admission и cancellation token |
| `src/controllers/chat_controller.py:1140 _on_send_message` | Нормализация источника и retry cache |
| `src/controllers/model_controller.py:1319 generate_chat` | Per-character serialization |
| `src/controllers/model_controller.py:1353 _generate_chat_serialized` | RAG, snapshot, effective capabilities, prompt, provider, plain/structured split |
| `src/controllers/model_controller.py:2126 _process_structured_output` | Parse/rejection, mutations, tool branch, history |
| `src/controllers/model_controller.py:2495 _handle_tool_call` | Tool execution/continuation |
| `src/handlers/chat_handler.py:220 generate`, `:252 _generate_chat_response` | LLM request construction и runner orchestration |
| `src/core/request_policy.py:8 RequestPolicy`, `:76 resolve_policy` | Различия сценариев |
| `src/core/cancellation.py:15 CancellationToken` | Cooperative cancellation |
| `src/core/character_locks.py` | Короткий state lock и отдельный generation lock |

## Functional Capability: ответ, реакция и инициатива

**ID:** `CAP-LLM-001`. **Статус:** ACTIVE. **Домен:** dialogue orchestration.

### Назначение и сценарии

Ответить на конкретное входящее сообщение; отреагировать на событие видимо или скрыто; инициировать реплику без сообщения игрока. Внешний game/task запрос использует ту же generation ветвь, но имеет дополнительные task/dialogue identifiers.

`reply` требует непустой message_id и передаёт его как origin_message_id. `react` требует instruction и разрешающие REACT_ENABLED + REACT_L1_ENABLED/L2_ENABLED; выключенная реакция возвращает False. Видимая реакция — L2, скрытая — L1. `initiate` использует chat policy и по умолчанию sender=System. Успех semantic submit означает отправку в orchestration, не успешную генерацию: admission rejection не возвращается наружу как False.

### Входы

character_id, user_input/system_input, sender, participants, images + source, task_uid, req_id/origin_message_id, policy, game_state snapshot, dialogue context/source, current/previous player message source, GM instruction override, trace id. Не все источники предоставляют все поля. Source transition запоминается отдельно; UI failed request cache хранит до 256 request copies по incoming message id, дополнительно последний UI request.

### Выходы

Текст/structured segments, assistant message id, thinking, voice profile, parse provenance/control-plane trust, sample/context snapshot ids. Дополнительно: history commit events, UI deltas/final rendering, task status, TTS request и изменения персонажа. Это несколько наблюдаемых результатов одного turn.

### Политики сценариев

| Сценарий | History в prompt | Запись turn | UI/stream/voice | Template/system input |
|---|---|---|---|---|
| chat | Да | Да | Разрешены, дополнительно settings/capabilities | Default, system role |
| react L2 | Да | Да | Разрешены | main_template.txt, event role |
| react L1 | Нет | Нет | Запрещены | react_template.txt, system role |
| game_master_observe/command | Нет | Нет | Запрещены | Системная задача, policy принудительно пересчитывается |

Запрет записи turn не означает отсутствия любых изменений: structured effects могут применяться отдельно от history policy. Также ChatController может заранее записать отображаемый system input отдельной операцией. Требуется проверять каждый side effect, а не обобщать write_to_history на весь pipeline.

### Владение, очередь и сериализация

ChatController регистрирует operation/token/character до постановки в GENERATION pool. Activity включает уже принятые ожидающие очередь запросы. PoolSaturated снимает activity, выдаёт failure UI event и task FAILED_ON_GENERATION. Размер/правила pool будут описаны при executor audit.

ModelController проверяет выбранного персонажа; неизвестный id/отсутствие персонажа даёт failure и None. Полная генерация защищена per-character generation lock; state snapshots/mutations — отдельным коротким character lock. Другие персонажи не обязаны ждать тот же lock. Ожидание generation lock не прерывается token cancellation немедленно: проверка происходит после получения lock.

### Последовательность основного turn

1. Нормализовать request/dialogue/source, создать stream correlation, вычислить effective policy.
2. Для task выставить PENDING. Подготовить UI streaming callbacks/JSON filter; нормализовать изображения bytes/base64. При разрешении показать system/image input.
3. Вызвать GenerationService.generate_chat. Найти персонажа и получить его generation gate.
4. Получить RAG context (кроме GameMaster/L1), exact core-memory triggers, private copy game state и character-specific world context; зарезервировать список временных system infos.
5. Выбрать пресет персонажа/сценария до вычисления capabilities; определить tools, response schema profile, working-state/action-memory, image support и prompt features.
6. При IMAGE_DESCRIPTION_ENABLED получить textual descriptions отдельным vision handler и передать hidden context вместо изображений. Исходные bytes сохраняются для истории. Источник TV/easel/character camera определяет смысл описания. Если describe бросает exception, изображения могут остаться в основном запросе; при нормальном возврате image_data очищается даже если описаний нет.
7. Собрать prompt под коротким character lock. Записать context snapshot для chat, разрешить intents только согласно выбранному шаблону, подготовить schema для custom params.
8. ChatModel строит request, сохраняет диагностический snapshot, runner выполняет preset chain/attempts/provider. Дальнейшие wire contracts описываются отдельно.
9. Разделить thinking и visible text. Выбрать plain NLP command path либо validated structured path. Применить эффекты персонажа, записать history при policy, опубликовать usage/completion.
10. Вернувшись в ChatController, проверить cancellation, обработать empty/GM result, выдать task SUCCESS либо VOICING и TTS request, завершить UI stream или показать nonstream answer.
11. Finally закрывает coalescer, при незавершённом stream посылает aborted finish, снимает operation activity. Trace завершится здесь либо продолжится до voiceover.

### Errors и cancellation

Token cancellation сначала cooperative: остановка всех active generations вызывает cancel каждого текущего token. CancellationToken идемпотентен, вызывает callbacks вне lock; новый callback после cancel вызывается сразу. Подписки дочерних tokens автоматически не удаляются.

OperationCancelledError превращает task в CANCELLED, не выдаёт обычную generation error. Любой другой exception — FAILED_ON_GENERATION и UI failure при echo_to_ui. None result/empty response — отдельные ошибки. GameMaster со structured segments может иметь пустой visible text: task получает пробел как transport placeholder.

В plain path изменения переменных/памяти происходят до write_turn. Structured path тоже применяет effects до возможного tool execution/следующего запроса/финального history commit. Отмена после generate_chat может произойти после уже сохранённого turn. Следовательно, сейчас нет подтверждённого инварианта «cancel откатывает весь ход». Для новой системы это отдельное решение о границе commit, не свойство Rust.

### UI и озвучка

Streaming требует ENABLE_STREAMING, allow_streaming и echo_to_ui. StructuredJsonStreamFilter выводит значения text и отдельно reasoning; это scanner для UI, не окончательная валидация JSON. SHOW_THINK_IN_GUI управляет reasoning. Роли assistant/think переключаются с flush, UI events отправляются ORDERED. Финальный stream id связывается с сохранённым message id, sample и context snapshot.

Без streaming thinking показывается перед assistant. При streaming отсутствующие deltas могут быть заменены финальным текстом. Частично показанный ответ при ошибке получает aborted finish.

Если есть текст, USE_VOICEOVER и allow_voiceover, voice_profile определяет speaker; GameMaster дополнительно требует GM_VOICE. Передаётся text/task/character/profile/message/trace. При TTS handoff task становится VOICING и generation trace остаётся незавершённым. Успех LLM и успех аудио — разные outcomes.

### Особый GameMaster postprocessing

ChatController не включает GM в очередь Mita-to-Mita. Явная пользовательская GM/test instruction может детерминированно создать broadcast intent, если модель не дала actionable directive. У пустого personal send-system intent отбрасываются некорректные arguments. Эта доверенная инструкция отличается по происхождению от model-produced intents. Семантику исполнения подтвердить на Unity стороне.

### Требования к новой реализации

Сохранить сценарии/политики, корреляцию, очередь и видимость состояний. Формально определить стадии admission→context→provider→validation→effects→commit→delivery→voice; определить доступную отмену каждой стадии. Отделить transient UI stream identity от persistent message identity. Состояния памяти/персонажа и запись истории требуют явной модели согласованности. Обязательна provenance для repaired/rejected model output.

### Возможная переорганизация и Rust alternatives

Нужны предметные операции Reply/React/Initiate и отдельные owned ресурсы provider request/history/audio. Из этого пока не следует необходимость actor на каждый существующий controller. Сравнение каналов, owned application services и actors — после полного discovery. Выбор crates не сделан.

### Пробелы

UI send command/admission; все retry/regenerate/delete/snapshot ветви; exact prompt templates/DSL; history writer semantics; structured parser trust; tool implementation и limits; provider wire formats; реальный shutdown активного ChatModel; image lifetime. Это обязательные продолжения, не исключения из аудита.

## Functional Capability: structured effects и tool continuation

**ID:** `CAP-LLM-002`. **Статус:** CONDITIONAL: effective structured_output. **Источники:** ModelController._process_structured_output/_handle_tool_call.

### Назначение, данные и правила

Получить машинно проверяемые segments/actions/state changes вместо разбора только свободного текста. Profile зависит от runtime capability, персонажа, tools mode/depth, изображений, schema reasoning и template intents. Native mode запрещает schema tool_call и дополнительно валидирует native call. Sanitize ограничивает поля действующим профилем.

### Parse failure

StructuredResponseParseError не пересылает сырой JSON как нормальный ответ. При write_to_history сохраняет rejected assistant с assistant_is_deleted=True, исходным raw text, usage и thinking; ошибка сохранения логируется отдельно. Возвращается пустой result с error_details code/stage/field, parse_level=rejected, control_plane_trusted=False. Parser repair semantics ещё не разобраны.

### Effects и working state

После parse/validation character.process_structured_response и flush_variables выполняются под state lock. Effects возможны даже для промежуточного tool turn. Working state обновляется только финальным ответом при включённом feature; None очищает состояние. Поле исключается из UI/task/history structured_data, в отличие от reasoning, который отображается отдельным think block.

Комментарий перед `_raw_json` утверждает «not saved to history», но comprehension history_dict явно сохраняет `_raw_json`. Фактическое удаление может происходить ниже в writer; это ещё не проверено. Нельзя утверждать отсутствие persistence только по комментарию.

### Tool lifecycle

Allowed tool требует tools_on, доступное имя и depth < TOOL_MAX_DEPTH. Начальный набор: calculator/web_search/google_search/web_reader/memory_search/reminder; reminder дополнительно gated REMINDERS_ENABLED. Реальные реализации исследуются отдельно.

Промежуточный assistant turn сохраняется/показывается, затем запускается tool. Исключение tool превращается в textual Tool error и может использоваться следующим LLM запросом. Native history дополнительно содержит native tool followup messages; обычная schema ветвь подмешивает system/user/both согласно TOOL_RESULT_MSG_MODE.

Продолжение использует тот же preset и depth+1, отключает дальнейшие tools на лимите, объединяет usage/thinking и повторно проходит structured validation/effects. User_input в продолжении пуст, чтобы не дублировать пользовательское сообщение. Followup не получает исходные stream callbacks.

Если followup пуст, возвращается первый ответ как fallback с parse_level=tool_intermediate и control_plane_trusted=False. Это не атомарный rollback tool effect/history. UI tool events в этом path посылаются непосредственно без проверки echo_to_ui — влияние на скрытые реакции нужно проверить отдельно.

### Требования, UI, ошибки и реорганизация

Нужен явный control/data contract, бюджет глубины tools, корреляция intermediate/final turns, сохранение audit provenance и понятный результат частичного успеха. Tool error, rejected structured output и отмена — разные outcomes. Выделить validation, разрешение effects и persistence policy; Python-class границы не копировать. Rust alternatives и формат схем будут исследованы после полного набора полей/интентов.
