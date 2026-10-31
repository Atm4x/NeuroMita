# Локальное управление приложением через JSON IPC

**Capability:** CAP-IPC-CTRL-001. **Статус:** CONDITIONAL, RUNTIME_IPC_ENABLED default False. Это отдельный loopback control endpoint, не Python AI worker transport и не game socket.

MainController создаёт DefaultRuntimeIPCService и регистрирует AIEngineController. GUI general section включает endpoint и задаёт порт; изменения enable/port сразу останавливают/перепривязывают server. Default127.0.0.1:47831; GUI разрешает1024—65535, backend также поддерживает0 для dynamic port. Bind failure отражается в status.last_error, повторная автоматическая retry policy не обнаружена.

Функции: ipc.ping, ipc.status, ipc.methods, hardware.snapshot(refresh), ai.topology и ai.restart_service(service,timeout). Последнее имеет прикладной эффект: перезапуск tts/asr/rag/beats через AIEngineController, с проверкой runtime switch. Иные методы объекта не становятся доступны автоматически: registry сканирует только явно декорированные @ipc_allowed descriptors, duplicate registration отклоняется.

Protocol: одна UTF-8 JSON line на connection, до1 MiB, socket read timeout10 s. Request id/method/params, params null/object/list; response id/ok/result либо error code/message. Object/list непосредственно превращается в keyword/positional callback arguments, полноценного typed schema validation в registry нет. Неподдерживаемый method, params type, invalid request, runtime и serialization errors различаются. Awaitable callback исполняется asyncio.run в request thread.

Server — ThreadingMixIn/TCPServer с daemon request threads. Штатный stop закрывает listener и ждёт serve thread до2 s; это не подтверждение окончания всех уже запущенных method calls. Auth token в этом endpoint не реализован; область доступа ограничена loopback и allowlist, а не идентичностью вызывающего локального процесса. Admission cap/rate limit/request execution deadline в прочитанном сервере не найден. Это факты контракта для нового design, endpoint не запускался.

Новая реализация должна определить допустимый каталог управления, typed arguments/result, связь endpoint lifecycle с выполняющимися operations и общие budgets. Существующий Python reflection/decorator registry — один механизм регистрации, не требование к Rust. Возможность локального управления и диагностики должна учитываться отдельно от необходимости поддерживать multiprocessing Python values внутри AI worker.

Источники: core/runtime_ipc.py и services/runtime_ipc_service.py целиком; MainController registration/shutdown; AIEngineController decorated restart_service; GUI general IPC controls. Test files найдены, не запускались; сетевых запросов и перезапусков workers не было.
