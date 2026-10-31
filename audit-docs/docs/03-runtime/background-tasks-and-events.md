# Фоновые задачи, отмена и события

Статус: ACTIVE. Это функциональные гарантии host runtime, не схема классов для переноса. Прочитаны TaskWorker, GuiTaskSupervisor, основные thread/future/lifecycle/watchdog paths TaskSupervisor, ExecutorRegistry и SerialDispatcher; EventBus admission/delivery/subscriptions/lifecycle по основным диапазонам. Полный failure policy, daemon executor internals и все consumers ещё не закрыты.

## GUI operations

CAP-JOB-001. TaskWorker оборачивает функцию в QThread, публикует progress/status/result/error/cancel. start атомарно регистрирует task_key и exclusive_resources у GuiTaskSupervisor; конфликт даёт False, shutdown supervisor — RuntimeError. Иерархические имена ресурсов разделены двоеточием: rag-index конфликтует с rag-index:crazy, разные characters не конфликтуют друг с другом. Это добровольные декларации отдельных jobs, не блокировка БД и всех mutations приложения.

Owner слабый; ownerless задача может переживать окно прогресса. cancel_owner помнит закрытого владельца и запрещает поздний новый start, отвязывает прикладные callbacks всех его задач, сохраняет служебный QThread.finished, запрашивает interruption и ждёт общий budget (default2s). Неостановленные jobs остаются в supervisor. stop_all дополнительно закрывает admission. Никакого force kill thread здесь нет.

Cancel cooperative: TaskWorker подставляет progress_callback, который бросает TaskCancelledError; до/после функции также проверяет interruption. Функция, не вызывающая callback или глотающая его exception, может продолжать работу и durable mutations. Если interruption пришёл после commit, finished result заменяется cancelled signal; отмена не гарантирует отсутствие эффекта. Не каждый caller проверяет False от start. Закрытие GUI/отвязка callbacks также не откатывает работу.

## Threads/futures и deadlines

CAP-JOB-002. Отдельный TaskSupervisor регистрирует app-wide задачи по owner identity и name, уникальным task_id, cancel_event/deadline. Повтор имени отклоняется; replace сначала просит старую остановиться и ждёт, если allow_overlap не разрешён. Для submit отказ может возвращаться Future с exception; start_thread бросает exception. Weak owner проверяется против повторного использования Python id, для неweakref объектов используется strong fallback. GC owner сам по себе не является гарантией остановки.

Cancellation event не автоматически передаётся в target: функция должна получить тот же event через args/closure либо запросить его у supervisor. Future guard проверяет event до начала; Future.cancel не прекращает уже выполняющийся fn. Watchdog отмечает deadline, ставит event/cancel и пишет log, но не убивает thread и не превращает поздний successful result в отдельный typed timeout. Snapshot различает running/cancellation_requested/overdue. Thread wrapper логирует BaseException; future failures остаются в Future.

cancel_owner и shutdown ждут threads в общем budget; running futures не присоединяются этим loop. Shutdown закрывает новые задачи и watchdog, но часть работы может ещё исполняться. Общая остановка MainController дополнительно управляет executors/services; детали каждого consumer нужны отдельно.

## Пулы и перегрузка

CAP-JOB-003. Именованные pool specs: generation3workers/capacity6, background-llm1/4, IO6/unbounded, DB-writer1/unbounded, LLM-HTTP8/8 с daemon retired budget8, debug-dump1/2, event-bus8/512. Capacity считает executing+queued **только если caller использует try_submit**. Обычный submit намеренно обходит capacity; TaskSupervisor.submit вызывает именно его. Наличие bounded spec не доказывает global bound всех callers.

Trace context переносится в executor callback. Reservation освобождается по done; HTTP daemon abandon может освободить логический slot до физического завершения. Shutdown cancel-ит queued futures при wait=False; это не гарантия прекращения network I/O. Registry после shutdown_all очищает pool map, сам не имеет permanently closed admission flag. Числа и конкретная модель thread pools — свойства текущего runtime, не обязательные параметры нового core.

## События и границы доставки

CAP-EVENT-001. EventBus — in-process asynchronous bus. Query-like get_/_get_ имена отклоняются, state query идёт через typed services. Подписки weak по умолчанию, есть close/unsubscribe/owner removal. Event snapshot subscribers берётся при admission; затем callbacks вызываются последовательно для конкретного event, failures логируются с продолжением, не возвращаются publisher.

BEST_EFFORT — bounded executor try_submit; COMMAND — отдельная lane1/capacity512; CRITICAL default —4 lanes по4096; ORDERED —8 lanes по4096. sync=True выбирает ORDERED, **не выполняет callback синхронно**. Явный delivery выше default; command names имеют приоритет перед sync. Ordered key: explicit, затем ASR общий ключ, иначе stream/task/uid/character/event name. Hash распределяет keys между striped FIFO lanes: разные keys могут мешать друг другу в одной lane, global event order между lanes не обещан. Critical key — имя события.

try_emit=True означает admission, включая случай отсутствия подписчиков. Это не ACK запуска generation, обработки команды, commit или доставки Unity. emit возвращает None, rejection логирует; нет durable bus/replay. flush ждёт command/critical/ordered, BEST_EFFORT executor в его idle wait не включён. Shutdown перестаёт принимать и закрывает dispatchers с budget; timeout может discard pending. Restart переоткрывает каналы того же bus, сохраняя subscriptions; это не сохранение очередей между процессами.

SerialDispatcher ставит item в queue до increment _queued; worker может забрать/закончить его раньше increment. Возможен stale pending counter и ложный timeout wait_idle/drain. Это статический interleaving risk, не воспроизведённый runtime дефект. Также admission/close не являются общей transaction с предметными mutations.

Для проекта с нуля нужны явные outcomes accepted/started/succeeded/failed/cancelled/partial, ownership и cancellation propagation, source revisions для поздних effects, admission budgets, ordering scope, shutdown deadlines и судьба незавершённых operations. Долговечность отдельных команд определяется их предметным смыслом; не следует объявлять весь bus durable автоматически.
