# Жизненный цикл необязательных функций

**Capability:** `CAP-RUN-005`. **Статус:** ACTIVE. **Домен:** capability availability. Источники E-010, E-012, E-018 из [индекса](../00-research/source-evidence-index.md). Функции внутри каждой регистрации требуют отдельных спецификаций.

## Назначение и сценарий

Не загружать все возможности заранее; запускать нужные по настройкам или явному запросу, сообщать готовность и освобождать ресурсы при отключении/выходе. Входы: registry specs, настройки, ensure request, shutdown. Выходы: Future результата создания и snapshot доступности. Состояние принадлежит RuntimeFeatureManager.

## Реестр из composition root

| Runtime name | Условие автоматического старта | Особые правила |
|---|---|---|
| telegram | USE_VOICEOVER и метод tg/telegram | Проверяет наличие telethon; TG_AUTOCONNECT/credentials отслеживаются, но сами не входят в enabled predicate |
| audio | USE_VOICEOVER | Требует pygame; shutdown удаляет sound files |
| local_voice | USE_VOICEOVER и метод local | stop_when_disabled=False |
| voice_models | Как local_voice | depends_on local_voice; stop_when_disabled=False; отслеживает LOCAL_VOICE_LOAD_LAST |
| speech | MIC_ACTIVE | Требует sounddevice; stop_when_disabled=False |
| capture | ENABLE_IMAGE_ANALYSIS и хотя бы один SCREEN/CAMERA/AUTO_ATTACH flag | Явный shutdown |
| reminders | REMINDERS_ENABLED, default True | Factory отдельного контроллера |
| embedding | RAG_ENABLED | EmbeddingService |
| reranker | RAG_ENABLED и RAG_CROSS_ENCODER_ENABLED | Явный shutdown |
| graph | RAG_ENABLED и GRAPH_EXTRACTION_ENABLED | Извлечение/хранение ещё не разобрано |
| install | Всегда разрешён | startup=False, только по запросу |
| installables | Всегда разрешён | startup=False, только по запросу |

Названия flags в таблице сокращены только для capture: точные ключи `ENABLE_SCREEN_ANALYSIS`, `ENABLE_CAMERA_CAPTURE`, `AUTO_ATTACH_IMAGES`. Default в predicate не доказывает default всей системы настроек.

## Модель состояний и входов

REGISTERED, DISABLED, LOADING, READY, FAILED, UNAVAILABLE, STOPPING, STOPPED, ABANDONED. `state()` и snapshot для REGISTERED вычисляют DISABLED/UNAVAILABLE по настройкам и наличию modules без обязательного изменения внутреннего entry.state.

`start_enabled` проверяет dependency DAG и планирует только startup+effectively enabled. `ensure_async` возвращает готовый instance, повторно использует loading Future или начинает новое поколение. STOPPING отклоняет запрос. Missing required modules даёт UNAVAILABLE до factory; неизвестное имя/закрытый manager/DAG cycle возвращают failed Future.

Важно: enabled управляет автоматическим стартом. Явный ensure технически может запустить factory и при disabled. Если stop_when_disabled=True, результат затем уничтожается и может вернуть None. При False explicit ensure может оставить функцию READY даже при enabled=False. Новый контракт должен явно различать эти случаи, а не считать None успешной готовностью.

## Правила зависимости и конкурентности

Dependency factories не ждут друг друга внутри занятого executor thread: Future callbacks образуют barrier, после готовности зависимостей задача ставится в executor. Это поддерживает DAG даже при одном worker. Реальный composition root использует max_workers=2. Нет декларации взаимозависимости всех смежных функций; проверена только явно заданная voice_models→local_voice.

Одновременные ensure во время LOADING разделяют public Future. Поколение меняется при новом load и abandonment на shutdown. После factory проверяются generation, stop_requested, closed и settings; устаревший instance уничтожается вместо публикации. Provided services публикуются под lock через owner-safe registration handles. При ошибке частичной регистрации handles закрываются, instance останавливается, entry становится FAILED.

## Изменение настроек, остановка и повторный запуск

Изменение relevant key затрагивает функцию и транзитивных dependents. Enabled entries в REGISTERED/DISABLED/FAILED/UNAVAILABLE/STOPPED планируются заново. Для disabled LOADING выставляется stop_requested; READY переводится в STOPPING, закрытие выполняется в обратном dependency order. Если настройка снова включена за время stop, после завершения запускается ensure заново.

Manager.shutdown идемпотентен, закрывает settings subscription, помечает loading entries ABANDONED с новым поколением, ready entries останавливает в обратном topological order, затем закрывает executor с cancel_futures. Поздние factory физически могут ещё выполняться: abandonment предотвращает публикацию, но не является принудительной остановкой вычисления.

Для instance снимаются EventBus subscriptions, отменяются owned tasks (timeout 1 s), вызывается spec.shutdown либо первый доступный shutdown/destroy/close/stop. Registration handles закрываются отдельно и не должны снять заменивший их service.

## UI, ошибки и побочные эффекты

Snapshot: state, enabled, depends_on, error string, missing_modules, generation. Конкретные места отображения будут установлены при GUI audit. Factory может запускать потоки/модели, создавать файлы, подписывать события; эти эффекты принадлежат отдельным capabilities. Failure одной optional factory не отменяет автоматически весь обязательный runtime.

## Требования к реализации с нуля

- Различать configured, installed, available, starting, ready и stopping; это независимые характеристики.
- Иметь единственного владельца создаваемого ресурса и его фоновых задач.
- Сохранять dedup loading, запрет поздней публикации и остановку dependents первыми.
- Определить явный результат запроса, проигравшего гонку с disable/shutdown.
- Дать наблюдаемую ошибку недоступной зависимости.
- Не переносить строковые service names, global service locator и runtime reflection автоматически.

Rust alternatives пока не выбраны. Будет сравнение обычных owned services с задачами и каналами против actor-подхода после выяснения фактической потребности в сериализации команд. Generation — идентификатор актуальности операции; он не заменяет ownership и cancellation.
