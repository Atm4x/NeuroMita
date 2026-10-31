# Отдельный prompt_editor: авторская работа и нодовый workflow

Статус: standalone tool, CONDITIONAL при отдельном запуске. Submodule HEAD35f25e8e57fc9756502dd43fd5d05fd21567e3ec перепроверен. Main core creation/integration witness не найден прежним и текущим поиском. PySide6/QDarkTheme этого приложения не обязательная зависимость основного runtime. Выбор GUI framework не исследуется.

## Сценарии и сохранение

Основной редактор даёт дерево prompt files, tabs, чтение/редактирование/save, выбор prompt root, config/variables, syntax diagnostics и composition preview. Это authoring, не исполнение production turn. Отдельное окно nodes открывается из Tools/Ctrl+Shift+N только для активного .script; initial text берётся из текущего editor buffer. Apply в node window заменяет buffer в основной вкладке; **не сохраняет автоматически файл**. Save in node window показывает отдельный filesystem picker и пишет export text. Model generation/Unity/worker ни этот Apply, ни Save не запускают.

Graph — визуализация собственного AST: SET/SET LOCAL, LOG, ADD_SYSTEM_INFO, RETURN, IF/ELSEIF/ELSE/ENDIF. Inspector редактирует выражения и ветви, поддерживает add/reorder условий и toggle ELSE, file snippets LOAD для RETURN. Scene предоставляет selection, pan/zoom, node position/color, connections. Connect меняет порядок/parent body AST; это не произвольный циклический workflow engine: self/ancestor cycles запрещаются. START задаёт начало последовательности, RETURN завершает выполнение.

Text→graph вызывает parse_script и показывает errors, но получает partial AST. Graph→text вызывает generate_script, сохраняющий только поддержанные node types; comments/исходное форматирование не являются lossless representation. Нельзя считать граф универсальным редактором всех текущих runtime DSL instructions.

## Выполнение preview

Run workflow повторно парсит buffer, создаёт отдельный DslAstRunner и local path resolver, получает initial vars (external provider, variables dock, config/default fallback), исполняет AST и показывает final text/sys infos/logs/before-after vars/per-node errors и exec trace. Узлы получают preview, IF — selected branch/значения переменных, graph — подсветку выполненного пути; double click открывает полный текст. Clear previews очищает отображение, не persistent character history.

Runner хранит собственные dictionaries и использует Python eval с ограниченным набором globals; он не тот же safe-AST engine, что current core DSL. SET изменяет preview vars, ADD_SYSTEM_INFO собирает локальные sys messages, LOAD читает author files. Успех preview не доказывает production context/effect parity, и его нельзя объявлять boundary для произвольного недоверенного Python expression. Реальный Character/DB/seed/graph side effects current core этим tool не проверяются.

Позиции/цвета/START хранятся в sidecar `<script>.meta.json`, fallback — Metas/default.meta.json. Debounced save600ms и explicit save отдельно от script content; ключ строится по node signature+occurrence, не durable runtime node identity. Clear meta с подтверждением удаляет metadata и очищает layout/color state, не .script. Ошибки read/save показываются/логируются; atomic persistence в этих путях не реализована.

## Проверенный предел и незавершённые действия

Изолированная проверка Python-B загрузила только parser/codegen submodule, без Qt, app bootstrap, file LOAD или runner execution. Вход `SET x = 1`, `RUN "helper.script"`, `RETURN "ok"`: parser вернул Unknown DSL command RUN, regenerated output содержит SET/RETURN, но не RUN. Assertions exit0. Это подтверждает **подмножество DSL и небезусловный round-trip**, а не общий тест редактора.

Create/Delete actions присутствуют в UI, но вызванные `NodeGraphController.insert_after`/`delete_node` не найдены как методы текущего controller source. Их successful outcomes поэтому **не подтверждены**; не объявлять работающий node CRUD только по кнопкам. Классы не исправлялись, GUI не запускался. Painter/drag rendering и все malformed expression/file cases не E2E-tested.

Предметная потребность для будущего продукта: author packs, видеть diagnostics/expanded context и понимать изменения состояния. Обязательность отдельного node editor, его расширение до полного DSL или поддержка именно этого .meta формата — продуктовые решения после аудита, не автоматически core parity. Сохраняем доказанные authoring сценарии, не навязываем Python AST/PySide6 новой архитектуре.

Источники: main.py; ui/main_window._open_node_editor231–260; ui/node_graph_window целиком; editor_widget construction/text/metadata/connection/run/vars paths; controller parent/connection/trace methods; inspector conditions/snippets; graph_scene pan/zoom/keyboard; logic/dsl_ast, dsl_parser, dsl_codegen; dsl_runner run/SET/IF/RETURN/eval. Поиск production callers в основном src и controller method definitions — read-only.
