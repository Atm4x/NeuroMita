# Запуск и завершение приложения

Охват: основной host, composition root, deferred GUI backend, headless host. Статический анализ; фактический запуск не выполнялся. Источники E-001—E-017 в [индексе](../00-research/source-evidence-index.md).

## Functional Capability: выбор режима запуска

**ID:** `CAP-RUN-001`. **Статус:** ACTIVE. **Домен:** lifecycle.

### Назначение и сценарий

Пользователь или launcher запускает приложение с интерфейсом, только оболочкой настроек либо сервером без GUI. Выход — работающий host или код ошибки; выбор влияет на состав обязательных сервисов, а не только на видимость окна.

### Входы и правила

По умолчанию `full`. `NEUROMITA_STARTUP_MODE` задаёт режим, CLI переопределяет env в порядке аргументов. `--gui-only` задаёт `gui_only`; `--headless`, `--server`, `--server-only`, `--no-gui` задают headless. `--startup-mode=` дополнительно нормализует aliases с дефисом/подчёркиванием. Неизвестное значение режима становится full.

`--headless-run-seconds=` / `--run-seconds=` и `NEUROMITA_HEADLESS_RUN_SECONDS` задают ограничение длительности (0 — бессрочно). `--headless-status-interval=` и одноимённая env с префиксом `NEUROMITA_` задают период снимков (default 60, 0 отключает периодику). Значения преобразуются в float с нижней границей 0, некорректное значение использует fallback. Граничные NaN/Infinity отдельно не проверены.

`--server-host=` и `--server-port=` записываются в env для дальнейшей настройки сети. Неизвестные аргументы остаются в argv. Поставляемый scripts/run.py не пересылает свои argv дочернему pyz; фактический способ задания CLI через Launcher.exe ещё не исследован. Env остаётся подтверждённым входом.

### Состояние, lifecycle, ошибки

Options immutable. Главный поток выбирает GUI/headless после общей подготовки. Headless не поддерживает последующее GUI attachment: `MainController.update_view` бросает исключение. GUI-only регистрирует disconnected game link и NoLoopService, создаёт fallback и выходит из конструктора до mandatory backend.

### UI и побочные эффекты

Full/gui_only создают окно; headless пишет status в logger. Startup options меняют process env и argv. Общий bootstrap создаёт каталоги, выполняет recovery/check updates и пишет диагностику.

### Требования и возможная реорганизация

Сохранить различие сценариев и независимость server-only от GUI imports. Новый режим должен задаваться типизированным startup configuration, не разбором строк в каждой подсистеме. Конкретный набор aliases — вопрос совместимости запуска, а не обязательная структура Rust API. Rust alternatives будут исследованы после полного функционального прохода.

## Functional Capability: отзывчивая оболочка при запуске backend

**ID:** `CAP-RUN-002`. **Статус:** ACTIVE для full, CONDITIONAL по выбранному режиму. **Источники:** E-002, E-007, E-009, E-013.

### Назначение, входы и выходы

Показывать интерфейс и настройки, пока основной runtime создаётся в фоне. Входы: settings controller, startup mode, runtime context. Выходы: backend attached либо startup error в представлении.

### Состояние и владение

GuiCompositionRoot владеет деревом GUI, settings binding, page/window/shell coordinators и adapters. GuiBackendLoader владеет стартовым потоком, stop event и ссылкой на готовый MainController. Backend создаётся без view; attachment происходит на GUI thread через queued signal. API presets принадлежат доступной при старте оболочке и могут использоваться до готовности backend.

### Жизненный цикл

1. Создать QApplication, dispatcher, Qt logging, wheel guard и app identity.
2. Создать shell settings и минимальные services, disconnected game link, settings-only character registry.
3. Создать/показать окно, обработать первые UI events, записать startup trace.
4. Через QTimer запустить loader; тот создаёт MainController в supervised thread.
5. MainController создаёт loop, AI engine administration, task/history/prompt/API/embedding presets, characters, model, chat; регистрирует optional capabilities, планирует enabled, подписывает handlers, создаёт сервер.
6. Loader инициализирует collectors; их отказ только логируется. Публикует controller и queued ready signal.
7. GUI root прикрепляет backend; планируется загрузка chat history и обновление home status.

### Инварианты, отмена и ошибки

Повторный loader.start не запускает второй поток. При stop до создания MainController дальнейшая сборка пропускается. При stop после создания controller он закрывается; поздний ready не должен прикреплять backend к закрытому GUI. GuiCompositionRoot отклоняет attach после close.

Исключение startup отображается как backend failure; окно не обязано исчезать. Ошибка attachment вызывает close_app и failure callback. Сбой внутри конструктора MainController до присваивания loader-local `controller` не даёт loader ссылки на частично созданный объект: это риск cleanup, а не доказанная утечка конкретного ресурса.

### Зависимости и побочные эффекты

Qt affinity, services registry, settings, background supervisor, game server. Сетевой сервер появляется до attachment GUI, но после обязательных регистраций. Optional loading продолжается независимо. Полный inventory UI состояний ещё не исследован.

### Требования к новой системе

Развести shell readiness, mandatory application readiness и readiness отдельных capabilities. Представление получает стабильные состояния/команды; бизнес-объекты не обязаны повторять иерархию root/loader/controllers. Сборка runtime должна иметь явно принадлежащие ей ресурсы и rollback при отказе на любом шаге.

## Functional Capability: headless hosting

**ID:** `CAP-RUN-003`. **Статус:** CONDITIONAL: headless mode. **Источники:** E-008, E-016.

Сценарий: обслуживать Unity без окна; возможен ограниченный по длительности прогон. Host владеет stop event, controller и previous signal handlers. SIGINT/SIGTERM устанавливаются только на main thread и восстанавливаются в finally. `request_stop` вызывает AI prepare_shutdown, если доступен, затем ставит stop event.

После создания controller host требует наличия server controller с running=True; иначе ошибка запуска и код 1. Более строгий snapshot проверяет и controller.running, и transport.running. Snapshot содержит PID, host/port, число connections, AI mode, worker alive/exitcode и ready services. Это диагностический снимок, не полная модель доступности.

Основной цикл проверяет stop каждые 0.25 s. Ограничение run_seconds отсчитывается после успешного startup и начального snapshot, а не от старта процесса. При остановке/KeyboardInterrupt код 0, прочей ошибке код 1. finally вызывает controller.close_app и восстанавливает handlers. UI prompts не должны быть необходимы; Telegram auth service регистрируется с available=False.

Core должен сохранять возможность работы без GUI и управляемый shutdown. Конкретные polling interval/поля private worker structures — текущие детали, не целевая Rust-модель. Проверить реальные ограничения headless в TTS, installer и auth при проходе соответствующих ветвей.

## Functional Capability: завершение с освобождением ресурсов

**ID:** `CAP-RUN-004`. **Статус:** ACTIVE. **Источники:** E-011, E-007, E-017; `src/ui/windows/app_window_base.py:1224 closeEvent`, `:1256 _finish_deferred_close`.

### Сценарий и состояния

Закрытие окна, quit приложения, signal, окончание headless duration или startup failure. Повторный close_app защищён lock и `_closing_started`. Окно сначала откладывает native close, отключает ввод и показывает shutdown overlay; в отложенном callback закрывает backend/dialogs, затем повторно закрывает окно с finalizing=True.

### Подтверждённый порядок close_app

Runtime IPC → игровой сервер → history timers → remote voice → GUI workers → GUI controllers → API configuration → model subscriptions → optional features → installable catalog → Telegram auth prompts → AI engine (timeout 5 s) → asyncio loop → character resources → settings subscriptions/writer → EventBus → background supervisor (timeout 3 s) → executors (wait=False).

Каждый shutdown_step логирует Exception и продолжает следующие шаги. Это best-effort cleanup: успешный выход из close_app не доказывает физического завершения всех потоков. Optional manager отдельно снимает registrations и останавливает зависимые функции до их зависимостей.

После app.exec loader получает shutdown, ожидание до 5 s; timeout логируется. GUI objects удаляются через deleteLater и обработку DeferredDelete. Отрицательный код event loop преобразуется в 1. Точные гарантии supervisors, subprocess escalation и cancellation ещё исследуются.

### Требования

Запретить приём новых работ до уничтожения ресурсов; сохранить запись настроек; исключить callbacks в удалённые UI objects; завершать зависимых до dependencies; сделать повторную остановку безопасной. Текущий порядок — источник зависимостей, а не фиксированный алгоритм для Rust. Требуется определить общий deadline и наблюдаемый итог cleanup в новой модели.

## Общая подготовка: эффекты до ready

Bootstrap вычисляет base directory, активирует core path, мигрирует распознанные старые runtime layers и запускает отложенную уборку overlays (default 5 s). Core path имеет приоритет над optional main runtime paths. AI environment root не добавляется целиком в main sys.path.

`features.env` загружается после первоначальной настройки путей. Updates/recovery выполняются до Qt imports; auto apply может прервать старт рестартом, check-only работает в daemon thread. Эти update threads не проходят через task_supervisor в проверенном коде. Последствия для общего shutdown требуют проверки updater.

`_run_torch_bootstrap` только пишет сообщение; `_prime_onnxruntime` и compatibility patches сейчас no-op. Поэтому phase names и старый комментарий не являются доказательством загрузки torch/ONNX главным процессом.

`base_dir()` вне явного env берёт корень исходников; settings находятся в `Settings`, logs — `Logs`, prompts/checkpoints допускают overrides. Полная карта history/models/temp и переносимость сохраняемых путей ещё не восстановлены.
