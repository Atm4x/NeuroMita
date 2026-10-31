# Шахматы и Морской бой: независимые игровые runtime и реакции персонажа

**Статус:** `CONDITIONAL` — обе игры зарегистрированы в production `get_available_games`, запуск зависит от настроек; внешний шахматный engine также зависит от файлов и загрузки. **Capabilities:** `CAP-MINIGAME-DETAIL-001—008`. Здесь описаны **игровые сценарии**, а не Qt widget hierarchy.

## Общий функциональный контракт

`GameManager` привязан к персонажу, хранит не более одного `active_game`, регистрирует `chess` и `seabattle` через `modules/available_games.py` (`src/managers/game_manager.py:11-16`). Запрос `StartGame`/ручной запуск проверяет `ENABLE_GAMES`, `GAME_CONNECTED` + `ALLOW_GAMES_WHEN_CONNECTED`, персональный `ENABLE_GAME_CHESS`/`ENABLE_GAME_SEABATTLE` (`47-70`). Одна запущенная игра останавливается перед следующей (`72-111`). При ручном выборе Desktop после успешного запуска отправляется **видимая** in-character реакция `ChatAPI.react` без повторного создания игры (`113-152`); та же action может быть инициирована LLM и тогда идёт обычный путь `start_game`.

`GameInterface` определяет `start`, `stop`, `cleanup`, `get_state_prompt`, legacy text tags, structured commands и запрос реакции у host (`src/modules/game_interface.py:1-57`). Host проверяет, что событие пришло от текущей активной игры, затем вызывает `ChatAPI.react` с `character_id` владельца, visible flag и sender=`Player` (`src/managers/game_manager.py:154-173`). Следовательно gameplay event ≠ непосредственно LLM request, а **потребность инициировать реакцию** в существующей admission-цепочке. При недоступном входе событие может не превратиться в ответ.

`MiniGameSessionRegistry` ведёт read-only краткое публичное состояние игры по character ID — owner name, game ID, last public event (`src/managers/mini_game_session_registry.py:8-72`). Это отдельная проекция, не authoritative board. В игровых обработчиках `update_public_event()` используется для сообщения о действиях игрока; `cleanup()` удаляет регистрацию.

### Формат запуска

`GameManager._parse_id_string` принимает `chess/easy|medium|hard/auto/cheat/resign/white|black` (независимые segments) и `seabattle/resign`; `Chess` difficulty mapping `1100/1500/1900` (`src/managers/game_manager.py:18-45`). Принятие game ID и запуск процесса разделены: `start_game` возвращает true после успешной постановки игры в статус active, если `playingGame` остался true (`72-111`).

## Chess — user workflow, state и эффект диалога

1. `ChessGame.start()` задаёт ELO, цвет игрока, `auto/cheat` и переменные `playingGame`, `game_id`, `GAME_CHESS_IS_AUTO/CHEAT`. Поднимает **отдельный `multiprocessing.Process`** с Qt board, command/state/reaction queues и listener thread в core (`src/modules/Chess/game_instance.py:31-75`). Поле `gui_thread` исторически названо thread, но фактически содержит Process.
2. Пользователь выбирает фигуру, ход, превращение пешки, опции автопоиска/читов и завершение в GUI (`src/modules/Chess/chess_board.py:273-488,684-842`). Qt GUI отправляет ходы/закрытие в reaction queue; `ChessGame` преобразует `player_chess_move`, `manual_mita_turn`, `player_game_over`, `player_game_closed` в запросы `ChatAPI.react` (`src/modules/Chess/game_instance.py:143-239`).
3. Запрошенные LLM commands: `RequestBestChessMove`, `MakeChessMoveAsLLM,<uci>`, `ChangeChessDifficulty,<level>`, включение/отключение auto и cheats, а также cheat-операции (`src/modules/Chess/game_instance.py:267-346`). Обработчик отправляет command dict в игровой процесс. Существуют legacy text tags `ChangeChessDifficulty`, `RequestBestChessMove!`, `MakeChessMoveAsLLM`, которые следует классифицировать как backward compatibility, а не второй игровой механизм (`240-265`).
4. Chess GUI/engine controller валидирует ход/turn, взаимодействует с `python-chess` и движком Lc0/Maia; часть бинарников и weights при отсутствии устанавливается отдельно (`src/modules/Chess/engine_handler.py:37-229,229-335,388-545,638-749`). **Наличие chess gameplay в Rust не означает перенос AI inference**: движок Lc0 — отдельный внешний binary, допустимый как game dependency.
5. `get_state_prompt()` потребляет последние state snapshots из process queue; при отсутствии новой записи использует кэш последнего завершённого board и посылает `get_state` при пустом состоянии. Переменные включают FEN, ASCII board, ELO, ходы в SAN/UCI, legal moves, цвет/очередь, ошибки и outcome; затем исполняется `_CommonPrompts/chess.system` (`src/modules/Chess/game_instance.py:379-476`). Персонаж получает не «всё содержимое GUI», а **сериализованную игровую проекцию**.
6. Завершение/закрытие/сбой сбрасывают `playingGame`, game_id, queues, публичный registry и ссылку на active game (`97-141,379-425`). Наличие отдельной game GUI process определяет отдельный failure boundary, не является обязательным требованием организации Rust.

## Sea Battle — user workflow, state и эффект диалога

1. `SeaBattleGame.start` запускает отдельный Qt process и три очереди; per-character флаги `playingGame/game_id` имеют тот же смысл, что в шахматах (`src/modules/SeaBattle/seabattle_instance.py:27-64`).
2. Игровой движок содержит **10×10 поле**, расстановку кораблей, phase placement/battle/game_over, проверку координат, пересчёт попаданий/промахов и представления досок **по ролям** (`src/modules/SeaBattle/seabattle_logic.py:20-113,115-269`). Игрок в GUI выбирает размер/ориентацию корабля, расставляет корабли, стреляет по противнику и может включать/выключать автоматическую реакцию Миты для матча (`src/modules/SeaBattle/seabattle_gui.py:214-310,382-492`).
3. Event queue поддерживает `player_target_selected`, `mita_target_hit`, `manual_mita_turn`, `player_placement_completed`, `player_game_over`, `player_game_closed`, `game_closed`; listener запрашивает соответствующие видимые реакции Core с инструкциями следующего действия (`src/modules/SeaBattle/seabattle_instance.py:119-235`). UI checkbox подавляет автоматические реакции для данной партии, но глобальный gate реакций остаётся отдельным.
4. Для LLM доступны `PlaceShipsRandomly`, `PlaceShip,<coord>,<length>,<H|V>`, `MakeMove,<coord>`; legacy tags `PlaceShip`, `PlaceShipsRandomly`, `MakeMove` конвертируются в те же backend-команды (`src/modules/SeaBattle/seabattle_instance.py:235-297`). Состояния команд/ошибок приходят обратно в state queue; **requested shot** и **accepted gameplay move** различаются.
5. `get_state_prompt` разделяет собственное поле Миты и её ограниченный обзор поля игрока, фазы, чей ход, победителя, историю выстрелов, раненые корабли и планируемые цели; затем использует `_CommonPrompts/seabattle.system` (`src/modules/SeaBattle/seabattle_instance.py:299-391`). Это существенный knowledge-boundary: модель не должна видеть скрытые клетки противоположной стороны.

## Общие состояния/инварианты продукта

| Состояние | Переход | Следствие |
|---|---|---|
| `Unavailable` | games disabled / Unity gate / game ID unsupported | не создаётся игровой runtime |
| `Starting` | допустимый StartGame | process + queue созданы, board может быть ещё не готов |
| `Running` | получена начальная проекция | UI принимает ходы, LLM реагирует с отдельным request admission |
| `Awaiting move/state` | action отправлена в child process | эффект подтверждается state snapshot/ошибкой, не фактом отправки |
| `Game over` | game engine сообщает outcome | итоговая реакция, дальнейшие ходы не выполняются |
| `Stopped/Closed/Failed` | shutdown/GUI close/critical process failure | cleanup, сброс per-character state и registry |

Объект `MiniGamePublicSession` допускает снимки **нескольких персонажей**, но отдельный `GameManager` допускает только одну активную игру данного персонажа (`src/managers/mini_game_session_registry.py:16-66`, `src/managers/game_manager.py:13-16`). Идентичность нельзя сводить только к `game_id`.

## Functional parity requirements

- `REQ-MINIGAME-DETAIL-001`: два отдельные gameplay rule sets — Chess и Sea Battle — с валидными ходами, фазами и итогом.
- `REQ-MINIGAME-DETAIL-002`: пользовательские запросы, LLM-команды и игровые события имеют общий scope персонажа, но различные initiating actors.
- `REQ-MINIGAME-DETAIL-003`: LLM получает роль-ограниченную, согласованную с игрой проекцию, включая «state not ready» и ошибки.
- `REQ-MINIGAME-DETAIL-004`: доступность игр определяется настройками и текущим режимом работы с Unity.
- `REQ-MINIGAME-DETAIL-005`: lifecycle игры и исходящие реакции не оставляют публичный session snapshot после остановки.
- `REQ-MINIGAME-DETAIL-006`: включение автоматических реакций контролируется игроком и общими policy gates; автоматическая реакция — отдельное admission-событие.
- `REQ-MINIGAME-DETAIL-007`: шахматный движок и его weights являются optional компонентами, а не обязательным Python AI runtime Core.
- `REQ-MINIGAME-DETAIL-008`: сохранена семантика недоступного/запаздывающего state после process start, без приписывания действиям гарантии выполнения.

## Тестовый минимум для будущего parity review (не выполнен)

Chess: белые/чёрные, 3 сложности, legal/illegal promotion, player move→reaction→engine move→snapshot, close during inference, engine asset absent, auto/cheat gates. Sea Battle: placement collision/forbidden adjacency, скрытое поле, move out of turn, disabled automatic reactions, miss/hit/sunk/game over, close while LLM pending. Cross-game: second game replaces first, two characters simultaneously, clear registry after failure, player-start reaction vs LLM-start no duplication.

**Ограничение исследования:** типовые runtime пути подтверждены кодом, но GUI/engine процессы и внешняя установка Lc0 не запускались; не заявлять испытание поведения человека в окне или точный реальный engine throughput. Часть отдельных cheat-команд и всех кнопок шахматного GUI требует последующего exhaustive map, без ухода в поиск ошибок.
