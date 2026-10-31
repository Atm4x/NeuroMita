# Structured response: форматы, восстановление и исполнение

Статус: ACTIVE/CONDITIONAL. Полностью прочитаны structured_response.py, sparse_structured_response.py, structured_response_parser.py, StructuredResponseCapabilities/runtime_capabilities и provider structured_output adapter. Это core processing, даже если исходный текст выдал AI. Полный provider wire audit остаётся отдельной ветвью.

## Входы и нормализованная модель

Внутренняя StructuredResponse содержит ordered segments, reasoning, image_description, stat changes, secret flag, memory CRUD/merge, reminders/timers, graph entities/relations, tool_call, custom_fields и working_state. Segment содержит text и набор game/presentation fields, target/addressee, hint, allow_sleep и intents type+payload. RESPONSE_PROTOCOL_VERSION=3 ставит Python в result, модель его не выбирает. Unity ожидает именно3.

Схема для provider и внутренняя validation model различаются: schema требует segments, может требовать явное решение secret_exposed, исключает недоступные поля. Внутренний segments имеет default[], optional secret flag может отсутствовать. Numeric deltas finite-normalized, per-turn/total clamps применяются позже character state. Custom fields генерируются динамической Pydantic model из character config: change_command/name, разрешённые identifier keys, type/nullable/default/required и numeric change_min/max. Cache keyed по content hash конфигурации, явного size bound для этого cache нет.

SegmentIntent валидирует только shape/nonempty type; фиксированного списка известных intent ids и payload schemas на Python стороне нет. Payload JSON string декодируется в object; inventory name string поддерживает shortcut. Invalid non-object payload заменяется на {}. Non-object intent/empty type отбрасывается. Это compatibility normalization, а не подтверждение исполнимости конкретной команды.

## Request-scoped capabilities

Runtime snapshot различает connected=true/false/unknown. При точно remote-only и включённом REMOTE_ONLY_STRUCTURED_FIELDS_EXCLUSION_ENABLED исключаются emotions/animations/idle/movement/visual/clothes/interactions/face/allow_sleep/intents. Unknown connection не приравнивается к disconnected. commands/music/start_game/end_game остаются program-capable, text/target/hint shared. Поэтому наличие commands без Unity не является автоматически ошибкой: надо проверить core command routing.

Дополнительные gates: ENABLE_GAMES; RAG+graph extraction; REMINDERS_ENABLED для reminder/timer; structured+tool mode/names/depth; image presence+inline description; character secret capability/revealed; schema reasoning; working state; custom params. Prompt intents opt-out и L1 exclusions дополняют profile. Один profile формирует prompt feature flags, provider schema exclusions и post-parse sanitization. Snapshot отражает момент request, реальная Unity availability при execution может измениться.

Sanitize выставляет исключённые top-level поля None, segment lists=[] и scalars=None; disallowed tool name удаляется. Это проверка класса функции/поля, не per-intent authorization или runtime preconditions.

## Полный и sparse wire formats

Обычный формат — full segments + top-level fields. OpenAI adapter строит json_schema strict=false либо json_object по настройке. Gemini adapter inline refs, преобразует schema subset и кодирует free object tool args/intent payload строками. Это наблюдаемые преобразования в коде, актуальные ограничения внешних API ещё не проверены по документации.

Responses adapter может включить sparse_enabled: segments имеют Text/Expression/Action/Full variants, top-level operations вынесены в changes[{type,value}] либо tool_call{name,args}. Поля changes строго сгенерированы из разрешённого profile; list effects представлены отдельными entries, scalar duplicate запрещён. Reasoning/secret/custom сохраняются explicit top-level decisions, если разрешены. Arbitrary payload/args/custom object могут быть JSON-encoded string. Strict DTO extra=forbid, strict=true, allow_inf_nan=false; nested JSON object parser отклоняет nonfinite constants и non-object root.

Sparse normalize возвращает прежнюю full internal shape перед effects/history/task output. Sparse changes не пересылаются Unity как отдельный протокол. Parser выбирает sparse normalization по наличию changes **или events**, независимо от transport setting; events не объявлен в strict DTO и сам по себе не является поддержанной альтернативной операцией. Disabled variant/duplicate scalar/invalid nested JSON rejects целый sparse response до обычного coercion.

## Лестница восстановления

Input должен быть непустой string. Extractor убирает BOM/markdown fence либо извлекает embedded JSON, распознаёт truncation. Далее direct json.loads → trailing comma/newline repair → inner quote escaping → closing truncated delimiters → discard incomplete tail + close → optional json_repair library → close+json_repair. Root обязан быть object. Ошибки имеют code/stage и безопасное field path без raw input; диагностический exception/log может содержать фрагмент исходного текста.

Validation сначала обычный Pydantic model_validate. При failure schema-aware pass приводит scalar→lists, string stats→float, missing/null fields, working_state shorthand, hoists misplaced custom/state/memory/graph fields, приводит entity/relation object forms. Повторный failure возвращает StructuredResponseParseError. Legacy flat JSON и partial text extraction используются только после валидации при отсутствии segments; tool_call допускает synthetic empty segment. Полностью пустой segment text может пройти parser, последующий ChatController определяет empty generation отдельно.

Repair сохраняет не только речь: completed commands/intents и другие поля могут оставаться в repaired response. Partial extraction, напротив, собирает text и обнуляет deltas. Полученный результат нельзя трактовать как один универсальный «безопасно восстановленный текст».

## Provenance и actual effect gates

Outcome.control_plane_trusted=true только при direct parse, без explicit coercion/fallback, extraction raw JSON или markdown fence. Repaired/embedded/truncated — false. **Этот флаг не является глобальным запретом исполнения**: ModelController после capability/native-tool checks применяет character effects, graph/memory/state и tool continuation независимо от parser trust. ChatController передаёт trust metadata в task; специальная проверка есть в GM explicit-instruction fallback. Unity scripts не содержат обращений к control_plane_trusted/structured_parse_level и исполняют подходящие segment commands/intents после своей validation.

Кроме того, первая Pydantic validation и before/after validators могут нормализовать input без schema_coerced=true. Перенос top-level commands в первый segment тоже не меняет trust metadata. Поэтому trusted означает ограниченную классификацию parse pipeline, а не отсутствие изменений исходного JSON или доказанную payload semantics.

В изолированном Python subprocess проверены пять synthetic cases, без logger файлов/app/database/network: baseline trusted; allow_sleep="false" и attitude_change="2.5" нормализуются с trusted=true/schema_coerced=false; invalid intent payload string превращается в {} с trusted=true; top-level commands переносится с trusted=true; missing outer brace сохраняет intent с trusted=false/truncation_close. Environment Pydantic2.10.3, requirements pin2.10.6: это проверка поведения доступного окружения плюс независимое подтверждение ветвей исходником, не выполненные release tests. Никакие игровые команды не исполнялись.

## Unity consumer и addressing

ResultProcessor парсит segments, target strings enum case-insensitive. Для auto dialogue группирует text по recipient, исключая Player/empty/source/None; full response/address map несут контекст остальных сегментов. Target — адресат речи, не имя GameObject для action. Unity protocol DTO сохраняет extensionData, поддерживает legacy actions alias в intents. Decoder сначала обрабатывает flat segment fields, затем structured intents; отдельные directives переставляются: outfits/apply presets впереди, save presets в конце. Внутри plan directives исполняются **до всех intents**, исходный interleaving двух групп не сохраняется.

## Требования к новой системе

Сохранить full/sparse compatibility только если она нужна как external contract; внутренняя модель может быть новой. Нужны явные parse provenance, набор допустимых operations с typed payload validation, решение какие effects разрешены после каждого вида repair. Разделить «JSON синтаксически восстановлен», «shape валиден», «функция включена», «runtime может исполнить», «эффект завершён». Dynamic custom schema и provider projection не требуют копирования Pydantic-классов в Rust; это предмет отдельного schema/compiler design и dependency research.

Остаётся проверить per-command limits/actual execution, downstream command failure feedback и provider streaming/tool adapters. Новый GameMasterResponse/actions executor найден в исходниках/тестах, production registration пока не найден: не считать его действующим вместо старого segment-intent GM пути.
