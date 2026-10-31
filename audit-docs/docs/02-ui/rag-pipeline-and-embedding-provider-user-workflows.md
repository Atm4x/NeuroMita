# RAG: пресеты поиска, провайдеры эмбеддингов и пользовательская готовность индексов

**Scope:** CONDITIONAL RAG user workflows на странице настроек моделей; фактические source locations из Python releases. **Разделять:** 1) профиль алгоритма поиска, 2) провайдер/модель embeddings, 3) наличие установленных весов, 4) построенность индекса, 5) загрузку embedding/reranker worker, 6) включённость автоматического RAG при генерации. Это независимые состояния.

## Пресеты поискового конвейера

`RagPresetWidget` отображает список предустановленных и пользовательских профилей, Select/Apply/Save As/Delete. `src/ui/settings/rag_preset_widget.py:34-185`, `src/controllers/gui/rag_preset_view_model.py:41-246`. `RAG_PIPELINE_PRESET` хранит выбранное имя; пользовательские профили сериализуются JSON под `RAG_PIPELINE_USER_PRESETS`. Встроенные names приходят из `RAG_PIPELINE_PRESETS` в `src/managers/rag/pipeline/config.py`; `Custom` представляет текущее ручное состояние, не сохраняемый builtin-профиль.

**Выбор имени ≠ применение настроек.** Select меняет selected key; Apply требует отдельного подтверждения, поскольку перезапишет активные RAG settings. Диалог предлагает (a) применить, (b) сначала сохранить текущий набор под новым именем и применить, (c) отменить. Save As делает snapshot текущих `RAG_DEFAULTS` и сохраняет пользовательский профиль; builtin/Custom overwrite запрещён. Delete допустим только для user preset, после удаления selected возвращается `Custom`. Источники: `rag_preset_view_model.py:58-217`; `rag_preset_widget.py:90-172`.

При Apply активные settings обновляются по ключам выбранного пресета, при изменении model/query-prefix выполняется sync legacy embedding settings→preset, затем асинхронно проверяются отсутствующие модели (`rag_preset_view_model.py:169-202`). Если веса отсутствуют, появляется отдельное предложение добавить необходимые targets в очередь; отказ от скачивания не откатывает уже применённый профиль (`:218-239`). Реальные install targets и readiness детализированы в [installables](../01-functional/installable-catalog-and-runtime-readiness-matrix.md). Не путать selection, profile applied, model installed, index built, worker warm.

## Провайдер эмбеддингов

Для embeddings есть **собственный каталог пресетов**, отличный от LLM API presets и RAG pipeline profiles. Типы: `local` (HF/локальный путь), `openai_compat` (совместимый API), `gemini` (Google API). Выбираются model id/name, при необходимости ручной HF id/path, endpoint/credential/reserve keys/query prefix; доступны add/delete/reorder/save/test/download (`src/ui/settings/embed_provider_settings.py:48-165,328-715`; `src/controllers/gui/embed_provider_view_model.py:27-411`). Stable provider_type и preset ID не должны зависеть от переведённых названий в combo.

`ActivateEmbedProvider` загружает выбранный `RAG_EMBED_PRESET_ID` (default `local_hf`), список пресетов может прийти из prefetch cache либо async source (`embed_provider_view_model.py:67-153`). Select выполняет асинхронный config load с generation protection; для local preset отдельно запрашивает известные модели, downloaded flag и текст статуса индекса. Успех выбора записывает `RAG_EMBED_PRESET_ID`, обновляет displayed config/index status (`:154-218`). Здесь **смена выбранного embedding preset** не равнозначна немедленной полной переиндексации существующих vectors.

Save формирует payload с model/url/key и другими полями, сохраняет `HF_TOKEN` отдельно и вызывает repository save; Add создаёт пустой local preset; Delete запрещён для builtin string IDs (допустим custom numeric); Reorder применяется к пользовательским IDs (`embed_provider_view_model.py:220-300`). Test публикует `EMBEDDING_PRESET_TEST` и ждёт коррелированный `EMBEDDING_PRESET_TEST_RESULT` по ID с UI timeout 30s (`:301-388`). Этот timeout означает отсутствие UI outcome, не доказательство отмены HTTP/inference. Download сначала сохраняет выбранный config/токен, затем вызывает download через RAG service; это отдельная операция от Test и от Index (`:326-349`).

`EmbedProviderWidget` умеет по-разному показывать local-only поля (manual path/download) и remote-only поля (URL, key), скрывать видимые credentials, открывать ссылку на получение ключа, помечать dirty при редактировании. В дальнейшем нужно зафиксировать точные persistence semantics key/credentials отдельно от визуальной маски; см. [settings/secrets](../01-functional/settings-storage-and-migrations.md).

## Индикация готовности и установочных целей

`RagInstallState` хранит **отдельно** target embeddings и reranker: `backend`, `index`, `model`, `loaded`, `button_visible`, `button_busy`, `loading` (`src/ui/settings/rag_install_presentation.py:8-44`). `RagInstallViewModel` получает cached/forced statuses, открывает AI Hub на соответствующей цели, реагирует на installable finish и `RAG_INDEX_CHANGED`, инвалидирует кеш и refresh (`src/controllers/gui/rag_install_view_model.py:20-154`). Это не один общий флаг `RAG_READY`.

Отдельные кнопки действий страницы запускают reindex embeddings, graph extraction, TTL/GC и graph visualization, со своими progress/confirmation; точки регистрации и действия `src/controllers/gui/rag_memory_controller.py:133-667,1057-1837`. Важно различать: установка model files, генерация embeddings для истории, обновление FTS, графовая экстракция, GC и подбор retrieval результатов — разные пользовательские операции. Пользователь может выбрать cloud embedding и не скачивать локальные веса.

## Core boundaries по функциям (без проектирования Rust)

- Настройка/валидация профиля и отображение статуса — presentation/application; извлечение vectors и cross-encoder inference остаётся Python AI.
- Ranking/query building, FTS/SQL storage, filtering и связывание результатов с историей — функциональность Core, не AI модель (см. [RAG pipeline](../01-functional/rag.md)).
- Состояния `saved settings`, `model installed`, `worker loaded`, `index up-to-date`, `query result`, `RAG_ENABLED` имеют разные ключи/источники и разные проверки. Не выводить результат одного из другого.

## Сценарии проверки паритета

Просмотреть builtin/custom profiles; Save As и запрет перезаписи builtin; Select without Apply; Apply с отменой/сохранением текущих; изменение выбранной embedding-модели и предложения скачать missing assets; локальный/удалённый provider; ручной HF путь; test success/failure/timeout; cache-prefetched view; add/delete/reorder; AI Hub переход на embeddings/reranker; готовность weights vs index vs worker; переиндексация после смены model; error/network/cancel.

**Не проверено:** реальные HF downloads, cloud provider calls, долгоживущие worker sessions, GUI E2E, полнота всех numeric RAG settings и визуальных элементов. Подробная техническая RAG поисковая семантика изложена в `01-functional/rag.md`, здесь только user interactions/state projections.
