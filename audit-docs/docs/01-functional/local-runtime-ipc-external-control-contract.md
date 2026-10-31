# Локальное runtime IPC: внешний клиент → Core, самостоятельный пользовательский контракт

**Задача исследования:** выделить функциональность внешнего программного управления приложением, не смешивая её с межпроцессным транспортом `Rust Core ↔ Python AI Engine` или протоколом Unity. **Source snapshot:** локальный `CodeNow.zip`, без подтверждённого commit SHA. В описании фиксируются действующие границы Python-протокола, но формат нового Rust API ещё не выбран.

## CAP-LOCAL-IPC-001 — запуск/выключение локального IPC по настройке

**Статус: `CONDITIONAL`, runtime registration подтверждена.** `src/controllers/main_controller.py:121-127,218,684-686`; `src/services/runtime_ipc_service.py:116-168,170-231`; `src/ui/settings/general_settings.py:185-222`.

При создании `MainController` формируется сервис локального IPC через settings service. Пользователь в General Settings включает `RUNTIME_IPC_ENABLED` (по умолчанию `False`) и указывает `RUNTIME_IPC_PORT` (по умолчанию `47831`, UI validation `1024..65535`). Сервис подписывается на оба параметра и **во время работы** останавливает либо поднимает слушатель. Если порт изменён, уже действующий слушатель закрывается и создаётся новый. При завершении MainController закрывает подписку и сокет. Используется loopback `127.0.0.1`, а не публичный сетевой интерфейс.

**Значимое состояние:** enabled/configured port, actually running/bound port, `last_error`. `ipc.status` может сообщить сконфигурированный и фактически связанный порт отдельно. Если сокет занять не удалось, listener не становится `running`; причина доступна в `last_error`. Значение `0` доступно программно для тестов и выбирает случайный порт, но UI принимает пользовательские порты `1024..65535`.

## CAP-LOCAL-IPC-002 — обнаружение разрешённых команд и прямой вызов

**Статус: `ACTIVE` внутри включённого IPC.** `src/core/runtime_ipc.py:18-90`; `src/services/runtime_ipc_service.py:37-71,78-114`; `src/controllers/main_controller.py:218`.

Объекты регистрируются через **явную маркировку** метода `@ipc_allowed(name, description=...)`, а не по всем публичным атрибутам. `IPCRegistry.register_object` обнаруживает только методы с такой меткой, запрещает одинаковое имя и сохраняет связанный callback. Список `ipc.methods` возвращает имя и описание разрешённых методов; неразрешённый метод выдаёт `method_not_allowed`. `params` может быть объектом (`**kwargs`), массивом (`*args`) или `null` (без аргументов). Возвращаемое awaitable выполняется до получения результата.

В текущем зарегистрированном каталоге:

| Метод | Действие | Источник | Результат |
|---|---|---|---|
| `ipc.ping` | Проверить отклик слушателя | `runtime_ipc_service.py:46-48` | `{pong: true}` |
| `ipc.status` | Прочитать running/host/ports/last_error | `runtime_ipc_service.py:50-52,212-223` | JSON object |
| `ipc.methods` | Обнаружить разрешённые методы | `runtime_ipc_service.py:54-56`; `runtime_ipc.py:64-70` | список имен/описаний |
| `hardware.snapshot` | Получить inventory устройств, `refresh=false/true` | `runtime_ipc_service.py:58-63` | hardware snapshot сервиса |
| `ai.topology` | Прочитать текущую карту AI workers | `runtime_ipc_service.py:65-70` | topology snapshot |
| `ai.restart_service` | Перезапустить сервис `tts/asr/rag/beats` | `ai_engine_controller.py:1973-2011`; `main_controller.py:218` | Boolean outcome |

В `main_controller` явно регистрируется `AIEngineController`. Других объектов `register_object()` на production path при данном поиске не выявлено. Это **шесть подтверждённых** команд, а не неограниченный Python RPC.

## CAP-LOCAL-IPC-003 — JSON-line request/response и обработка ошибок

**Статус: `ACTIVE` при включённом сервере.** `src/services/runtime_ipc_service.py:73-114`.

Сетевой транспорт: TCP, один JSON-request на строку, один JSON-response на строку, UTF-8, с пределом на входящую строку **1 MiB**, timeout сокета **10 секунд**. Различаются `id` запроса, `method`, `params`; синхронный ответ содержит `{id, ok, result}` либо `{id, ok:false, error:{code,message}}`. Зафиксированы категории ошибок `request_too_large`, `method_not_allowed`, `invalid_params`, `invalid_request`, `runtime_error`, `serialization_error`. Запрос без `method`, некорректный JSON, неподдерживаемые `params` явно отвергаются.

Текущий сервер использует `socketserver.ThreadingMixIn` и выделяет обработчик на соединение, с daemon threads. При включении/отключении весь listener пересоздаётся и новые запросы больше не принимаются после остановки. Сохранение долговременных IPC sessions, доставка событий подписчикам, потоковая выдача результатов и встроенная авторизация клиентов **не обнаружены**; не следует без проверки объявлять их существующими функциями.

## Сценарии, состояния, зависимости, границы

1. Включить настройку → TCP listener готов → `ipc.ping`, `ipc.methods`; внешняя автоматизация видит доступные команды без GUI-кнопок каждого действия.
2. Запросить `hardware.snapshot(refresh=true)` → hardware inventory service → свежая диагностическая проекция.
3. Запросить `ai.topology` → owner AI Engine administration → актуальная топология; worker может ещё не быть ready.
4. Запросить `ai.restart_service` с конкретным `service` → AIEngineController в текущей shared/split конфигурации выполняет управление worker; Boolean не равен обязательной готовности всех AI-моделей.
5. Изменить порт либо выключить IPC → listener пересоздаётся/останавливается; объектные сервисы Core продолжают работу независимо от внешнего управляющего TCP.

**Функциональная зависимость:** IPC registry/transport → Core settings + hardware inventory + AI administration. Никакой inference или CUDA-модели сервер не исполняет. Это **входящий control-plane**, отличный от исходящего LLM API, Unity transport и внутреннего Python AI worker IPC.

**Концептуальные контракты будущего Core:** управляемая локальная доступность, явно ограниченный набор внешних команд, обнаружение API, correlation request-id, typed errors, согласование результата с фактическим состоянием worker и диагностика отказа bind. Не требуется дословно переносить декораторы, Python reflection или конкретный socketserver.

## Возможные функциональные проверки паритета

| Сценарий | Ожидаемая функциональность | Основание |
|---|---|---|
| Disabled → enabled → disabled | listener появляется и исчезает по настройке без перезапуска приложения | `test_runtime_ipc.py:118-137` |
| Allowed / unknown | зарегистрированная команда выполняется, неизвестная отвергается | `test_runtime_ipc.py:53-81` |
| `ai.restart_service` | request с `service`, `timeout` достигает AI administration | `test_runtime_ipc.py:84-116` |
| Invalid input | формализованные error responses для invalid JSON/params/too large | `runtime_ipc_service.py:78-113` |
| Runtime state | enabled отличается от actual running и причины bind failure | `runtime_ipc_service.py:160-194,212-223` |

**Неясности:** внешний consumer, использующий конкретные команды в реальном пользовательском окружении, не установлен; IPC не выполнялся на этой машине. Верификация безопасности/доступа не подменяет функциональный аудит, а проектирование протокола нового Rust Core будет отдельным этапом.

**Требования:** `REQ-LOCAL-IPC-001` — условный внешний control-plane должен включаться/выключаться из user settings без жизненной зависимости бизнес-логики; `REQ-LOCAL-IPC-002` — discoverable allowlisted commands с typed results и errors; `REQ-LOCAL-IPC-003` — hardware/AI topological diagnostics и AI service administrative action должны быть представлены как отдельные операции, их readiness не следует путать с network listener readiness.
