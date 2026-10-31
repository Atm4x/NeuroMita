# Контракты typed services и уведомлений настроек

**Срез:** active Python runtime (статический). Цель: отделить фактические guarantees/scope от названий `EventBus`, `SettingsService`, `SettingsRegistry`. Основное общее поведение фоновых задач и EventBus уже описано в [background-tasks-and-events](background-tasks-and-events.md); здесь — ownership и стык с настройками.

## CAP-SERVICE-001 — typed service registry (ACTIVE)

`src/core/services.py:24-39,43-80,85-227`:

- Lookup contract через конкретный Python ABC/type, при отсутствии `get` бросает `ServiceNotRegistered`; `get_optional` возвращает default; `wait` ждёт registration с monotonic timeout. `isinstance(impl, contract)` проверяется при register.
- `register` без owner — application-scoped; duplicate без replace отвергается. `register_owned` создаёт уникальный owner token + закрываемый handle. Поздний close старого owner **не** удаляет новый service. Если optional заменял постоянный application service, close может восстановить его; предыдущий временный owner намеренно не возвращается.
- `reset` очищает entries, но не освобождает автоматически backing resources — lifecycle сервиса принадлежит владельцу.
- Общий `services()` глобальный процессный registry; typed contract ≠ доказательство explicit dependencies во всех callers (часть кода обращается к нему через `use`). Это свойство нынешнего composition, не обязательная Rust layout.

**Специальный случай API configuration:** `src/startup/api_configuration.py:13-65` создаёт ProtocolBuilderService/ApiPresetService до backend и в headless по требованию. Returned runtime handle закрывает presets только если сам создал его; фактическое закрытие/удаление регистрации при вызове `close` различаются и требуют owner composition review.

## CAP-SET-OBSERVER-001 — SettingsRegistry (ACTIVE)

`src/core/settings_registry.py:15-40,45-102,103-171,173-240,242-347`:

- `SettingChange` содержит key/new/previous/revision/source. `set` одинакового значения no-op; `update_many` не посылает событие для unchanged keys. `subscribe(keys=...,replay=True)` доставляет replay с текущей общей revision и `previous=None`.
- Каждый subscriber получает свою очередь изменений и serial drain; разные subscribers могут исполняться одновременно/через разные dispatcher lanes. Нет атомарности вида «сначала запись в файл, затем уведомления».
- Значения и snapshots shallow: изменения nested objects не нормализуются/не детектируются автоматически. `replace_all` уведомляет только о присутствующих ключах, не эмитит отдельных delete events для ключей, исчезнувших из старой карты (`replace_all:173-202`). **Наблюдаемая семантика**, потенциальный compatibility edge-case.
- `SettingsSubscription.close` idempotent, unsubscribe удаляет pending listener changes; observer callbacks exceptions изолированы/логируются; registry close закрывает dispatcher с `drain=True`/timeout=2s.

## CAP-SET-GUI-BRIDGE-001 — Qt settings mirror (CONDITIONAL GUI)

`src/ui/settings/settings_binding.py:12-72,87-188,190-246`:

- В GUI локальный shallow snapshot и подписка на registry; backend callback только emit Qt queued signal, применение — Qt thread. Write делает **optimistic local update**, затем `SettingsService.update`; на exception snapshot rollback + `write_failed`.
- Two-way binding подавляет feedback loop по `(id(owner),key)`, отписывает owner destroyed и disconnect write signal; widget write callback проглатывает exceptions после самого mirror-set. Qt signal pump и runtime registry revision не образуют единого синхронного transaction.
- Qt mirror не равен источнику правды; его локальное состояние может временно опережать другой consumer. UI should reflect persistence errors separately from immediate mutation.

## EventBus: точная семантика важных вызовов

`src/core/events.py:17-61,118-143,211-307,325-405`; `src/core/serial_dispatcher.py:24-29,59-94,96-165`:

| API / режим | Фактический outcome |
|---|---|
| `try_emit` без подписчиков | `True`, без выполнения handler |
| `try_emit(sync=True)` | ORDERED async admission, **не synchronous invocation** |
| `emit` | `None`, отказ non-best-effort лишь логируется |
| `COMMAND` | single lane, maxsize512, FIFO admission; execution errors изолированы |
| `ORDERED` | striped8 lanes, maxsize4096; FIFO per hash key / lane, без global order |
| `CRITICAL` default | striped4 lanes, key=event name, maxsize4096 |
| `BEST_EFFORT` | executor try_submit; saturation даёт отказ |
| `flush` | ждёт command/critical/ordered, **не** BEST_EFFORT executor |
| `shutdown` | после budget может отбросить queued items; restart сохраняет bus identity и subscriptions, но не очередь |

Важное разделение: `accepted` означает передачу в очередь, **не** commit факта, действие игры, готовность GUI или delivery ACK. Event handlers могут завершиться exception, которая не возвращается publisher. `SerialDispatcher` имеет потенциальную гонку счётчика `_queued`: queue.put перед increment, worker может обработать item до increment (`serial_dispatcher.py:77-84,140-160`). Это статический риск ложного `wait_idle`, а не проверенный исполняемый дефект.

## Требования / проверки

- `REQ-SERVICE-001`: Различать lifecycle временного и process-scoped service; не допускать позднего cleanup прежнего поколения.
- `REQ-SERVICE-002`: Readiness/wait/get/no service должны иметь явные outcomes. Порядок и ownership не следует выводить из имени `Service`.
- `REQ-OBSERVER-001`: Typed changed snapshots с revision, unsubscribe/replay, serialization of notification per subscriber; отдельно durable persistence outcome.
- `REQ-EVENT-001`: Не выдавать admission за success; различать delivery scope, overflow, scheduling, execution и application ACK.

Валидация: owner replacement race; replay после replace_all; unsubscribe при pending changes; async `sync=True`; absent subscriber; saturated lanes; shutdown non-draining queue; GUI optimistic write failure.

**Границы:** full callgraph всех `services().get/use` и всех event consumers ещё не собран. Отдельные legacy consumers могут нарушать ожидаемые typed interfaces; искать при дальнейшей проверке reachability.
