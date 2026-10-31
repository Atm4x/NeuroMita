# Инструменты персонажа и доступ к вебу

**Capability:** CAP-TOOLS-001—006. **Статус:** CONDITIONAL. Подтверждён путь ModelController → общий ChatModel.tool_manager → builtin implementation → следующий LLM request. Это функции Python core; вызов модели для их выбора не превращает HTTP, вычисление или расписание в локальный AI inference.

## Функции и зависимости

| ID / tool | Пользовательская возможность | Реальная реализация и ограничения |
|---|---|---|
| CAP-TOOLS-001 calculator | Вычислить арифметическое выражение | Собственный AST evaluator: числа, скобки, + - * / // % **, unary +/-; имена, вызовы, attributes и subscripts запрещены. Это stdlib, не уникальная Python library. Ограничения сложности/величины выражения в evaluator не найдены |
| CAP-TOOLS-002 web_search | Найти страницы и вернуть title/url/snippet | DDGS.text; результат JSON. Переданный max_results напрямую идёт библиотеке; JSON schema диапазон3—20 не является runtime validation в ToolManager |
| CAP-TOOLS-003 google_search | Искать через настроенный Google Custom Search API | Общий HTTP client, GET googleapis customsearch/v1, GOOGLE_API_KEY и GOOGLE_CSE_ID из settings, timeout10 s; title/link/snippet. Код ограничивает num сверху15 и не реализует pagination; работоспособность всех значений отдельно не проверялась |
| CAP-TOOLS-004 web_reader | Получить текст страницы либо GitHub blob | URL blob преобразуется в raw.githubusercontent.com; затем GET https://r.jina.ai/{url}, timeout20 s; возвращается текст до max_chars плюс marker. BeautifulSoup импортируется, но в рабочем run не используется: собственной HTML extraction/JS browser ветви здесь нет |
| CAP-TOOLS-005 memory_search | Поиск прошлых фактов и реплик по запросу, источнику и датам | RAGManager.for_character.search_relevant с overrides; auto/fts/vector/hybrid/keyword, memories/history/both. Не зависит от автоматического RAG_ENABLED: непустой либо пустой dict overrides означает explicit tool search |
| CAP-TOOLS-006 reminder | Просмотр, создание, удаление напоминаний и создание автономного таймера | Character.reminder_system; list/add/delete/timer, ISO или набор RU/EN relative dates, positive delay через ReminderManager. Persistence/fire semantics — в [отдельной спецификации](reminders-and-timers.md) |

Web reader зависит от внешнего reader service даже при установленном bs4. DDGS также нельзя считать просто локальным HTML parser. Для новой реализации надо выбирать отдельно search provider и extraction strategy, их API/условия и доступность; текущая Python-обвязка не задаёт обязательную архитектуру. Актуальные ограничения внешних сервисов в этом проходе не исследовались; таблица описывает исходники.

## Доступность и настройка

ToolManager регистрирует четыре lazy builtin wrappers; ModelController добавляет memory_search и reminder. По умолчанию memory_search/reminder включены, остальные выключены. Общие gates: TOOLS_ON, capabilities.tools_prompt_enabled, TOOL_MAX_DEPTH>0, TOOLS_MODE!=off; GameMaster tools отключены. Reminder дополнительно требует REMINDERS_ENABLED. GUI содержит per-tool checkbox, depth, result message mode, Google credentials. TOOLS_MODE читается backend, но control этой настройки в просмотренном settings module не найден.

Lazy wrapper импортирует module и создаёт singleton tool при первом запросе description/parameters/run. Ошибка загрузки запоминается до пересоздания wrapper; schema getters возвращают «недоступен»/пустые параметры, а не исключают автоматически tool name. Включение optional package во время работы само по себе не сбрасывает этот failure cache. Фильтрация выключенных tools избегает их загрузки при обычном schema build.

## Выбор, выполнение и продолжение

Единый request profile определяет список и глубину. Native mode поддерживается runtime для openai_chat_completions и openai_responses при capability tools_native; иначе используется schema tool_call. Различие protocol transport и прикладного инструмента не должно потеряться в новой спецификации.

Native bridge допускает ровно один tool call за turn, требует advertised/enabled name, непустой call ID и object arguments, запрещает смешивание schema/native и уже использованный ID в текущей цепочке. Для streaming есть накопление function name/argument fragments. JSON arguments декодируются в object; полного runtime исполнения JSON Schema builtin parameters ToolManager не делает: вызывает run(**arguments), ловит исключение и возвращает текст Tool-Error.

Schema путь использует structured.tool_call и gates name/depth/tools_on. Обычные character effects к этому моменту могли уже примениться, поэтому tool chain не является транзакцией. До tool execution записывается промежуточная schema-реплика и отображается UI; native промежуточная history пишется после результата с protocol history. Working state промежуточного ответа скрыт и должен commit-иться в финальном. Публикуются ON_TOOL_EXECUTING/ON_TOOL_DONE и UI system message с результатом.

Tool исполняется синхронно на generation worker. Cancellation проверяется до него и перед следующим LLM call, но в Tool.run не передаётся token. HTTP timeouts двух сетевых tools не являются общим budget для всех инструментов. После результата следующий LLM request получает native call/result pair либо assistant JSON и tool result как system/user/both. Depth повышается, на пределе schema/profile запрещают новый call; изображения повторно в final continuation history не записываются. При пустом follow-up возвращается первая реплика с parse_level=tool_intermediate и control_plane_trusted=False; уже созданное напоминание/иной side effect не откатывается.

Native duplicate ID protection действует в текущих messages; это не durable idempotency расписания при повторе всей пользовательской задачи. Errors/no results/success имеют строковые форматы, универсального typed outcome builtin tools нет.

LegacyToolExecutor умеет искать XML/JSON calls в plain text и делать follow-up. По поиску src нет production import/instantiation этого класса. Его нельзя считать действующим альтернативным инструментальным pipeline только из-за имени файла. Dialect wrappers openai/gemini также не доказывают native Gemini orchestration: актуальный policy разрешает native только двум dialect IDs выше.

## Поиск памяти и время

Memory tool ограничивает limit1—50; при фильтре дат запрашивает в5 раз больше, затем фильтрует и обрезает. Это ограниченный post-filter retrieval, не гарантия всех результатов периода. Записи без распознанной даты отбрасываются. date_to расширяется до23:59:59; нераспознанные filters превращаются в None. Перечень доступных search_type вычисляется из settings, неизвестное runtime значение получает overrides по умолчанию. source=both не принуждает оба источника, а сохраняет текущие pipeline settings; formatter также умеет graph results.

Relative dates реализованы регулярными выражениями и локальным naive datetime, а не универсальным NLP parser. Порядок search patterns может менять смысл: например вчера проверяется до позавчера с substring search, yesterday до day before yesterday; reminder завтра до послезавтра. Это ограничения текущей реализации. Новая спецификация должна определить timezone, точность, неоднозначность и видимый результат распознавания.

## Scope и новая модель

Один ToolManager принадлежит общему ChatModel. set_char_context изменяет _char_id у разделяемых memory/reminder instances непосредственно перед run. Генерации сериализуются per character, не глобально. Между set context и чтением scope другой worker может поставить другого персонажа; local locks вокруг пары set/run не обнаружены. Это архитектурный риск смешения scope, не свидетельство фактического изменения чужих данных. Новая operation должна получать immutable request context явно, вместе с инструментальными аргументами.

Функциональные требования: каталог доступных tools и причины недоступности; валидируемые arguments; scope и request identity; budget/cancellation; bounded result; понятные no-results/failure outcomes; отдельная политика durable side effects и retries. Реализация parser, HTTP и scheduler может быть общей для новой Python/Rust архитектуры по смыслу, существующие managers переносить не требуется.

## Доказательства и пределы

Прочитаны ToolManager, base и lazy wrapper; шесть builtin tools; safe_eval арифметическая и общая policies; LegacyToolExecutor и openai/gemini dialects; ModelController registration/gates/_handle_tool_call и continuation; services/native_tool_calls; ChatModel construction/native request setup; protocol tool codecs по основным encode/decode/stream branches; UI tool settings. RAG explicit-call gate проверен отдельно. Реальных searches, чтения страниц, API calls, timer creation и model requests не было. Доказательства относятся к Python releases38172493; актуальность удалённых API и Rust alternatives исследуется отдельно.
