# Песочница, контекст запросов и экспорт данных

**Capabilities:** CAP-DIAG-001—003, CAP-DATA-001—003. **Статус:** ACTIVE/CONDITIONAL GUI/core functions. Это наблюдение и сохранение данных, не встроенный training/inference pipeline.

## Песочница и состояние

Sandbox показывает текущего персонажа, его фактический API preset с per-character override, prompt pack, связь с игрой и availability voice/mic/RAG. Selectors поддерживают смену модели/персонажа/набора; выбор prompt сохраняется и reload-ит персонажа. Есть быстрые actions history/open/clear, настройки отображения, capture controls и debug. Текстовый чат/send/history/cancel/ASR описаны в отдельных функциональных документах.

Memory/status inspector показывает количество active/forgotten/deleted, missing embeddings, последнюю активность и размер DB. Effective history count вычисляется через HistoryService.prepare_for_prompt: это вызов подготовки контекста, не простой COUNT. Context budget/cost — оценка, зависит от последнего model stats/config, не доказанное provider billing. Отдельный budget panel сейчас закомментирован в registry, поэтому наличие viewmodel нельзя выдавать за видимую панель.

CharacterStateViewModel показывает attitude/boredom/stress, secret flag, числовые/boolean custom params и formatted variables. При построении snapshot читает variables/settings; это проекция состояния, не подтверждённый редактор переменных. Обновления вызывают смена/reload/reset/успешный ответ. Visibility панелей активная сессия/status/last_request/capture/actions управляется SANDBOX_PANEL_*; last_request по умолчанию скрыт, остальные включены.

Debug позволяет вставить system message в историю либо user [Системное] для provider compatibility, сохранить/загрузить history snapshot, открыть последний request/response, включить generation ingress capture и отдельные display/schema diagnostics. Snapshot mutation semantics — в [history](history.md). Скрытие UI inspector и остановка записи диагностических файлов — разные настройки.

## CAP-DIAG-002: просмотр контекста

Перед каждым LLM request ChatModel создаёт ctx_{uuid} и синхронно сохраняет SavedMessages/last_request_context.json плюс request_contexts/{id}.json. Это работает независимо от FINETUNE_COLLECTION_ENABLED и DEBUG_SAVE_LLM_DUMPS. В snapshot входят messages с image-payload redaction, модель/провайдер/протокол/dialect, ограниченный набор generation extras и локальная token projection. Api key из req не переносится в этот record целиком; сообщения всё равно содержат пользовательский текст и prompt.

После response в тот же per-request file добавляются raw/cleaned response, finish_reason и usage; обновляется также global last fallback. «Immutable» здесь означает зафиксированную request identity, а не file write-once: response дополняет файл. Request retries могут создавать несколько ctx artifacts. Общий retention этих files в прочитанном path не найден; dataset cap не ограничивает SavedMessages/request_contexts.

Открытие из конкретной реплики сначала ищет ctx id, иначе dataset sample id; при некоторых paths доступен общий last context с used_fallback=True. UI должен явно различать fallback от контекста выбранной реплики. ContextViewer даёт request/response tabs, tree groups, search next/previous/highlights, JSON formatting, fullscreen, copy JSON/messages/response/group; отображает sections/token/usage. По функциями rendering просмотрен частично, все HTML/actor formatting branches не закрыты.

Token projection классифицирует prompt/history/active context/current trigger по roles и markers. Изображения считаются отдельно, не входят в текстовую оценку. Token counter с tokenizer всё равно estimated относительно реального provider, иначе heuristic. У новой реализации фактический usage ответа и локальная оценка контекста должны иметь отдельные поля.

## CAP-DIAG-003: вход до построения prompt

GenerationInputCollector включается DEBUG_CAPTURE_GENERATION_INPUT_ENABLED, default False. Сохраняет last_generation_input.json и monthly generation_inputs_YYYYMM.jsonl. ModelController собирает incoming request/source/ids/policy/game state, состояние подготовки/capabilities и компактные image summaries. Он нужен для объяснения того, что пришло в generation до prompt build; это другой artifact, чем отправленные provider messages и полученный ответ. Полноценная кнопка replay из сохранённого payload не найдена, хотя описание класса упоминает replay.

## Dataset collection, rating, retention

GUI backend loader создаёт FineTuneCollector; headless equivalent initialization не подтверждено. FINETUNE_COLLECTION_ENABLED по умолчанию True при наличии collector. После успешного provider response, до очистки и прикладной structured validation, сохраняется месячный samples_YYYYMM.jsonl: UUID/timestamp UTC/character/model/provider/protocol/dialect/generation settings/game_connected/messages/raw response/rating/usage. Следовательно dataset record не равен успешно committed character turn: malformed response/tool intermediates могут быть отдельными samples.

По умолчанию сохраняются последние50 records по порядку lines/month files; FINETUNE_UNLIMITED отключает предел. Enforce limit удаляет старые файлы либо переписывает оставшиеся lines. Chat actions умеют rating1/-1 по sample id; sample id также переносится с response, а старый single pending sample slot существует для fallback UI. Rating переписывает весь месячный файл под локальным lock, без atomic temp replacement. Ошибка возвращает False и логируется; UI action этого bool не показывает.

GUI data section показывает stats total/rated/positive/negative/by-character, управляет enable/limit/unlimited, предлагает другой каталог, enforcement и удаление всех sample files с confirmation. Текущий browse переводит collector.data_dir; переноса старых файлов не делает. Startup FineTuneCollector constructor использует base/FineTuneData, а FINETUNE_DATA_DIR в нём не читается: применение сохранённого пользовательского пути при следующем запуске этим constructor не подтверждено. Data directory и retention должны задаваться одним functional contract.

Stats кешируются по file path/mtime_ns/size; load/stat scans не все держат writer lock. Corrupt JSON lines пропускаются, file IO failures могут дать partial count/list вместо error outcome. Операция clear возвращает количество реально удалённых файлов, даже если последующее удаление отказало.

## CAP-DATA-003: фильтры и экспорт

Collector поддерживает date range/characters/models/min_rating; GUI ExportDialog предоставляет даты UTC (конец дня23:59:59), checkbox character list, rating и формат. Invalid timestamp в record при date filtering может остаться в результатах, потому что parse exception не отклоняет запись. Empty character selection означает все. Просмотр числа подходящих записей и export загружают samples целиком; в прочитанном dialog это синхронные вызовы viewmodel, большого corpus QA не было.

Raw JSONL сохраняет все выбранные records. ShareGPT преобразует system/user/assistant в system/human/gpt, multipart content оставляет только текст, добавляет финальный response; tool-role entries пропускает. Это lossy text export, не round-trip native tool/multimodal conversation. Запись выдаёт count и может оставить partial destination при exception; UI сообщает count как завершённый export. Фактических файлов экспорта аудит не создавал.

## Требования новой системы

Различать generation ingress, immutable request identity, provider result, validated reply, committed history и dataset sample. Определить retention/export fidelity/user path/redaction для каждого artifact, не объединять их флагом «отладка». UI должен показывать exact vs fallback context и actual vs estimated tokens/cost. Dataset filtering/rating/export требуют observable failure/partial results, bounded reads и source correlation. Эти функции реализуемы поверх нового storage/UI с нуля; текущие JSONL/singletons не являются обязательным проектом для Rust.

## Доказательства и пределы

Прочитаны Sandbox controller/viewmodel основные selectors/status/memory/budget/actions, CharacterStateViewModel, panel registry, debug controls; FineTuneCollector целиком, FineTuneDataViewModel/presentation facade и data directory/export actions; ExportDialog filter/count/export; ChatModel context snapshots и collector hook, chat sample-context/rating lookup; GenerationInputCollector и ModelController capture assembly; ContextViewer controls/copy и symbol map, token stats основные branches. Не все diagnostic rendering/UI selectors и history/DB viewer capabilities закрыты. Пользовательские SavedMessages/FineTuneData/DB не открывались; GUI/model calls не запускались.
