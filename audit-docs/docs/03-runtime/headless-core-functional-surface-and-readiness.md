# Headless NeuroMita — функциональная поверхность Core без desktop GUI

**Статус:** `CONDITIONAL`, подтверждённый пользовательский режим запуска. **Scope:** поведенческий контракт headless Core, а не предложение архитектуры Rust или новая реализация CLI/TUI. **Capabilities:** `CAP-HEADLESS-SURFACE-001—005`. **Revision:** рабочий снимок `CodeNow.zip`; Git SHA локально не проверен. **Evidence:** `src/__main__.py:59-122,317-352`, `src/startup/headless_runtime.py:14-157`, `src/controllers/main_controller.py:65-110,155-190,192-291`, `src/services/telegram_auth_service.py:34-71`.

## Назначение и сценарий

Пользователь может запускать NeuroMita **без рабочего графического окна**, обслуживать подключение Unity и Core/AI сервисы, наблюдать состояние готовности в логах и корректно завершать процесс. Это не эквивалент `gui_only`: первый режим запускает Core, во втором включается GUI с отключённым обязательным backend. GUI-панели настройки и авторизация Telegram, ожидающая пользовательский ввод в окне, для headless не предоставляются автоматически.

## Фактический способ запуска

`src/__main__.py`:

| Способ | Назначение | Эффект |
|---|---|---|
| `--headless`, `--server`, `--server-only`, `--no-gui` | Выбрать реальный серверный режим | Не инициирует Qt runtime (`load_gui=False`); Core bootstrap выполняется до создания host |
| `--startup-mode=headless` | То же через общий mode | Нормализуются aliases с дефисами/подчёркиваниями |
| `NEUROMITA_STARTUP_MODE` | Значение по умолчанию без CLI override | Может быть переопределено аргументами |
| `--server-host=…`, `--server-port=…` | Адрес игрового TCP listener | Переносятся в `NEUROMITA_SERVER_HOST/PORT`, читаются server controller при startup |
| `--headless-run-seconds` / `--run-seconds` | Ограниченный по времени запуск | 0 означает без deadline, отсчёт после готовности Core |
| `--headless-status-interval` | Периодическая запись статуса | 0 выключает периодические snapshots, default 60 секунд |

При запуске режим `headless` создаёт `MainController(None, startup_mode='headless')`, не создаёт `QApplication` и требует, чтобы игровой server controller действительно сообщил о запуске (`startup/headless_runtime.py:113-126`). Указанный `host/port` является параметром TCP listener, **не HTTP/GUI административной API** и не автоматическим удалённым TUI.

## Границы доступности функций без GUI

| Возможность | Статус/условие | Источник/оговорка |
|---|---|---|
| Core и обработка диалогов Unity | Серверная ветвь active после успешного запуска | `main_controller.py:192-291`; наличие работающего connection/client отдельно не гарантировано |
| Отдельные Python AI workers | Входят в Core backend, имеют независимую готовность | `headless_runtime.py:72-103`: снимок показывает `ai_mode`, процессы alive, `ready_services` по каждому worker |
| Telegram voice | Conditional по voice method/settings; получение кода/2FA через GUI недоступно | `main_controller.py:169-180`; `telegram_auth_service.py:34-71`: `available=False` в headless, интерактивный auth prompt приводит к явной ошибке |
| GUI-only установки и modal prompts | Не следует считать доступными по умолчанию | отдельный `InstallableOperationsService` поддерживает headless задачи, но конкретный backend/install readiness зависит от service construction и настроек; [очередь установок](../01-functional/installable-component-probe-and-operation-contracts.md) |
| Управление Core через TCP | Игровой протокол доступен после handshake/registration | [семь входящих команд](unity-ingress-seven-actions-and-state-outcomes.md); [отдельный внешний Core TCP IPC](../01-functional/local-runtime-ipc-external-control-contract.md) включается настройкой и **не** является тем же TCP server |
| UI-переключение / диалоговые окна / GUI auth | GUI отсутствует | `MainController` с headless mode не поддерживает `update_view`; интерфейс потребует отдельного пользовательского маршрута и **не** реализован этим headless host |

**Проверить перед объявлением полного паритета:** доступность установщика на headless без Qt; управление API-профилями/голосовыми движками вне GUI; auth bootstrap с уже сохранённой Telegram-сессией; включение и остановка optional features; Windows service process lifetime. Эти функции не следует предполагать реализованными только из-за наличия flag `--headless`.

## Готовность, состояние и остановка

- **Startup ready**: после инициализации `MainController` и game-link controller; если listener не поднялся — startup error с ненулевым exit (`headless_runtime.py:113-122`). Наличие server listener не гарантирует готовность AI inference.
- **Снимок состояния**: `pid`, `server_running`, `host`, `port`, число игровых connections, `ai_mode`, `workers[name]={alive,exitcode,ready_services}` (`:72-103`). Это **наблюдаемость процесса**, а не универсальная health-карта всех optional функций.
- **Периодический статус**: initial snapshot после успешного startup, затем при `status_interval > 0` (`time.monotonic`), а не по абсолютным часам (`:124-140`).
- **Завершение**: `SIGINT/SIGTERM` на main thread либо запрос stop вызывают `prepare_shutdown()` AI controller, затем флаг остановки; `finally` закрывает Core и восстанавливает предыдущие signal handlers (`:29-70,148-157`). Нормальная остановка и KeyboardInterrupt возвращают 0; неисправность инициализации — 1.
- **Временной запуск**: `run_seconds` отсчитывается после успешной готовности (`:127-136`), а не от запуска процесса; при 0 процесс остаётся действующим до внешнего stop.

## Инварианты будущей полной версии

- `REQ-HEADLESS-SURFACE-001`: Core и игровое взаимодействие доступны без графического runtime; обязательные backend dependencies нельзя маскировать наличием GUI.
- `REQ-HEADLESS-SURFACE-002`: статус listening Core и готовность конкретных AI workers/services различимы.
- `REQ-HEADLESS-SURFACE-003`: завершение headless режима координирует AI/process/network shutdown и возвращает наблюдаемый результат.
- `REQ-HEADLESS-SURFACE-004`: отсутствие GUI делает операции, требующие интерактивной аутентификации/подтверждения, явно недоступными или требующими отдельного подтверждённого канала, а не зависающими без пользователя.
- `REQ-HEADLESS-SURFACE-005`: bounded-run и периодический status mode сохраняют семантику monotonic elapsed time и явно отделены от user conversation timer.

**Parity fixtures:** launch flags/env precedence, no Qt import, server-start failure, ready snapshot with worker states, signal stop, idempotent cleanup, disabled status interval, 1s bounded run, Telegram new authorization in headless. Тест `src/utils/Testing/test_headless_runtime.py` в этом проходе: **6/6 passed**, offline mocks/entrypoint parsing, не live server/Windows deployment.

**Граница дизайна:** этот документ не выбирает Rust CLI/TUI, remote management transport, authentication или способ установки удалённого приложения. Все эти решения допустимы *после* аудита на основании функционального перечня.
