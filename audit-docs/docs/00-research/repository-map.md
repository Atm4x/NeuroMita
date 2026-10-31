# Репозитории и рабочая ревизия

## Python

Ветка `releases`, HEAD `38172493fa0d1caf1a5225bc1c559f095f18bb7a`, совпадает с fetched `origin/releases`. Origin: `https://github.com/Atm4x/NeuroMita`.

На старте существует неотслеживаемый `src.zip`. `.pytest_cache` выдаёт отказ доступа при git status. Архив не распаковывался, кэш не менялся.

| Область | Наблюдаемое содержимое | Что ещё проверить |
|---|---|---|
| `src/startup`, `src/__main__.py` | Bootstrap, GUI/headless hosts, профилирование | Все дополнительные entrypoints |
| `scripts`, `build.py`, `launch.py` | Запуск дистрибутива, сборка, локальный запуск | Native launcher, payload и update handshake |
| `src/controllers`, `src/services`, `src/core` | Композиция и runtime contracts | Полный граф вызовов по областям |
| `src/domain`, `src/infrastructure`, `src/schemas` | Потенциальные модели и адаптеры | Реальная достижимость |
| `src/characters`, `src/managers`, `src/DSL`, `src/presets` | Персонажи, память, правила и шаблоны | Сценарии и совместимость данных |
| `src/game_connections`, `src/connetors` | Игровой транспорт и интеграции | Оба конца протоколов |
| `src/handlers` | LLM, audio и AI services | Граница core/inference |
| `src/ui`, `src/localization`, `src/styles` | Основной GUI | Все экраны, действия, состояния |
| `src/modules`, `src/web` | Дополнительные функции | Условия регистрации |
| `src/utils/Testing`, `tests` | Тесты поведения | Различать ожидание и проверенный результат |
| `assets`, `extra`, `docs`, `src/docs` | Ресурсы и документация | Что включается и используется в runtime |
| `Settings`, `Histories`, `Lib`, `Logs`, `temp`, `venv` | Локальные данные/окружения | Не считать содержимое функциональным исходником автоматически |
| `archive` | Исторические исходники | Использовать только как контекст при необходимости |

Submodule `prompt_editor`: URL `https://github.com/NeuroMita/NeuroMitaPromptEditor.git`, фактический HEAD и gitlink `35f25e8e57fc9756502dd43fd5d05fd21567e3ec`. Его PySide6-интерфейс — отдельная поверхность; достижимость из основного приложения пока не установлена.

## Unity

Локальная ветка `codex/card-game-portability-audit`, HEAD `e7c7ae428f77d3f6d714971ddcaf8256ffd21624`, дата коммита 2026-10-22. Есть изменения сцен, материалов, шрифтов, prefab и неотслеживаемые материалы/профили. Working tree не равен чистому коммиту.

Origin фактически `https://github.com/Atm4x/NeuroMita-Unity.git`, upstream — NeuroMita organization, отдельный remote `vinerx` — VinerX. Это отличается от единственного Unity URL в задании.

Выполнен `git fetch origin`, рабочие файлы не менялись. Origin текущей ветки обновился до `1e02a70c2`; `origin/releases` отсутствует. Существуют `origin/releases27092026`, `origin/releases4-fixes`, `origin/releases5` и локально известная `vinerx/releases`. Их актуальность/назначение ещё не установлены. Нельзя молча считать любую из них парой Python releases.

Unity submodule `Modules/TVModule`: `1c78ae5e452e3dea59c624c59bfa4bf47d219aff`. Статус использования ещё не проверен.

При сетевом проходе уточнено: fetched origin/codex/card-game-portability-audit=`1e02a70c2f4b1742df4ce39ae2a6da40763d7336` (2026-10-22 11:19 +03). Network scripts, Dialogue/Application и DialogueRuntimeContextBuffer идентичны local HEAD по git diff; эти области также не имеют working-tree diff. Remote origin/HEAD указывает на main=`c97872c5` от2026-06-26, то есть не на новейшую рабочую ветку; сравнивать с ним как с «актуальной версией» ошибочно. Локальная Unity ветка/dirty assets не менялись.

Локальный `AGENTS.md` требует перед аудитом анимаций игрока прочитать `Tools/PlayerAnimationConversion/README.md`, актуальный контекст — `Docs/Animation/README.md`. Анимации пока не исследованы.
