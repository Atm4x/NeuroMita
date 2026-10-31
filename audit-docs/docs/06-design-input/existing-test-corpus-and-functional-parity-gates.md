# Действующие тестовые свидетельства и проверка функционального паритета

**Статус:** inventory (static source discovery), не утверждение о том, что тесты пройдены на этой машине. **Цель:** показать следующему аудитору и автору Rust Core 2.0, *какие уже сформулированные пользовательские сценарии и протокольные гарантии можно взять как исходные наблюдаемые контракты*. Файлы тестов — дополнительные доказательства ожидаемого поведения, но не подтверждение production reachability сами по себе.

## Размер и границы инвентаря

В `src/utils/Testing/` обнаружены **250** файлов с именем `test_*.py`. Регулярным поиском определений `def test_`/`async def test_` (включая методы внутри классов) обнаружены **2177** синтаксических определений. Это **не** число реально собранных/пройденных pytest-test cases: параметризация, skips, fixtures, conditional imports и внешняя среда меняют фактический объём. Источники: `src/utils/Testing/test_*.py`, локальный снимок Python-релиза, без запуска всего набора.

Исследованный корпус содержит как `unittest`, так и `pytest`, импорты GUI/PyQt6, внешних audio/OS adapters, подмены HTTP/worker, локальные SQLite и deterministic stubs. Поэтому **достоверная тестовая гарантия** требует отдельно указывать платформу, feature flags, зависимости и исполняемый fixture; название теста не является доказательством его успешного прохождения.

## Маршруты, где уже существует проверочный материал

| Домен | Конкретное существующее свидетельство | Проверяемый контракт для новой реализации | Чего это пока не доказывает |
|---|---|---|---|
| Диалог и контекст | `src/utils/Testing/test_chat_request_pipeline.py`, `test_chat_api.py`, `test_local_message_pipeline.py`, `test_context_counter.py` | Приём сообщения, подготовка контекста, routing, статус выполнения, подсчёт контекста | Живые ответы поставщика и реальные лимиты тарифа |
| Structured effects и intents | `test_structured_response_capabilities.py`, `test_sparse_structured_response.py`, `test_structured_response_intents.py`, `test_intent_view_model_runtime.py` | Доступность полей согласно runtime, разбор разреженного ответа, событие/проекция эффекта | Реальное выполнение каждого эффекта в Unity |
| Transport/API providers | `test_llm_http_transport.py`, `test_openai_schema_compat.py`, `test_gemini_message_order.py`, `test_api_endpoint_policy.py` | Сборка запросов, HTTP и schema adapter, порядок сообщений | Полный conformance удалённых OpenAI/Gemini/ChatGPT Plan API |
| История/память | `test_history_manager_atomicity.py`, `test_history_epoch_guard.py`, `test_character_history_clear.py`, `test_memory_dedup.py`, `test_memory_islands.py` | Идентичность, сброс/сжатие, дедупликация, раздельность персонажей | Одна сквозная транзакция SQLite + граф + embeddings |
| RAG / retrieval | `test_rag_search_golden.py`, `test_rag_units_golden.py`, `test_rag_reindex_batch_size.py`, `test_gemini_embedding_provider.py` | Pipeline с фиксированным порядком, перевод векторов, batch-индексация, wire эмбеддингов | Семантическое качество реальных моделей; в `test_rag_search_golden.py` используется нарочито детерминированный fake embedding, не production inference |
| Персонажи и игровые события | `test_character_game_state_isolation.py`, `test_dialogue_sender_identity.py`, `test_game_master_target_resolution.py`, `test_world_character_context.py` | Actor identity, target, status/world projection, GM | Модовая анимация и настоящие Unity scene effects |
| Unity TCP / session | `test_multimita_live_socket.py`, `test_unity_dialogue_routing_boundary.py`, `test_unity_retry_store.py`, `test_player_message_source.py` | Client ownership, game request admission, delivery replay и источник sender | End-to-end результат в действующей сборке Unity |
| AI Engine supervisor | `test_ai_engine_runtime_switch.py`, `test_ai_worker_admission.py`, `test_ai_environment_switching.py`, `test_worker_environment_paths.py` | Конфигурация shared/split, запуск, отмена, пути окружений | Установка реальных CUDA/TTS моделей |
| Установка и AI Hub | `test_installable_catalog_loaders.py`, `test_installable_catalog_service.py`, `test_ai_hub_queue_admission.py`, `test_install_on_demand_contract.py` | Каталог, readiness, admission, очередь, lazy plan | Реальная загрузка весов и Windows DLL/E2E |
| Конкретные AI-пакеты | `test_f5_tts_installables.py`, `test_fish_speech_installables.py`, `test_omnivoice_installables.py`, `test_edge_tts_rvc_installables.py`, `test_opencv_installables.py` | Контракт планов установки, идентификаторов и статусов | Исполнение моделей и лицензии поставщиков в конкретной версии |
| Голос/ASR | `test_asr_ptt.py`, `test_asr_session_routing.py`, `test_speech_reconciler.py`, `test_remote_voice_delivery.py` | Session ownership, push-to-talk, синхронизация речи и доставка | Реальное устройство ввода/вывода и качество распознавания |
| GUI и локализация | `test_sandbox_page_controller.py`, `test_ai_hub_progress_rendering.py`, `test_db_viewer_character_filter.py`, `test_localization.py` | Состояние view/UI actions, локализованные подписи, фильтры | Скриншотная/ручная визуальная проверка всех экранов |
| Release и launcher | `test_release_contract.py`, `test_launcher_bootstrap.py`, `test_distribution_metadata_stamp.py`, `test_release_assets.py` | Обязательные файлы артефакта, пути запуска, версия/метаданные | Подлинная установка/апгрейд полной поставки на Windows |
| Runtime и управление ресурсами | `test_task_supervisor.py`, `test_runtime_features.py`, `test_async_runner_lifecycle.py`, `test_shutdown_paths.py` | Порядок регистрации/остановки, lifecycle задач, условный feature start | Стресс-тесты потоков, пользовательская отмена во всех UI сценариях |

Все указанные имена относятся к фактически присутствующим файлам исходного снимка. Таблица — **маршрут аудита**, а не заявление, что перечисленные тесты одинаково полезны, актуальны или проходят. Наличие тестов на старые проблемы не превращает дефект в требование к новой версии.

## Перенос тестовой идеи, а не Python fixture

1. Для каждой `CAP-*` определять **наблюдаемый вход и результат** на границе сервиса: сообщения диалога, task status, сохранённые записи, readiness probe, события GUI, Unity packet.
2. Сохранять отдельно deterministic contract tests (JSON/identities/state transitions), component tests (SQLite/temp FS, fake worker), и внешние acceptance tests (Windows + GPU + Unity + Telegram/API). Не смешивать fake-inference с качеством реальной модели.
3. Сопоставлять `source → capability → requirement → future parity fixture` в `feature-traceability.md`; старый `test_*.py` указывать как **reference evidence**, а не как тест, который Rust должен запускать неизменным.
4. Прежде чем объявлять область `PRIMARY`/закрытой, проверить reachable production path через регистрацию и потребителя; наличие unit-теста не заменяет эту проверку.

## Открытые вопросы

- Какие тесты из корпуса сейчас запущены на CI, какие пропущены или зависят от живой инфраструктуры? Нужен discovery конфигурации запуска и фактическая статистика test collection.
- Какие публичные сетевые контракты допускают golden record/replay без раскрытия авторизационных токенов?
- Для Unity, hardware, CUDA, Windows и Telegram живые fixtures отсутствуют в текущем offline audit; сроки и среду для их проверки нужно определить отдельно.
- Для истории/графа/RAG важно проверить *функциональный сценарий восстановления данных*, не копируя сегодняшние внутренние SQL/таблицы буквально.

## Локальные проверки этого 30-минутного прохода

Запускались через `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `python -m pytest -q -p no:cacheprovider` (без сетевых/аппаратных тестов, исходники не редактировались):

| Набор | Наблюдение | Что подтверждает / не подтверждает |
|---|---|---|
| `test_message_content_codec.py` + `test_performance_trace.py` | **14 passed** | Контрактные преобразования content и process-local trace unit logic в этой среде; не LLM/GPU/GUI parity |
| К этим двум добавлен `test_mini_game_public_context.py` | **18 passed, 1 failed, 2 subtests passed** | Часть публичной проекции работает; один тест ожидает `miss` при payload `{"coord":"B4","message":"miss"}`, а source извлекает `result_code` именно из поля `result`, поэтому публикует `shot`. Краткое наблюдение несовпадения fixture и текущего producer, без расследования исправления |
| Четыре файла, включая `test_performance_trace_integration.py` | collection blocked: `ModuleNotFoundError: pygame` | Весь integration набор в этой среде не собран; нельзя называть его пройденным |

В новом функциональном проекте критичен *смысл* public event (координата/исход попадания), а не автоматический перенос ожидания старого unit-теста. Runtime producer должен иметь явно заданный контракт полей `result` и `message`, после чего golden-fixture можно обновить уже в проекте Rust.

## Контрольный запуск проверки dialogue identity

Проверен набор `test_dialogue_sender_identity.py`, `test_dialogue_target_resolution.py`, `test_conversation_event_writer.py`, `test_live_dialogue_echo_identity.py` в том же offline окружении без изменения source: **16 passed, 2 failed**. Оба failed относятся к ожиданию отсутствующего в текущем `ModelController` метода `_canonicalize_structured_targets` в `test_dialogue_target_resolution.py`; это свидетельствует о несоответствии части тестового интерфейса текущему снимку, но **не доказывает дефект пользовательского runtime**. Ни source, ни тесты не исправлялись. Для Rust parity сохраняется функциональное требование однозначного target resolution, а не необходимость переноса устаревшей функции Python. [Семантика идентичности](../01-functional/dialogue-actor-and-message-identity-contracts.md).

**Дополнительный таргетированный запуск streaming:** `test_llm_http_transport.py -k 'presentation_coalescer or presentation_flush or presentation_close'` — **4 passed, 34 deselected** (в этом файле; без реального внешнего HTTP). Подтверждает локальные свойства batching, flush barrier и close timeout в описанной тестовой среде. [Контракт stream](../03-runtime/llm-stream-event-and-presentation-lifecycle.md).
