# Установщик: транзакции, отмена, удаление и восстановление

**Область:** Python Core installer orchestration, не AI inference. **Метод:** статическое чтение исходников из `CodeNow.zip` (releases revision заявлена как `38172493fa0d1caf1a5225bc1c559f095f18bb7a`, но Git metadata в ZIP нет). Установка/удаление пакетов и моделей в этом проходе не выполнялись.

## CAP-INSTALL-LIFECYCLE — жизненный цикл задания установки

**Статус: ACTIVE / CONDITIONAL** (конкретное действие зависит от выбранного installable и настроек среды). **Основные источники:** `src/controllers/install_controller.py:1141-1501` (`run_task`), `:896-1140` (`_execute_plan`), `src/core/runtime_environments.py:453-670` (`EnvironmentTransaction`).

- Вход: `task_id`, runner, `meta` (`kind`, `item_id`, `op`, `clean`), callback, timeout, `threading.Event` для отмены. Runner возвращает `InstallPlan`, словарный эквивалент или результат, приводимый к `bool`.
- Состояние: начальный logical environment → staging transaction → resolved overlay → actions → committed manifest/registry → validation/activation → finalize. При ошибке до commit вызывается `abort`, при провале валидации основного окружения — `rollback_commit`.
- Установка с управляемым окружением вычисляет зависимости и общие backend layers отдельно. `install_environment_lock` разворачивает решённый пакетный набор в staging, `_execute_plan` выполняет остальные шаги; `commit` формирует ревизию, накапливает manifest и регистрирует её (`install_controller.py:1356-1436`, `runtime_environments.py:534-629`).
- Важное исключение: категория `backend` после успешных actions регистрирует только кандидатов shared backend layers и **отменяет overlay transaction**, а не публикует его как обычный feature environment (`install_controller.py:1407-1416`).
- `plan.already_installed` позволяет пропустить операции при `!clean` и наличии активного managed environment (`:1333-1342`). Для обычного `_execute_plan` пропуск возможен лишь если нет backend actions (`:924-928`).
- `clean=True` при managed install сначала **удаляет существующее environment**, затем начинает новую staging transaction (`:1345-1355`). Это не симметрично обычному atomic replace: при последующей ошибке прежнее environment уже отсутствует. Новому приложению нужен явно сформулированный контракт clean reinstall, а не предположение, что rollback вернёт прежнюю версию.
- В `run_task` три терминальных маршрута: `TASK_FINISHED` (`:1458-1460`), `TASK_FAILED` при возврате False (`:1462-1469`) и `TASK_FAILED(cancelled=True)` при `InstallCancelled` (`:1471-1480`). Exception path также шлёт `TASK_FAILED` (`:1482-1491`). `cb_progress`/`cb_status` могут отправлять несколько `TASK_PROGRESS` для одной логической фазы (`:1166-1200`). События несут task ID/meta/operation details; ошибка теряет объект исключения, публикуя текстовое поле.

### Action vocabulary

`InstallAction.type` допускает исполняемые ветви `pip`, `download_http`, `call`, `call_async` (`install_controller.py:948-1138`). Неизвестный тип приводит к `Failed`; `call` принимает callable с гибкой адаптацией аргументов; `call_async` запускается в собственном event loop через `asyncio.run` и polling до deadline (проверка отмены каждые ~0.1 s; `:1074-1119`). `call` не получает такого общего deadline: `_run_with_heartbeat` лишь обновляет видимый статус, поэтому `timeout_sec` нельзя трактовать как жёсткий timeout любой операции.

**Побочные эффекты:** процессы pip/uv, файловая staging/overlay/registry, HTTP downloads, модели, backend registration, процессная maintenance session. **Наблюдаемость:** `InstallCallbacks` (`progress`, `status`, `log`, optional `raw_log`), события `Events.Install`, журналы.

## CAP-INSTALL-CANCEL — отмена установки

**Источники:** `src/controllers/install_controller.py:1283-1302, 1471-1501, 555-603`, `_execute_plan` на `:937, 1060-1119`; `src/utils/pip_installer.py` (`cancel`, процессная установка); `src/core/runtime_environments.py:665-670`.

`run_task` поднимает отдельного watcher через `task_supervisor().start_thread`: при установке `cancel_event` вызывает `cancel()` у всех `PipInstaller`, созданных внутри task; watcher завершается после `task_finished` и имеет `join(timeout=0.5)`. Сам план проверяет cancel перед каждой action, асинхронная action периодически; HTTP downloader проверяет событие между файлами и chunks. При `InstallCancelled` staging transaction abort, task emits `cancelled=True`. **Не следует обещать мгновенную отмену произвольной синхронной `call`:** эта ветвь вызывает внешнюю callback синхронно; реальная кооперативная отмена зависит от её кода. В документе `installer-component-plans.md` уже отмечены отдельные download/compile path, их поведение необходимо проверять индивидуально.

## CAP-INSTALL-HTTP — загрузка ассетов

**Источник:** `src/controllers/install_controller.py:476-614` (`_download_http_files`).

- На входе URL+destination, необязательные HTTP headers, progress interval, `force`, cancel event. Existing `dest` с ненулевым размером пропускается, если `force=False`. Это **не проверка валидности файла** и не гарантия idempotency по checksum.
- Сначала HEAD для `Content-Length` (30 s timeout), затем GET (60 s timeout на операции чтения), запись в `dest + '.part'`, `os.replace` после завершения GET; HTTP failures возвращают False. Часть обработчиков ошибок оставляет `*.part` при обычном HTTPError/Exception; `InstallCancelled` удаляет `*.part` (`:598-611`). Повторная попытка открывает `.part` через `wb`, перезаписывая его.
- Progress использует отношение байт, только если длины **всех** объектов известны; иначе progress по числу имеющихся конечных файлов (`:526-553`). При неизвестных длинах процент не отражает скачанные байты.
- При `force=True` существующий destination сначала удаляется, прежде чем новый файл гарантированно скачан (`:496-504`). Следовательно clean download допускает промежуточное отсутствие ранее работавшего ассета.

## CAP-INSTALL-UNINSTALL — удаление model environment

**Источники:** `src/controllers/install_controller.py:788-867` (`_uninstall_plan`, `_artifact_cleanup_plan`), `src/core/runtime_environments.py:1244-1308` (`remove_installed`).

- Для категорий AI service берётся maintenance session, если сервис администрирования доступен; при его отсутствии и наличии работающего engine — явная ошибка, если engine отсутствует — продолжение без session (`:792-810`). Это важно для открепления DLL и активных workers.
- Для managed environment cleanup-plan **отфильтровывает pip actions и `environment_mutation`**, выполняет только artifact cleanup, затем деактивирует main environment, удаляет environment registry/revisions и забывает active worker runtime (`:807-831, :848-866`). Для unmanaged installable `_execute_plan` выполняет исходный uninstall plan, включая pip, если он присутствует.
- `remove_installed` сначала снимает registration/runtime selection под lock, расставляет `.pending-delete` (или `.retired`), записывает registry атомарно, затем физически удаляет revision tree. При Windows locked DLL неудачное `rmtree` переводится в marker-based deferred deletion (`runtime_environments.py:1244-1308`). Return `True` означает удаление registry/невозможность повторного выбора, **не обязательно немедленное удаление всех байтов**.
- Если удаление managed environment падает после cleanup ассетов, автоматический возврат удалённых ассетов не прослеживается. Main process environment при исключении `remove_installed` восстанавливает activation попыткой (`install_controller.py:817-827`), но не является универсальной транзакцией удаления всех файлов.

## CAP-PIP-REMOVAL — старый unmanaged package removal

**Источники:** `src/utils/pip_installer.py:830-926` (`uninstall_packages`), `:927-1012` (`_collect_removal_targets`), `:1041-1095` (`_rmtree_with_retries`, `_manual_remove`).

- `include_dependencies=True`: recursive dependency tree **минус protected dependency closure**. `False`: только явно перечисленные дистрибутивы; нужен для shared dependencies. Вызывающий должен гарантировать эксклюзивность выбранных пакетов.
- Если пакет имеет `RECORD`, для uv используется uninstall; при ошибке или отсутствии RECORD есть ручной file removal. Если `RECORD` позволяет, удаляются **точные файлы**, чтобы не снести соседей в общем namespace; если нет — по `top_level.txt`, затем нормализованному package name, что менее безопасно.
- Абсолютные target paths ограничены целевым Lib root, но при отсутствии `RECORD` полная принадлежность namespace каталога не доказуема. Удаление retry 0.5/1/2/3/5 s, выгрузка `sys.modules` и GC; повреждённые dist-info в staging ремонтируются отдельно.
- В `uninstall_packages` при неуспешном удалении непрямой зависимости ошибка записывается в `dependencies_failed`, но удаление может всё равно считаться успешным, если удалены основные пакеты (`:905-925`). Это осознанная best-effort semantics, которую не следует переносить как строгую guarantee.

## CAP-INSTALL-REPAIR — repair без порчи живых окружений

**Источник:** `src/utils/pip_installer.py:1110-1173` (`repair_broken_target_metadata`).

Проверка ограничена путями с `.staging`, `.install-staging` или `.core-staging-*`: активные immutable environments не мутируются. Удаляется dist-info с отсутствующим или пустым METADATA; OSError при чтении рассматривается как transient lock, а не доказанное повреждение. Для недавно созданного dist-info есть короткий повтор чтения (0.25 s). Далее `:1175-1200` предусмотрены предупреждения о OneDrive и non-ASCII пути. **Семантическая гарантия:** не исправлять потенциально здоровые активные версии посредством destructive repair.

## Минимальные обязательные функциональные контракты для новой реализации

- `REQ-INSTALL-LIFE-001`: единый идентифицируемый task с прогрессом, фазами, логом, terminal status, error и отдельным terminal cancellation.
- `REQ-INSTALL-LIFE-002`: staging/validation/publish для managed environments и отказ без порчи прежнего окружения **при обычном обновлении**; clean reinstall должен иметь явно заданную иную семантику.
- `REQ-INSTALL-LIFE-003`: разделение package environment, shared backend, downloads, пользовательских ассетов и registry publication; не смешивать package uninstall и artifact cleanup.
- `REQ-INSTALL-LIFE-004`: кооперативная отмена actions и процессов, учёт non-cancellable side effects и промежуточных `.part`.
- `REQ-INSTALL-LIFE-005`: удаление registry/references отдельно от физической cleanup и deferred deletion на Windows; корректность при файлах, заблокированных DLL/антивирусом.
- `REQ-INSTALL-LIFE-006`: repair повреждённого staging без модификации активных immutable environments; explicit checksum/size policy для downloaded assets.

**Возможная переорганизация (не выбор архитектуры):** формально выделить task state и outcomes, package environment transaction, artifact lifecycle, controlled cancellation и progress reporting как разные функциональные контракты. Нынешние `InstallController` / `PipInstaller` — доказательства, не предписанные будущие Rust-типы. **Rust alternatives:** выбор механизмов supervision, atomic filesystem/publish и cancellation отложен до отдельного technology research; кандидаты нельзя фиксировать без платформенных тестов.

## Открытые вопросы / предел доказательств

1. Реальное поведение `call` installables при отмене/timeout и при падении после частично скачанных моделей — проверить по каждому component callback.
2. Обязательность успешного завершения cleanup ассетов при uninstall (например, RAG noop и voice false-return) — необходимы explicit policy и тесты.
3. Crash-recovery во время `os.replace` и registry update на Windows + OneDrive; существуют recovery helpers в `runtime_environments.py`, но disaster scenarios не прогнаны.
4. Race при одновременных install/clean/uninstall одного logical ID — concurrency locking и task GUI queue проверить отдельно.
5. Lifecycle внешних моделей, которые не принадлежат managed environment, не следует считать полностью транзакционным.

**Уверенность:** CONFIRMED — перечисленные ветви в конкретных функциях; INFERRED/RISK — возможные последствия при отказах. Динамические инсталляции, удаление, DLL locks и антивирус не воспроизводились.
