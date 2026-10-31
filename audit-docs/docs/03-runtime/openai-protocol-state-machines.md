# Chat Completions и Responses: состояние диалога, tools, streaming, отказы

**Основание:** поставленный `CodeNow.zip`, прежняя ревизия Python `releases/38172493` указана в checkpoint, но в ZIP нет `.git` для независимой проверки SHA. **Способ проверки:** детальное статическое чтение исходников; реальные провайдеры не вызывались. **Статус:** `CONDITIONAL` — зависит от выбранного protocol/dialect и настроек.

## Назначение

Один application turn строит `LLMRequest`, затем provider/protocol сериализует диалог в один из несовместимых wire-contracts. Форматы Chat Completions и Responses нельзя объединять по признаку «оба HTTP JSON»: отличаются представление истории инструментов, reasoning, multimodal content, терминальность потока и отклонения. Исторические Python-классы не являются кандидатами на перенос 1:1; это исходные доказательства контрактов.

## Подтверждённый путь выполнения и источники

| Слой | Доказательство | Контракт |
|---|---|---|
| Chat Completions encode | `src/handlers/llm_providers/protocols/chat_completions/request.py:18-115` | `req.messages` → message allowlist, native/unified parameters, OpenRouter provider routing, optional stream usage, tools, schema |
| Chat Completions HTTP | `src/handlers/llm_providers/openai_http_base.py:32-95,97-254` | URL rewrite только очевидного base URL; query/headers; HTTP 400 format downgrade; closure of stream |
| Chat Completions decode | `src/handlers/llm_providers/protocols/chat_completions/response.py:15-106` | Первая `choice`, text/reasoning/tools, finish reason, usage, persisted tool history |
| Chat Completions stream/tools | `src/handlers/llm_providers/protocols/chat_completions/stream.py:13-75`, `tools.py:10-115` | Дельты текста/рассуждений и сборка calls по index, финальный finish reason |
| Responses encode | `src/handlers/llm_providers/protocols/responses/request.py:13-140` | Item-based input, typed function call/output, protocol history, policy/gates |
| Responses HTTP | `src/handlers/llm_providers/responses_provider.py:12-83` | Только dialect `openai_responses`; safe header subset, запрет redirect, статус/parse/cancel |
| Responses decode | `src/handlers/llm_providers/protocols/responses/response.py:11-82`, `tools.py:8-58` | Terminal status, structured output items, tool identity/advertisement, raw replay |
| Responses stream | `src/handlers/llm_providers/protocols/responses/stream.py:14-203` | Item identity/index, delta/pending arguments, terminal response, refusal/error handling |
| Историческая миграция | `src/handlers/llm_providers/protocols/history.py:4-28` | Старые `responses_output`/`responses_reasoning_items` → `protocol_history` |
| Special ChatGPT Plan | `src/handlers/llm_providers/chatgpt_plan_provider.py`, `.../chatgpt_plan_protocol.py`; [предыдущий аудит](provider-wire-contracts.md) | Отдельная более узкая `ResponsesPolicy.siwc()`, нельзя приравнивать к generic Responses |

### Chat Completions: параметры и трансформации

- При `native_parameters is not None` их копия используется вместо унифицированной схемы; иначе select `temperature`, `max_tokens`, penalties, `top_p`, условные `top_k`/`logprobs`, reasoning. `reasoning_control` выбирает разные wire shapes для OpenRouter (`reasoning`), DeepSeek (`thinking`) и effort (`reasoning_effort`); отсутствие `enable_thinking` не создаёт этот блок (`request.py:18-74`).
- Неизвестные поля истории отфильтрованы allowlist; вложенное protocol history Chat Completions может восстановить tool calls поверх текущих (`request.py:77-87`). OpenRouter дополнительно модифицирует trailing system, cache annotations, routing/session id (`:88-100`); значит одно и то же `LLMRequest.messages` не всегда имеет одну семантику для разных preset.
- `response_format` выставляется лишь при `structured_output` и `native_structured_output`. При **HTTP 400 с распознанной ошибкой формата** общий OpenAI-compatible transport может повторить HTTP-запрос: `json_schema → json_object → без response_format`; максимум два narrowing steps, независимо от внешнего retry runner (`request.py:118-165`, `openai_http_base.py:127-154`). Это *не* general API fallback и не доказательство полной идемпотентности.
- `openai_http_base.py:97-105` при `depth > 3` возвращает `LLMResponse` с `error_message`, а не бросает typed exception: верхний caller обязан различать failure-as-response и failure-as-exception. У других протоколов это ограничение нужно проверить отдельно.

### Chat Completions: завершение turn

- Nonstream считает существенной первую choice; `finish_reason ∈ {length,content_filter,error,failed,cancelled,incomplete}` или `message.refusal` переводится в error field; пустой текст без tool calls — тоже error field, а не успешная пустая реплика (`response.py:59-106`). Reasoning извлекается из `reasoning_content`, `reasoning`, `reasoning_details`; OpenRouter usage cost маркируется в credits (`:40-56`).
- Stream accumulates content/reasoning/tool deltas from first choice. Если есть content/tool/reasoning, но поток закончился без terminal `finish_reason`, создаёт `stream.incomplete`; errors/refusals terminate. Пустой поток без meaningful content может закончиться response with error_message, не обязательно exception (`stream.py:24-75`).
- Tool calls объединяются по numerical `index`. `ToolCallAccumulator` конкатенирует фрагменты имени и JSON arguments, хранит дополнительные поля и выдаёт ordered list (`tools.py:73-115`). В итоговой parser-ветке аргументы **обязаны быть JSON object** (`:25-51`). Реальное выполнение tools регулирует более высокий слой и не должно запускаться на незавершённой дельте.

### Responses: запрос и история

- `system → developer`; `user`/`assistant` сохраняются, `tool` превращается в `function_call_output` при обязательном `tool_call_id` (`request.py:74-90`). В `protocol_history.openai_responses.output` допускаются raw `reasoning`, `message`, `function_call` только для assistant; есть отдельный fallback `reasoning_items` и преобразование старых inline полей (`request.py:91-120`, `protocols/history.py:4-28`).
- Multipart текстовые блоки получают `input_text`/`output_text`, URL изображения — `input_image`; при `input_image` создаётся **user item** даже внутри assistant content (`request.py:32-71`). Это адаптация текущего кода, не гарантия семантики удалённого сервиса. `input_file` разрешён только для user; неизвестные блоки отвергаются ValueError.
- Формируется `model/input/store=False/stream`; whitelist native параметров зависит от `ResponsesPolicy`. `ResponsesPolicy.siwc()` ограничивает его `reasoning/text/parallel_tool_calls`, запрещает запись store и принуждает wire stream (`request.py:13-29,121-140`). Native tools проходят через namespace, `parallel_tool_calls=False` в namespaced variant. Structured output добавляется через `text.format` лишь при caps.
- Output `status=failed/incomplete/cancelled` и refusal дают `LLMProviderError` с `retryable=False`; неизвестный nonterminal status также error. Разбираются `message/output_text`, `reasoning`, `function_call`; произвольный output item ValueError (`response.py:29-82`). Протокольное `output` сохраняется в `LLMResponse.protocol_history` целиком для будущего replay.
- Tool decoder сверяет имя с *advertised tools*, требует call ID, object arguments и запрещает конфликтующие duplicate call IDs (`tools.py:30-58`). Отсутствие advertised tool невозможно легально превратить в команду пользователя.

### Responses: event stream

- `iter_responses_events` пропускает `[DONE]`, требует JSON object (`stream.py:14-21`). Возвращение результата требует **`response.completed`**, иначе `responses.stream_interrupted` (`:159-203`).
- `response.output_item.added/done` накапливается по `item.id`/`call_id`, при их отсутствии допускается временный `index:<n>`; конфликты id/call id — ошибки (`:47-80`). Аргументы function-call могут прийти до самого item и хранятся в `pending`; orphaned arguments при completion отвергаются (`:88-94,141-165`).
- Text/reasoning deltas могут отправляться UI через accumulator; при `req.stream=False` (но wire stream=True, например Plan) UI callbacks предварительно отключаются (`:24-30`). На terminal response старые deltas сверяются с final payload, raw tool/reasoning items достраиваются; fallback к собранному тексту только при отсутствии output_text (`:159-201`).
- `error`, `response.failed`, `response.incomplete`, refusal events прекращают streaming c typed failure (`:95-111`). Cancellation проверяется перед каждым event, но реальное время реакции ограничено скоростью чтения HTTP: это нужно моделировать отдельным тестом.

## Контракт владения состоянием и инварианты

1. **Conversation history ≠ wire history**: хранить source conversation и протокольно-специфический replay metadata отдельно; преобразование в wire — детерминированная projection с проверяемыми потерями данных.
2. **Tool execution только после терминального подтверждения**: streamer может показывать tool-start/delta, но execution orchestration принимает только validated completed call с именем, call id и JSON-object arguments.
3. **Failure taxonomy**: HTTP error, provider terminal refusal, incomplete, parse violation, stream interruption, cancellation, final `error_message` и developer constraints различимы.
4. **Retry policy с несколькими уровнями**: локальный HTTP 400 schema-narrowing ≠ вызов request runner fallback ≠ повторный dialogue turn. Все уровни должны быть проверены на tool side effects.
5. **Нельзя обещать полный parity Responses↔Chat**: item hierarchy, reasoning replay, stream phase, multimodal role conversion и namespace обязательны, если функция активна в конкретном preset.

## Риски и проверки

- `response.py:11-26` создаёт usage dict даже из `None`, потому `normalize_responses_usage(None)` возвращает `{}`; итог `LLMUsage` может быть `None` при полном отсутствии usage, но при пустом словаре — нулевым; необходимо goldens разных форм.
- `responses/stream.py:159-178` сшивает final payload и ранее виденные tools/reasoning. Нужны случаи duplicate id, partial event, out-of-order events и disagreeing final payload. Не объявлять здесь доказанный production bug.
- `responses/request.py:65-70` принудительное изменение роли image chunk в user item — риск смысловой перестановки при round-trip истории; golden test с assistant image.
- `openai_http_base.py:127-154` schema downgrade делает дополнительные HTTP попытки; зафиксировать observability попыток, отмену между запросами, реакцию на тело streaming 400.
- Для обоих протоколов необходимы unit fixtures без настоящих ключей и real integration отдельно; в этом проходе ни те ни другие не запускались.

## Требования к новому Core — без выбора Rust-архитектуры

`REQ-PROTO-001`: текст, reasoning, rich content, tool calls и протокольный raw history имеют явные типы/границы; неизвестные типы не превращаются молча в текст.

`REQ-PROTO-002`: cancellation и termination semantics проверяются отдельно для UI stream, wire stream и nonstream.

`REQ-PROTO-003`: nested HTTP format downgrade и external retries наблюдаемы, ограничены и не повторяют tool execution.

`REQ-PROTO-004`: fixture matrix проверяет JSON request, stream events, final response, usage, tool identity/namespace, schema fallback, refusal и serialization of old histories по обоим диалектам.

`REQ-PROTO-005`: сохранение protocol-specific history должно иметь явную версию и независимое от GUI владение.

**Неисследованное:** продвинутые provider-specific policy overlays/HTTP redirect hosts/проксирование, stream cancellation в реальном сетевом IO, наличие production callsites всех `protocol_history` сценариев и внешняя API совместимость. Источник выше задаёт только подтверждённое локальное поведение.
