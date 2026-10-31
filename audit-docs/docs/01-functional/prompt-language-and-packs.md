# Авторские наборы промптов, DSL и Post-DSL

**Capabilities:** CAP-PROMPT-002—006. **Статус:** ACTIVE для runtime DSL и выбора pack; CONDITIONAL для download/правил конкретного pack; отдельный prompt_editor — самостоятельный инструмент с неподтверждённой интеграцией в core. Основная сборка контекста описана в [prompt-system](prompt-system.md).

## Что умеет пользователь/автор

| ID | Возможность | Подтверждённое поведение |
|---|---|---|
| CAP-PROMPT-002 | Выбрать набор конкретного персонажа, посмотреть metadata, открыть его каталог, перечитать данные | Каталог Prompts/{char_id}/{set_name}, settings selection и Character reload |
| CAP-PROMPT-003 | Собрать контекст из reusable текстов и условных скриптов | Runtime DslInterpreter, файлы .txt/.script/.system, includes/sections/variables/features |
| CAP-PROMPT-004 | Задать начальные знания, память и связи из content pack | SEED_MEMORY / SEED_RAG_MEMORY / SEED_ISLAND / LINK_ENTITIES и RUN вложенных scripts |
| CAP-PROMPT-005 | Преобразовать ответ и custom field effects авторскими правилами | PostScripts/main_rules.postscript: TEXT/REGEX/FIELD rules, замена/удаление и SET |
| CAP-PROMPT-006 | Скачать и заменить наборы, перечитать персонажей | PromptDownloader → staged extraction → directory replacement → RELOAD_ALL_DATA |

Новая система должна сначала решить, какие из этих возможностей нужны автору и игроку. Текстовый синтаксис, side effects при prompt build и структура интерпретатора не являются обязательной архитектурой переписывания.

## Content packs и выбор

Каталог содержит варианты per character и info.json. Metadata читается UTF-8 с fallback cp1251; отсутствие/ошибка возвращает пустую структуру, часть ошибок показывает QMessageBox. GUI показывает варианты, сохраняет setting и запрашивает reload; смена набора не тождественна смене активного персонажа песочницы. Есть отдельные кнопки применения и открытия папки. Paths GUI listing/open частично захардкожены как Prompts, в то время как core paths и Character знают NEUROMITA_PROMPTS_DIR; пользовательский перенос prompts root требует отдельной согласованной модели.

В исходном checkout корневого Prompts нет; release assets находятся в extra/Prompts. build.py default copy maps extra/Prompts → output/Prompts. Поэтому отсутствие runtime каталога в source checkout не означает отсутствие функционала или пустой релиз. extra/LegacyPrompts и собственные prompt_editor/Prompts не считать текущими shipped packs.

prompt_catalogue_manager также содержит copy/create/delete/write helpers, но production callsites copy/create/delete по src не найдены. Наличие этих функций не доказывает доступную кнопку CRUD. Активны listing/read и выбор из GUI; редактор пользовательских персонажей/pack operations проверяется отдельно в GUI-проходе.

## Runtime язык: данные, условия, композиция

Главный template выбирает top-level includes [<path>] в stable blocks и [<@ path>] в volatile context. Свободный текст вне includes в process_main_template в blocks не добавляется. Объявления support_intents и behavior_state читаются regex, затем request-local feature overrides имеют приоритет. support_intents default True. Features/context infos очищаются на каждом main build.

.txt поддерживает nested includes и подстановку [{name}] из features/character.variables/app_vars; неизвестная переменная даёт пустую строку. Неизвестные locals из .script не становятся автоматически .txt variables. Section markers [#NAME]...[/NAME] позволяют загрузить часть файла. Полная LOAD-ветвь и tag LOAD имеют разные preprocessing steps; это поведение языка, которое нужно специфицировать, если совместимость content станет требованием.

Script commands: IF/ELSEIF/ELSE/ENDIF; SET и SET LOCAL; ADD_SYSTEM_INFO и ADD_CONTEXT_INFO; LOG; RETURN с expression/LOAD/LOAD_REL/tag; RUN; seed/link commands. Тройные кавычки объединяют многострочный expression. ADD_SYSTEM_INFO отдаёт отдельный static channel, ADD_CONTEXT_INFO — поздний volatile channel. RETURN заканчивает script; RUN игнорирует returned text, сохраняя side effects и дополнительные infos.

Expressions вычисляет собственный AST evaluator на stdlib ast. Он поддерживает literals/collections, arithmetic, boolean short circuit, comparisons, conditional expression, f-strings, allowlisted direct calls str/int/float/len/round/abs/max/min/random. Attribute access, subscription, lambda/comprehension, arbitrary calls запрещены. random() даёт float, random(int,int) — включительные границы; bool/fractional/обратные границы запрещены. Это собственная логика, не зависимость от полноценного Python exec.

Scope expression: character variables → app variables → features → local variables, более поздние перекрывают ранние. UnknownName может автоматически получить None в locals, до10 fills; отдельная ошибка concatenation вызывает повтор с primitive values, преобразованными в str. SET persistent обращается к Character.set_variable; SET LOCAL не пишет persistent state. process_script очищает общие interpreter locals при каждом вызове, включая nested scripts; отдельного frame stack locals нет.

## Память и эффекты во время сборки

SEED_MEMORY добавляет active memory с skip_if_exists; SEED_RAG_MEMORY задаёт retrievable knowledge без постоянного active block; SEED_ISLAND — island type/content. ENTITIES прикрепляет перечисленные имена. LINK_ENTITIES создаёт protected graph entities/relation при включённом RAG; failure логируется и игнорируется. Это записи в данные во время построения prompt, а не чистое форматирование текста. В shipped extra/Prompts init scripts действительно RUN common world knowledge и character seeds. Отдельные flags управляют персонажными seeds и каноническими сведениями.

Post-DSL загружается при создании/reload Character из PostScripts/main_rules.postscript. RULE содержит TEXT substring, REGEX с capture names либо FIELD name; ACTIONS допускает SET/SET LOCAL/LOG, REMOVE_MATCH и REPLACE_MATCH WITH expression. Rules идут по порядку над изменённым предыдущими правилами текстом. SET может менять persistent variables; errors action логируются и обработка продолжается. На each text-processing cycle locals сбрасываются; structured response обрабатывает каждый segment отдельно, затем custom fields вызывают FIELD rules. Поэтому правило на текст может выполниться несколько раз за ответ и иметь эффекты независимо от видимой реплики.

Post expressions используют общий safe evaluator, дополнительные captures/field/default(). Реальное объединение eval_scope кладёт app_vars последними: комментарий про captures как наивысший приоритет не описывает все коллизии. DEBUG_DISPLAY задаёт отображаемые variables для debug projection персонажа.

## Ошибки, пути и preview

LocalPathResolver разрешает pack-relative paths, ./ и ../ по текущему context directory и common directories, проверяет lexical containment внутри prompts root. Это не проверенная sandbox boundary для arbitrary filesystem links: realpath/junction resolution в прочитанной проверке нет. RemotePathResolver содержит simulated content, production factory использует Local; удалённые runtime includes не подтверждены.

Ошибки DSL преимущественно возвращаются как текст [DSL ERROR ...]/[PY ERROR ...], часть уже выполненных SET/seed остаётся. Незакрытый IF в конце script даёт warning. MAX_RECURSION=10 ограничивает локальный include substitution loop, но не является доказанным общим budget всех рекурсивных RUN/process_file. Предварительный linter — отдельная developer utility: missing/cyclic includes, duplicate paragraphs, некоторые content warnings; runtime startup он не блокирует.

В core присутствуют set_insert/_apply_inserts для {{NAME}}, однако production вызов _apply_inserts в src не найден. README самостоятельного редактора описывает вставки; это не достаточное доказательство их работы в текущем core engine.

prompt_editor/main.py запускает отдельный PySide6/QDarkTheme app. Поиск core src/build references не нашёл запуска редактора из основного GUI. В нём подтверждены file tree/tabs/save, выбор prompts directory, variables panel/config save, syntax check, composition preview с before/after state, node script editor с AST/trace/previews. Он использует собственные models/logic engines; preview не является проверкой current core contract. Исследованы entry/menu/preview и runner contract; полный редактор/node graph ещё не исследован. PySide6 из этой подпрограммы нельзя автоматически добавлять к обязательным runtime зависимостям основного PyQt6 core.

Дополнение Pass13: [authoring/node workflow](../02-ui/prompt-editor-authoring-and-node-workflow.md) закрывает основные text↔graph/run/metadata/apply/save paths и фиксирует реальные ограничения DSL subset, round-trip и неподтверждённых Create/Delete outcomes. Ранее указанный пробел теперь относится к renderer/E2E и unsupported operations, а не отсутствию функционального описания node workflow.

## Обновление наборов

PromptDownloader по умолчанию берёт GitHub VinerX/NeuroMita branch main, независимо от текущей Python releases branch. Download limits128 MiB, expanded256 MiB/10000 files; spooled archive, HTTP connect10/read120 s, incremental cancellation. Extraction выбирает найденный Prompts prefix, запрещает symlink entries, проверяет containment и раскладывает только этот subtree в staging. Затем старый каталог переносится в Prompts_backup, staging становится активным; при exception пытается вернуть backup. Предыдущий backup удаляется перед заменой. Защиты от одновременных updater calls либо читающих pack files в этой функции не найдено; complete script-level consistency для live prompt build не обеспечивается одним directory rename.

ModelController запускает update на IO pool, при success публикует RELOAD_ALL_DATA и reload_prompts_success. Cancel event loader поддерживает, но этот caller его не передаёт. Ошибки превращаются в bool false/failed event; downloader сохраняет backup успешной предыдущей версии. Download не выполнялся во время аудита.

## Требования для проектирования с нуля

Версионированный content pack и preview должны иметь одинаковую семантику runtime; stable/volatile channels, source location diagnostics и итоговая projection должны быть наблюдаемы. Scope variables, чистые text operations и durable effects следует определить отдельно. Seeds требуют идемпотентности по identity/version, reload — явного state contract. Нужен общий execution budget и определённый outcome invalid pack, включая уже применённые эффекты. Актуальная библиотека parser/templating может быть выбрана после этой спецификации; наличие своего DSL не является доказательством незаменимости Python.

## Источники и пределы

Прочитаны src/DSL/dsl_engine и post_dsl_engine по всем execution methods, primitives, LocalPathResolver, factory и template helper; safe_eval; prompt_catalogue_manager; PromptDownloader; relevant Character/PromptController/GUI selection/reload paths. Shipped templates Crazy Default и Sleepy Lite, init scripts и common/structural examples проверены выборочно; все content packs не признаны семантически проверенными. build.py default copy mapping прочитан. prompt linter и editor читались по указанным branches; полного GUI QA нет. Никаких DSL scripts с настоящими memory effects, обновления файлов/наборов, запусков editor/build/app не выполнялось.
