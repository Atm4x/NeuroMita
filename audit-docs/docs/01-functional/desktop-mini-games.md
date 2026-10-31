# Шахматы и морской бой в Python

**Capabilities:** CAP-GAME-001—004. **Статус:** CONDITIONAL, production registration подтверждена. Это самостоятельные desktop mini-games Python, не игровые системы Unity. available_games регистрирует chess и seabattle; каждый Character создаёт GameManager.

## Общие сценарии и ownership

Пользователь запускает игру из desktop settings, либо модель выдаёт start_game. Gates: ENABLE_GAMES, ENABLE_GAME_CHESS/SEABATTLE, и при подключённой Unity ALLOW_GAMES_WHEN_CONNECTED. Manual start явно разрешает владельца: если персонаж Sandbox отличается от игрового собеседника, предлагается выбор; выбранный игровой собеседник может стать Sandbox selection. Обычные gates сохраняются.

У каждого персонажа не более одной active_game; разные персонажи имеют отдельных managers. При попытке нового старта существующая игра останавливается до проверки имени/gates новой игры. Это текущее поведение, не требование новой системы. Старт устанавливает playingGame/game_id, создаёт отдельный PyQt6 GUI process, command/state/reaction multiprocessing queues и listener thread. Считается запущенным после process start и локальных variables, не после readiness окна/engine. GameManager проверяет, не очистил ли game себя при startup.

Реакции идут через GameHost → ChatAPI.react с зафиксированным owner character, обычным dialogue admission/history pipeline. Host отклоняет запрос от уже неактивного instance. Ручной запуск приглашает персонажа коротко отреагировать; IGNORE_GAME_REQUESTS подавляет это приглашение. Shared MiniGameSessionRegistry хранит только owner/game/последний публичный факт; не содержит hidden boards. Другие персонажи получают shared context, а не контроль чужой игры.

Core читает последнюю state projection из очереди, кеширует её при временно пустой queue, при первом чтении может ждать до0.25 s. Пока initial state нет — prompt сообщает, что окно открывается/синхронизируется, вместо заявления об отсутствии игры. Поля состояния переносятся в character variables и обрабатываются _CommonPrompts/{game}.system через DSL. Это не persisted match snapshot: продолжение партии после перезапуска в просмотренном pipeline не найдено.

## CAP-GAME-001: шахматная партия

Пользователь выбирает цвет/сложность при launch parameters, на доске выделяет фигуру и legal destinations, делает ход мышью; превращение пешки открывает выбор q/r/b/n с отменой. Окно даёт новую игру белыми/чёрными, автоматическую реакцию Миты либо manual request хода. Game over сообщает outcome; обработаны restart/close choices при поражении игрока. Закрытие пользователем отличается от программного stop: первое может вызвать реплику персонажа, второе не должно её имитировать.

PureBoardLogic использует python-chess: Board/FEN, legal UCI moves, SAN, история ходов со special events, ASCII board. Окончание проверяет mate/stalemate/material/75 moves/fivefold repetition и can_claim_draw. Последнее автоматически считается окончанием в этом wrapper, хотя семантику заявления ничьей для новой игры нужно выбрать явно. Prompt получает цвет/очередь, FEN/board, recent history, legal short list, promotion availability, last move, outcome и errors.

По принятому player move при включённой реакции запрашивается обычный LLM turn с RequestBestChessMove; manual button запрашивает такой же ход при отключённой автоматической реакции. Правила доски остаются детерминированной локальной логикой; реплика модели и выбор engine move — разные операции.

## CAP-GAME-002: шахматный двигатель и специальные команды

Сложности easy/medium/hard сопоставлены Maia weights1100/1500/1900. Это названия конфигураций проекта, не измеренная сила игры. При старте дочерний процесс находит/скачивает Lc0 executable и Maia .pb.gz, распаковывает и запускает через chess.engine.SimpleEngine.popen_uci; configure WeightsFile, ping. Файлы живут в lc0_engine_files относительно cwd. Hardcoded release URLs не проверялись сетевым запросом. Эти установки обходят основной AI Hub component pipeline.

Команды модели: RequestBestChessMove, MakeChessMoveAsLLM,UCI, ChangeChessDifficulty,easy|medium|hard, CheatMove,UCI, CheatSpawn,square,piece, CheatRemove,square, EnableAuto/DisableAuto и EnableCheats/DisableCheats. Существуют также active plain-text tags для части этих операций. Cheat commands проверяются instance.is_cheat до публикации в child queue. Auto mode выполняет engine ответ без ожидания модельного выбора. В engine backend есть normal legal move, force chess-board move, spawn/remove; special mode не следует смешивать с обычной проверкой правил.

UCI engine думает с time limit, запрос лучшего хода берёт snapshot FEN в отдельный thread. Результат затем применяется к текущей board через legal validation; явный match/board revision fence в этом участке не найден. Поэтому валидность хода по текущим правилам не заменяет проверку принадлежности результата исходной позиции. После new game/смены состояния это существенный design input.

При запросе конкретного UCI board legality проверяется; warning о неправильной очереди LLM не останавливает попытку, но make_move проверяет принадлежность к legal_moves текущей стороны. Ошибки возвращаются через state projection и prompt variables. Queue acceptance не подтверждает выполнения команды или актуальность projection: немедленный drain после command не ждёт child ACK.

Важное разделение зависимостей: python-chess — правила/notation/UCI wrapper; Lc0 — отдельная executable/inference engine, Maia — model artifact; PyQt6 — окно. Переписывание core не требует переписывать Lc0. Возможность заменить python-chess Rust-реализацией будет проверяться по полноте правил, notation, истории и UCI, а не по наличию package с таким же именем.

## CAP-GAME-003: морской бой

Собственная SeaBattleEngine на stdlib:10×10, fleet4/3/3/2/2/2/1/1/1/1, placement/battle/game_over, запрет соседства кораблей, hit/sunk оставляет ход атакующему, miss передаёт ход, повторный выстрел отвергается. Пользователь выбирает длину корабля, preview/размещение мышью, правой кнопкой меняет ориентацию; стреляет по закрытому полю. Модель расставляет свои корабли вручную либо случайно и выбирает выстрел.

Structured commands: PlaceShip,coordinate,length,H|V; PlaceShipsRandomly; MakeMove,coordinate. Координаты A1—J10, length1—4 проходят regex, затем engine проверяет actual placement/phase/turn/repeated shot. Plain-text tags остаются активной совместимостью для этих команд. Для random placement каждая оставшаяся длина имеет до100 попыток; failure может оставить уже размещённую часть fleet.

Projection Миты включает собственное поле и закрытый opponent view, оставшиеся ships, shot history, wounded ship/hunt target hints, last result, errors. Provider вычисляет tactical hints из известных попаданий. Прочитанные opponent views скрывают неатакованные корабли. Они не должны стать доступными другим персонажам через public session context.

Есть automatic reactions после player shots, завершения расстановки, game over, закрытия и hit/sunk Миты (follow-up, поскольку ход сохраняется); при выключенной automatic реакции есть manual Mita turn. Наблюдение: automatic player-shot invitation всегда говорит «теперь твой ход» даже при hit/sunk игрока, когда engine сохраняет ход игроку. В новой спецификации реакция на попадание и приглашение совершить следующий ход должны быть разными событиями.

## CAP-GAME-004: lifecycle и обратная связь

Command/state/reaction channels пока передают Python dict без version/session contract. GUI child живёт отдельно от main GUI, состояния в памяти child. Reaction listeners и get_state_prompt обнаруживают shutdown/crash и очищают playingGame/game_id/session. Chess stop ждёт до10 s и затем очищает handles без terminate в прочитанной ветви; SeaBattle stop ждёт5 s, затем terminate. Queues закрываются, но общая гарантированная остановка всех native/child operations не следует из этих timeout.

Read state обновляет character variables, а окно может измениться независимо во время следующего LLM call. Новая модель требует match identity, board revision, operation result и stale-command rejection. Правила games и их GUI не должны зависеть от текущего глобального выбора персонажа после старта. Допустимые реакционные события/частота, cancellation при закрытии и сохранение/несохранение match нужно определить явно.

## Доказательства и пределы

Прочитаны GameManager/interface/available registry; MiniGameSessionRegistry; ChessGame и SeaBattleGame lifecycle/commands/reactions/projections; PureBoardLogic основные rules/mutations/outcomes; ChessGameController setup/UCI/moves/commands/state/shutdown по ключевым диапазонам; chess GUI move/promotion/reaction/close и child queue dispatcher; SeaBattle engine/state provider основной gameplay/views/hunt; GUI commands/placement/shots/reaction/close и child entry; manual launch resolution/settings. GUI paint/layout, downloader edge cases, engine ELO replacement и некоторые helper ranges не закрыты полностью. Реальных партий, загрузок engine/model, запуска дочерних процессов, GUI и build не было. Это функциональный проход основных сценариев, не полный runtime QA.

## Сквозной межперсонажный public session context

Дополнительно подтверждён **неочевидный пользовательский контракт**: отдельная Мита, не участвующая в текущей партии, может знать, что игрок играет в шахматы или морской бой с *другим* персонажем. `src/managers/mini_game_session_registry.py:9-70` сохраняет readonly `MiniGamePublicSession(owner_character_id, owner_name, game_id, last_public_event)`, индексируя по владельцу. `GameManager.start_game` публикует сессию **после** успешного старта и проверки `playingGame`; закрытие игры вызывает `stop`, а Chess/SeaBattle обновляют `last_public_event` во время игры.

`src/controllers/prompt_controller.py:730-759` формирует `[Shared Mini-game Context]` для персонажа, исключив **собственную** сессию текущего персонажа. В этом event-блоке содержатся только тип игры, имя другого владельца и последнее публичное событие (ограничено 240 символами), с инструкцией не отправлять команды Chess/SeaBattle чужой партии. Это **социальная осведомлённость персонажа**, не доступ к игровым ходам, закрытым полям или board engine; статусы публичных сессий не следует автоматически приравнивать к игровым сохранениям.

Контракт паритета: играющий персонаж видит собственное приватное игровое состояние через game-specific provider; посторонний может получить только публичную сводку; закрытая партия исчезает из shared context; разные одновременные owners не перетирают друг друга. Source evidence: `src/managers/game_manager.py:70-132`, `src/modules/Chess/game_instance.py:113,179`, `src/modules/SeaBattle/seabattle_instance.py:89,176`, `src/controllers/prompt_controller.py:730-759`, `src/utils/Testing/test_mini_game_public_context.py`, `src/utils/Testing/test_manual_game_launch.py` (тесты здесь не запускались).

**Наблюдение при локальном тестировании (без поиска исправления):** в `test_mini_game_public_context.py` один тест ожидает `miss` по `message="miss"`, тогда как `_dispatch_player_target_reaction` в production читает исход из `event.result`, а `message` использует лишь для LLM narration. Это расхождение тестового payload и runtime field mapping. Будущему API необходимо явно разделить machine-readable result code и человекочитаемое описание; фиксировать старый результат по ошибочно сформированному fixture не требуется.
