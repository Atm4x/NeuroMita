# Каталог компонентов и установки

Capability CAP-INSTALL-001, ACTIVE/CONDITIONAL. Исследованы общий pipeline, очередь, статусы и основные maintenance операции. Компонентные планы всех моделей, manual package removal и весь progress parser ещё не закрыты. Ничего не устанавливалось/удалялось во время аудита.

## Пользовательские операции и каталог

InstallableOperations поддерживает install/uninstall/initialize; clean=true означает повторное скачивание/перестройку. Metadata доступна из декларативного manifest без импорта тяжёлой реализации. Lazy registry загружает implementation group только для status/settings/plan, запоминает group success/failure; invalidate component сбрасывает всю соответствующую loader group. Это полезное разделение shell readiness и работоспособности модели.

Статическая часть manifest включает backend CPU/CUDA/ONNX; TTS Edge/Silero+RVC CUDA/ONNX, OmniVoice, Fish Speech семейство medium/medium+/medium+low, F5 семейство high/high_clf5/high+low/high_clf5+low; пять ASR engines; beat_this; FFmpeg/OpenCV; все/индивидуальные character voice assets. Точный список здесь отражает ids, не подтверждение readiness каждой реализации. RAG-карточки добавляются из embedding/reranker presets, дополнительно активная custom HF model; aggregates rag:embeddings/reranker доступны для lookup без показа отдельными карточками. Локальный path не превращается в downloadable HF card. Каталог динамический, общее число не фиксировано.

ComponentStatus различает unknown/not_installed/installed/ready/needs_reinstall/backend_missing/failed, installed и ready отдельными bool. Compatibility — отдельный verdict supported/recommended/reason/warning/tags. Backend/vendor и manifest-specific compute rules могут запрещать install либо только показывать предупреждение. Эти проверки говорят о заявленной поддержке в текущем коде, а не гарантируют успешный inference.

## Status probes и settings

Catalog status key = component id + hash контекста: environment paths, hardware, language/model settings revision и прочие стабильные поля. Есть4 probe threads и2 async request threads. Общий wait budget default15s; timeout/stale/pending возвращают transient unknown, а не «не установлено». Поздний результат публикуется COMPONENT_STATUS, если поколение актуально. Invalidation повышает revision, отменяет/abandons старые probes. Failed outcome не кэшируется. Close убирает subscriptions/futures/cache; физическая остановка уже выполняющегося probe не гарантируется.

Settings schema/load работают по configurable component interface. Voice device schema расширяется из hardware snapshot; старые значения могут мигрироваться и сохраняться при load. Save нормализует setting behaviors, проверяет выбранные devices и component validation, возвращает ok/errors, затем invalidate. Schema/load errors логируются с fallback []/{}, поэтому потребитель может не отличить отсутствие настроек от сбоя по одному return value. В новой модели эти outcomes следует различить.

Install preview показывает required backend/packages/additional components/action descriptions и hardware. Actual plan строится при исполнении, с новым component context и ограниченным набором execution keys. Initialize отклоняется при missing_backend; отсутствие initialize plan превращается в «Nothing to initialize». Нельзя считать preview неизменным executable plan.

## Admission и очередь

InstallableController получает компонент, формирует runner/meta/task_id и обращается к InstallQueueService. Admission содержит accepted/task_id/duplicate/error и не равен завершению установки. FIFO queue сериализует все install/uninstall/initialize jobs, dedup выполняется по task_id среди running+pending. Queue без явного maxsize. Running cancellation ставит event, queued cancellation удаляет job; это разные эффекты. Queue pause/quiesce отвергает новые jobs, очищает pending, отменяет running и ждёт до deadline. Close отмечает worker stop и unregister services; полный drain обеспечивается отдельным maintenance flow.

В текущем production src единственный QueueService implementation — **InstallGuiController**, создаваемый optional GUI feature install. Его RUN_HEADLESS означает job без окна внутри этой очереди, а не автоматически доступный queue host в режиме приложения headless. При отсутствии queue InstallableController с with_ui=false пытается COMMAND event RUN_HEADLESS; отдельного headless subscriber rg не нашёл. Blocking InstallService.run_blocking существует отдельно. Это разрыв composition для будущей проверки, нельзя обещать одинаковую headless установку по названию event.

UI task_id группирует initialize и install в один ключ `component:install`; uninstall имеет отдельный ключ. Повтор может быть принят как duplicate без нового исполнения. Обязателен раздельный operation id и policy dedup в новом контракте, чтобы разные намерения не сливались случайно.

## Исполнение и окружения

InstallPlan содержит actions pip/download_http/call/call_async, backend requirement и environment flags. Actions выполняются по порядку; false/error останавливает plan. Cancellation проверяется между шагами и во время cooperative loops. Sync call не имеет принудительной общей deadline; call_async имеет timeout/cancel polling, но синхронная работа внутри coroutine способна задержать его. Defaults в install_types **7 200 000s total и3 600 000s no-activity**; единицы именно seconds, это не7200/3600. Не интерпретировать их как обычные короткие watchdogs.

Обычный managed install: определить active/probe-empty context → component plan → begin staging transaction → shared core layers → uv resolve/install overlay → component artifacts/actions → commit installed revision. Backend install регистрирует candidates; runtime activation и validation остаются до initialize. Dependency category отдельно проверяется import subprocess Python -S и подключается к main sys.path. Поэтому TASK_FINISHED для AI model означает установленные файлы, а не выбранную/загруженную модель. Подробнее [окружения](../03-runtime/ai-environments.md).

**Clean reinstall** сначала remove_installed прежнего окружения, затем строит новое с нуля. При последующей ошибке старый installed record уже удалён: rollback предыдущей работающей версии этой ветвью не гарантирован. Эта операция сознательно запрашивается в UI как удаление и повторная загрузка, но её нельзя смешивать с обычным transactional upgrade.

Uninstall для AI service берёт maintenance_session, останавливая workers до cleanup. Для managed overlay pip/environment_mutation actions исключаются: удаляется целый environment record/tree и отдельно artifacts. Main dependency деактивируется из sys.path; уже импортированный native module этим не выгружается. Удалённые overlays маркируются pending-delete/retired, registry/runtime selection очищаются; неудачное физическое удаление Windows допускает deferred cleanup. Shared core layers очищаются только по references/profile/candidates/installed requirements; это отдельная GC policy.

Registry recovery восстанавливает ready unregistered overlay без pending-delete/retired, выбирая newest mtime, если logical id отсутствует. Legacy ids мигрируются, включая ранее схлопнутые `+`. Это recovery структуры, не повторное доказательство inference совместимости.

## Downloads и external processes

download_http пропускает непустой dest, clean удаляет его перед скачиванием. HEAD оценивает размер, GET пишет .part, затем os.replace. Проверка checksum и точного Content-Length в этом generic path не найдена; component-specific validation может быть дальше. Cancellation удаляет .part; обычная HTTP/IO ошибка возвращает false и может оставить .part. Непустой final file сам по себе считается достаточным для skip.

PipInstaller использует приватный uv executable в .bootstrap/uv; embedded pip служит bootstrap uv, fallback resolver на pip отключён. Overlay сначала uv pip compile с core overrides/no-emit core packages, затем install --no-deps из temporary exact-version lock. Сохранение этого lock как долгоживущего artifact здесь не обнаружено. Immutable staging отделён от main Lib, protected constraints ограничиваются хрупким runtime stack. Утилита сама Python-код, но исполняемый uv — внешний package-manager backend; для Rust-host это потенциально самостоятельный процесс, не причина переносить Python installer классы.

Windows PTY используется для живого uv progress через pywinpty, иначе pipes; оба маршрута парсят text output и raw logs. PTY failure повторяет тот же command через pipes, включая неуспех раннера после cancellation/timeout — проверить, чтобы cancellation не стартовала второй процесс. Pipes terminate→wait0.5→kill относится к direct process; полного process-tree guarantee здесь не видно. Известные Windows locks допускают2 retries с задержками0.35/0.9s; disposable staging очищается перед повтором. Ошибка path materialization отдельно прекращает retries. Progress включает как фактические byte/task metrics, так и soft progress по выводу: процент не является точной долей durable work.

## Сброс всех AI окружений

DefaultAIEnvironmentMaintenanceService serializes reset operation lock и состояния validating→draining_installs→stopping_workers→deleting→reconciling→restarting→completed/failed. Queue quiesce≤30s, engine maintenance≤15s, затем reset managed storage, invalidate catalog, restart workers и resume queue. На ошибке queue пытается resume. Проверяются resolved environment root и owned subpaths, запрещены filesystem root/main Lib/core. Reset удаляет managed environment tree; scope model artifact directories вне него требует inventory компонентных планов. Аудит reset не запускал.

## Требования к новой архитектуре

Catalog metadata, compatibility policy, probe state, admission, execution result, installed revision и live runtime readiness должны иметь явные независимые контракты. UI только наблюдает/отправляет intents; очередь и environment ownership нужны и headless. Отмена обязана завершать operation outcome и сохранять проверяемый disk state. Поддержать clean rebuild как явно разрушительную операцию, обычный upgrade с сохранением previous revision, artifact validation и recovery после crash на каждой границе. Тяжёлые Python environment/package операции можно оставить за самостоятельным Python management boundary; точное разделение с Rust выбирать после проверки всех plans.

## Доказательства/пробелы

InstallController run_task/execute/download/uninstall/main validation и callbacks прочитаны; старые helpers проверки packages частично. InstallableController orchestration и admission; InstallGuiController queue/admission/cancel/quiesce/run/enqueue (не весь window plumbing). DefaultInstallableCatalogService основная metadata/status/settings/plan реализация, LazyInstallableRegistry, install_types/installables types/compatibility. RuntimeEnvironmentManager reset/migrate/recovery/remove и ранее transaction/composition. PipInstaller entrypoints/lock/uv bootstrap/process runners/cancel/deadlines/retry прочитаны, progress aggregator/metadata repair/manual uninstall не полностью. Полный model-specific download/license/security/compatibility audit ещё впереди.
