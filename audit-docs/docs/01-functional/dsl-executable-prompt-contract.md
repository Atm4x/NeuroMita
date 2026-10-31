# DSL как исполняемый слой формирования промптов

**Статус:** `ACTIVE` для локального `DslInterpreter`, `CONDITIONAL` для конкретных пользовательских сценариев/скриптов, `UNRESOLVED` для удалённого `RemotePathResolver` как production backend. **Capabilities:** `CAP-DSL-EXEC-001—007`. **Предмет:** функциональные возможности и наблюдаемые контракты, не перенос Python-парсера один-в-один.

## Назначение и место в живом приложении

Перед LLM-запросом приложение формирует для выбранного персонажа набор инструкций из пользовательского prompt pack: основной шаблон, включения, переменные состояния, условные ветви, статические и volatile-context блоки. **DSL — не просто формат `.txt`: скрипт способен записать переменные персонажа, создать записи памяти/острова и защищённые связи графа.** Поэтому формирование промпта имеет как текстовые результаты, так и возможные побочные эффекты.

Прямой production-путь: `Character` создаёт `DslInterpreter` через `create_dsl_interpreter()` и `LocalPathResolver` (`src/characters/character.py:165-174`, `src/managers/dsl_manager.py:2-10`). `PromptController._build_system_messages()` выбирает файл, создаёт request-scoped capability-переменные и вызывает `process_main_template` (`src/controllers/prompt_controller.py:400-485`). Игровые `ChessGame` и `SeaBattleGame` также вызывают `process_file` для `_CommonPrompts/{game_id}.system` при получении game-state prompt (`src/modules/{Chess,SeaBattle}/*_instance.py`).

## Контракт чтения ресурсов / граница prompt pack

`LocalPathResolver` принимает два корня: общий `prompts_root` и вложенный каталог данных персонажа. Входные относительные пути:

| Форма | Относительно какого места | Source |
|---|---|---|
| `_CommonPrompts/…`, `_CommonScripts/…` | общего корня prompt pack | `src/DSL/path_resolver.py:111-114` |
| `./…` и `../…` | текущего файла/скрипта из context stack | `src/DSL/path_resolver.py:115-121` |
| прочий `relative/path` | каталога персонажа | `src/DSL/path_resolver.py:123` |

Путь нормализуется и проверяется на нахождение внутри глобального корня; текст загружается UTF-8 и обрезается справа (`src/DSL/path_resolver.py:92-152`). Путь выхода через symlink отдельно не проверялся; не считать файловую песочницу доказанной для всех Windows/filesystem вариантов. `RemotePathResolver` определён в том же файле (`154-236`), но production construction в просмотренных источниках использует **локальный** resolver; удалённое чтение не следует включать в обязательную первую Rust-версию без доказательства достижимости.

Поддерживаемые file categories: `.script` и `.system` обрабатываются как DSL, `.txt` — как текстовый шаблон с nested includes и `[{variable}]` подстановкой (`src/DSL/dsl_engine.py:931-1004`). Основной шаблон перечисляет включения `[<path>]`; с префиксом `[<@ path>]` документ отправляется в актуальный volatile-context (`856-922`).

## Исполняемые конструкции

| Семейство | Семантика/выход | Источник |
|---|---|---|
| `IF / ELSEIF / ELSE / ENDIF` | Условные ветви, вложенный стек `if_stack`; невыполняемые ветви пропускаются | `src/DSL/dsl_engine.py:422-485` |
| `SET name = expr` | Обновляет персонажную переменную через `character.set_variable`, если имя не объявлено локальным | `491-527` |
| `SET LOCAL name = expr` | Временная переменная интерпретатора; не является persistent character field | `499-525` |
| `ADD_SYSTEM_INFO` | Добавляет текст к отдельным системным сведениям `dsl_system_infos` | `529-545` |
| `ADD_CONTEXT_INFO` | Добавляет текст к volatile-сообщениям, ближе к запросу | `529-545`, `src/controllers/prompt_controller.py:528-533` |
| `RETURN expr/LOAD…` | Возвращает отрендеренный фрагмент; поддерживает `LOAD`, `LOAD_REL` и tagged section | `558-595` |
| `RUN script` | Запускает вложенный файл для его эффектов; отдельный возвращённый текст здесь не включается в результат родителя | `666-674` |
| `SEED_MEMORY`, `SEED_RAG_MEMORY` | Инициализация long-term/только-индексируемого факта, optional entities, skip-if-exists для первого варианта | `597-626` |
| `SEED_ISLAND` | Инициализация типа острова памяти | `628-638` |
| `LINK_ENTITIES` | Создание protected entities и relation при доступном RAG и `RAG_ENABLED` | `640-664` |
| `LOG` | Диагностическое выражение, не часть результата LLM | `548-556` |

Выражения обрабатывает `core.safe_eval.safe_eval_expression` с явным белым списком функций (`str/int/float/len/round/abs/min/max/random`), объединённым scope `character.variables`, `app_vars`, prompt-feature declarations, local variables (`src/DSL/dsl_engine.py:217-306`). Неизвестные идентификаторы могут автоматически получить локальное `None` (до 10 добавлений); для сложения строки с числом есть попытка повторить вычисление с преобразованием primitive values в строки. Это **фактически наблюдаемая совместимость DSL**, но не необходимость копировать Python error recovery.

Обычные вложенные ссылки `[<file.script>]` разворачиваются не более 10 проходов, невозможность завершить развёртывание оставляет диагностические маркеры (`752-802`). `LOAD TAG FROM …` читает содержимое между `[#TAG]…[/TAG]` (`830-854`); `LOAD` внутри выражений разворачивается перед safe evaluator (`323-376`). Текущие `{{INSERT}}` хранятся в интерпретаторе (`804-820`), однако `set_insert/_apply_inserts` не имеют подтверждённого внешнего вызова по выполненному поиску; **не** классифицировать их как действующий пользовательский API без runtime evidence.

## Система prompt features и граница cached/volatile

Шапка template содержит declarations `support_intents` (по умолчанию true) и `behavior_state`; `feature_overrides` может изменить значения только для текущего prompt-build (`src/DSL/dsl_engine.py:890-899`). `PromptController` переопределяет `support_intents=false` для react-level 1; sparse-response feature определяется request capability (`src/controllers/prompt_controller.py:467-478`). Сами prompt features живут в интерпретаторе, а не в сохранённых переменных персонажа.

В выходном message set `blocks` классифицируются на stable и volatile; список tools публикуется отдельным static system block, generated sparse contract — отдельным, оперативная память, islands/reminders и `ADD_CONTEXT_INFO` — отдельными volatile messages (`src/controllers/prompt_controller.py:489-551`). В режиме `separate_prompts` содержимое может разбиваться на несколько системных сообщений. Это значимый контракт **порядка/происхождения** контекста, не обязанность копировать Python классы.

## Состояние, жизненный цикл и пограничные случаи

- `process_main_template` очищает previous `prompt_features` и `context_infos`, но не откатывает побочные эффекты вызванных скриптов (`src/DSL/dsl_engine.py:856-929`).
- `process_script` при запуске очищает локальные переменные и контекст текущего блока, затем выполняет правила по порядку. Для вложенных вызовов используется тот же экземпляр интерпретатора: область видимости локальных переменных между вложенными скриптами требует явного parity-теста (`378-408`, `666-674`).
- Ошибки отдельных script/file/main-template нередко превращаются в **текстовые диагностические маркеры**, а не выбрасываются наружу (`684-700`, `923-972`). Откат созданных фактов памяти после ошибки не обеспечивается этой границей.
- Наличие исходника `RemotePathResolver` не означает его активное использование. Наличие syntactic `RUN` не означает, что любой путь разрешён: ограничение идёт через resolver.
- Выбор `react_template.txt` имеет fallback на общий `Common/react_template.txt`, затем основной шаблон персонажа (`src/controllers/prompt_controller.py:443-466`).

## Функциональные требования для нового продукта (без архитектурного решения)

- `REQ-DSL-EXEC-001`: набор prompt-pack ресурсов выбирается по персонажу, сценарию и типу события; вложенные ссылки разрешаются относительно однозначного корня.
- `REQ-DSL-EXEC-002`: логика условий, вычислений и подстановок предоставляет персонажу актуальные переменные без исполнения произвольного системного кода.
- `REQ-DSL-EXEC-003`: различаются persistent character fields, локальные скриптовые значения и transient prompt features.
- `REQ-DSL-EXEC-004`: static, volatile и отдельные dynamically generated sections сохраняют ordering/provenance перед LLM-запросом.
- `REQ-DSL-EXEC-005`: функция инициализации memory/RAG/islands/graph из prompt pack сохраняет смысл side effects и их условия доступности, независимо от выбранного DSL.
- `REQ-DSL-EXEC-006`: неразрешённый путь/ошибка выражения не должны выдавать непроверенный текст за корректную инструкцию; точное UX-поведение выбирается при проектировании.
- `REQ-DSL-EXEC-007`: сериализованный prompt-build со всеми side effects проверяется на повторяемость, независимость персонажей и смену настроек.

## Проверка паритета (пока не выполнена)

Минимальная fixture matrix: вложенный `IF` и unknown variable; `SET LOCAL` и persistent SET; `ADD_CONTEXT_INFO` рядом с пользовательским сообщением; `@include` + обычный include; tagged section; seed memory/island/graph при RAG on/off; malformed include + неполный шаблон; два персонажа/два поколения prompt; react override и supported-intents gate. Эти тесты **предложены**, а не объявлены пройденными.

**Неясности:** полный inventory реально поставляемых `.script/.system/.postscript` отсутствует в переданном snapshot; они могут храниться в отдельных prompt packs. Совместимость пользовательских авторских пакетов необходимо исследовать отдельно по образцам. Не объявлять DSL необязательным, поскольку production path подтверждён, но не требовать сохранения его синтаксиса без отдельного требования backward compatibility.
