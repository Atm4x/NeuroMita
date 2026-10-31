# Фактическая топология процессов NeuroMita по пользовательским функциям

**Статус:** системное сведение подтверждённых ACTIVE/CONDITIONAL runtime-путей. Это **не предложение** повторить существующие Python processes/threads в Rust, а карта того, *какая функция сейчас на какой стороне границы выполняется и где находится её видимый результат*. Источник — `src/controllers/main_controller.py`, `src/services/runtime_features.py`, `src/controllers/ai_engine_controller.py`, `src/handlers/ai_engine/engine_process.py`, `src/modules/Chess/game_instance.py`, `src/modules/SeaBattle/seabattle_instance.py`, `src/game_connections/server.py`, `src/controllers/speech_controller.py`.

## Участники и границы

| Участник | Функции | Граница/транспорт | В каком состоянии существует |
|---|---|---|---|
| Main Python application / optional PyQt6 GUI | Каталог персонажей, LLM orchestration, история/SQLite, настройки, UI, installer admission, Unity/TG subscriptions, хранение runtime state | Внутрипроцессные typed services, EventBus, futures, Qt signals | GUI может быть отсутствующим: предусмотрены `gui_only`/`headless` режимы; точный set подключённых feature зависит от startup и настроек |
| Отдельные Python AI workers | Embeddings/reranking, ASR, TTS/RVC и другие inference/ML функции | Managed subprocess/queues; service request с correlation и timeout | Устанавливаемое окружение + selected runtime composition + ready worker + загруженная модель — разные стадии |
| Unity игровое приложение | Сцены, анимации/действия, игровые события и диалоговый turn admission, audio playback в игре | TCP JSON newline, hello/create_task/task_update/asr_text; frame/data artifacts отдельно | Может отсутствовать или переподключаться без выключения desktop Core |
| Mini-game Chess child | GUI доски, легальность ходов, движок и reaction notifications | `multiprocessing.Process`, отдельные command/state/reaction Queues | CONDITIONAL, запускается по игре; собственная партия принадлежит конкретному персонажу |
| Mini-game SeaBattle child | GUI поля 10×10, engine, расстановка/выстрелы, reaction notifications | `multiprocessing.Process`, command/state/reaction Queues | CONDITIONAL, отдельный runtime child, не разделяет игру шахмат |
| Telegram bot/service | Авторизация и messaging/audio replies бота | Сетевой Telethon client в optional feature основного runtime, async jobs и timeout | CONDITIONAL по способу озвучки/credentials; наличие client не значит, что бот доступен |
| Remote LLM/web/voice API | Текст, потоковые ответы, веб-поиск, Jina reader, удалённые voice профили | HTTP/streaming clients, API auth; не собственные local subprocess в этом audit | При наличии сети/ключа, может ошибаться/отключаться независимо от Core |
| Installer/downloader | Download model weights, Python packages/layers, ffmpeg.exe, activate AI worker | Операции в main runtime + отдельные задачи и новые AI environment layers, возможно subprocess pip | CONDITIONAL/ON_DEMAND; скачан, установлен, активирован и загружен — разные состояния |
| Optional local runtime IPC | Локальный control-plane извне: ping, status, hardware, AI restart | Отдельный TCP/JSON сервис, **не** Unity protocol и **не** AI worker IPC | Только по RUNTIME_IPC_ENABLED и доступности порта |
| Standalone FastAPI web/VTT & HOI4 prototype | Отдельные web tools/prototypes | Самостоятельные entrypoints | Не объявлять частью production Core без доказательства registration/startup |

## Контуры пользовательских запросов

**Текстовый диалог:** пользователь / Unity событие → application admission/routing → prompt/history/RAG → удалённый LLM provider → structured response→ история/UI → по запросу TTS. На этом пути Python AI worker может понадобиться для embeddings или локального голоса, но облачный LLM request непосредственно принадлежит Core HTTP side.

**Голосовой ввод:** device selection и mic capture принадлежат существующему Python audio/ASR пути, включая managed remote worker; распознанный текст после проверки ownership идёт либо в desktop composer, либо Unity через TCP (если game session владеет player input). Captured audio frame/PCM и готовая текстовая реплика — разные artifacts.

**Game actions:** LLM structured intent → Core semantic actions / packaged task update → Unity intent executor → обновлённое игровое состояние и новые события. Принятие packet не означает выполненную анимацию. Игровой scheduler continuation/idle принадлежит клиенту Unity, а не только Core.

**Mini-games:** запускается дочерний GUI+engine процесс конкретной игры, его очередь состояния возвращает контекст/события владельцу. В основную LLM беседу другого персонажа попадают только публичные summaries из `MiniGameSessionRegistry`, не внутреннее состояние доски.

**Установка AI модели:** GUI/Headless запрос → component manifest → plan/queue → download/pip/staging → runtime composition → optional worker restart/validation → readiness probe → UI status. Передача operation status и loaded-model status по разным каналам предотвращает ложное равенство `installed == usable`.

## Семантические состояния, которые нельзя потерять

- Main application **запущено**, но Python AI layer ещё не установлен.
- Отдельный AI worker **готов**, но конкретный TTS/ASR/RAG model ещё **не загружен**.
- Unity **подключена**, но клиент не является current player input owner (несколько сессий/anonymous compatibility).
- Chess/SeaBattle GUI **создан**, но logical game state/engine ещё не опубликовал readiness.
- HTTP request **передан**, но поток ещё не выдал первую видимую часть текста; затем может быть tool follow-up.
- Voice asset **произведён**, но проигрывание в игре ещё не состоялось; завершение проигрывания — отдельное событие.
- Import/installer task **accepted**, но очередь ещё не исполняет её; UI cancel может подавить показ result, не обязательно принудительно прервать backend.

## Ограничения и направление дальнейшего аудита

Это карта ролей, а не запрет на будущий процессный монолит/actors/threads: новую реализацию надо выбирать **после** сбора требований. Проверить ещё: точное platform-specific process tree (Windows), remote TTS временные файлы и cleanup, inter-process cancellation semantics на long-running CUDA, состояние Qt/Unity при живом installer, полный набор externally configurable TCP ports, и разрешения доступа standalone сервисов.

**Смежные спецификации:** [Startup](startup-and-shutdown.md), [AI env](ai-environments.md), [AI IPC](ai-ipc.md), [Unity TCP](unity-transport.md), [optional features](optional-features.md), [mini-games](../01-functional/desktop-mini-games.md), [install queue](install-operation-admission-queue-and-completion.md), [local IPC](../01-functional/local-runtime-ipc-external-control-contract.md). Живые запуски Windows/Unity/CUDA/Telegram и E2E не проводились.
