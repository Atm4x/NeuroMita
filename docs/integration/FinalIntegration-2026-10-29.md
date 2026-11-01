# Python для общей Unity-ветки — 29 октября 2026

Ветка: `codex/final-integration-2026-10-29`.
Согласованная Unity: `VinerX/NeuroMita-Unity`, одноимённая ветка, `ff5f4626b`.
Проверенная Python-основа до добавления интеграционных тестов: `081efdb1`.
База Python: `origin/releases`, `38172493`.

Объём по прямому уточнению пользователя: только изменения под собранную
Unity-ветку. Отдельные экспериментальные направления Python не объединяются.

## Источники

| Функция | Источник | Перенос |
| --- | --- | --- |
| Desktop | `codex/desktop-mode-context` / `51e73769` | Merge `7e541532` |
| Совместный Timeline | `codex/unified-world-timeline-20261027` / `8d5bcdd1` | Merge `3f33c30f` |
| Картриджи | `a2a63a37` | Cherry-pick `02d5f8f1` |
| 2D-личность | `eb78e886` | Cherry-pick `9ce72331` |
| 2D transform | `a0f268f3` | Cherry-pick `eeb6d2c8` |
| 2D prompt | `90996946` | Cherry-pick `7595c1b1` |
| Редактируемые 2D-промпты | `c50d8e19` | Cherry-pick `7b4b36ed` |
| Общий pipeline 2D | `008056ed` | Cherry-pick `081efdb1` |

Desktop и Timeline включены с историей; releases — их предок итоговой ветки.
Картриджи и 2D перенесены конкретными коммитами с `-x`: их старая общая база
содержала ONNX-коммит `a6593678`, который намеренно исключён.
Проверено, что отдельные вершины OpenCode и RAG/ONNX не включены.

Изменения RAG, шахмат и Sea Battle внутри Timeline сохранены: это участники
checkpoint/restore и защита от поздних результатов, входящие в парный протокол.
Существующая релизная функциональность API/GUI остаётся унаследованной из releases.
Старый WIP player-activity-time-awareness отдельно не переносился: это не
необходимая Python-зависимость собранных Unity-функций.
GOAP-доставка в Unity остаётся C# API/debug-возможностью; слияние Python не
создаёт отсутствующие LLM-команды и не расширяет поддерживаемую автономность.

## Конфликты и архитектура

В реестре socket actions сохранены оба обработчика: desktop_state и timeline.
Hello также объявляет версии cartridge и novel.

HistoryController после переноса общей 2D-модели проверяет runtime profile:
картриджи и 2D не запускают background memory; обычные персонажи используют
Timeline-сжатие и возвращаются до старого фонового обработчика. Это проверено
отдельным параметризованным тестом.

Сохранены barrier и транзакционный протокол Timeline: Python владеет identity
и своими снимками, Unity — физическим снимком. Состояния prepare/commit/ack и
recovery не заменены простой загрузкой истории.

## Проверки

- 186 pytest-тестов Timeline, UnitySessions, restore, outputs, RAG snapshots,
  мини-игр, 2D и картриджей: passed, 0 failed, 0 skipped; дополнительно 128 subtests passed.
- 65 тестов общих socket routes, capabilities/history, ASR, reaction provenance
  и headless runtime: passed, 0 failed, 0 skipped.
- Итого 251 обычный тест и 128 subtests. Первый JUnit XML учитывает subtests
  в tests=314; это не 314 отдельных pytest-функций.
- 113 изменённых/новых Python-файлов успешно разобраны через ast.parse.
- Новые изменения проходят git diff --check.

GUI-процессы, необходимые тестам snapshot, работали с QT_QPA_PLATFORM=offscreen.
Один DeprecationWarning относится к pygame/pkg_resources; падений нет.

Отчёты: [основной](FinalIntegration-2026-10-29-tests.xml),
[протоколы](FinalIntegration-2026-10-29-protocol-tests.xml).
Новые регрессионные проверки: tests/test_final_unity_integration.py.

Это проверки Python и контролируемых участников. Совместный запуск этой пары
веток с живым Unity, реальным LLM, голосом и desktop overlay не выполнялся.
Полный набор тестов приложения, упаковка PythonBuildDev и релиз не выполнялись.

## Дальнейшее ревью

Сравнение: `git diff origin/releases...codex/final-integration-2026-10-29`.
Отдельно смотреть пересечения MainController, HistoryController,
PromptController, ModelController и game_connections между Desktop, Timeline и 2D.
Проверить startup/shutdown, reconnect, смену мира во время генерации,
восстановление task/audio и изоляцию истории виртуальных персонажей.
После статического аудита нужна совместная проверка Unity ↔ Python.

## Локальное состояние

Новый worktree не создавался. До переключения основная ветка была
codex/desktop-mode-context. Локальная правка Prompts/Mila/Main/main.txt
сохранена во вложенном репозитории prompt_editor в stash
`6d868ee4e3f9c3a739ca8bd41cfcdd3de12483d4`:
`Before paired Python integration 2026-10-29: local Mila prompt`.
Stash не применялся к интеграции и не удалялся. Подмодуль и пользовательские
настройки, истории, модели и сборки не обновлялись.

Ветка подготовлена локально. Разрешение на отправку Unity в VinerX/NeuroMita-Unity
не используется как разрешение на публикацию Python в Atm4x/NeuroMita.
