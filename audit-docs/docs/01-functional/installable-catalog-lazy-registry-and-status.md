# Каталог устанавливаемых компонентов: metadata, lazy loading, readiness

**Срез:** извлечённый `CodeNow.zip`, 2026-10-30, без `.git` SHA. **Статус:** `ACTIVE/CONDITIONAL`. Аудит исходников, НЕ реальная установка моделей. Этот документ описывает только каталожную часть, а не исчерпывающую проверку скачивания и запуска каждой модели.

## CAP-INSTALL-CATALOG-001 — два этапа обнаружения

`src/installables/catalog_manifest.py:18-40,908-1059` формирует `InstallableCatalogEntry` с ID, локализованным описанием и адресом фабрики; часть RAG-карточек формируется из model presets при импорте, а активная нестандартная карточка — динамически по текущим настройкам. `rag:embeddings` и `rag:reranker` добавляются в индекс для lookup, но явно исключены из визуального набора карточек. `catalog_entries()` отражает динамический custom model, а обратносуместимый `CATALOG_ENTRIES` содержит статический импортный snapshot.

`src/installables/registry_builder.py:13-176` откладывает `importlib.import_module` до `get`, `require`, `all`, `by_category`. Один `loader` может вернуть группу компонентов. Внутри защищённых `RLock` множеств находятся загруженные, загружаемые и провалившиеся группы. Только первый caller вызывает loader; остальные ожидают `threading.Event`. Если фабрика падает, `_failed_groups[loader]` запоминает ошибку: простой последующий `get` не повторит импорт до `invalidate`/создания нового registry. `get` возвращает `None` при ошибке; `require` поднимает `RuntimeError` с первопричиной (для неизвестного ID — `KeyError`). Указанное относится к loader failure, а не к любой install failure.

`src/services/installable_catalog_service.py:360-369` различает обычный `require_component` и `refresh`, который заменяет глобальный lazy registry целиком. `:526-550` service `invalidate` сбрасывает status entries по ID, ревизии, inflight probe claims и группу lazy registry; далее status может быть проверен заново. Сброс одного component ID затрагивает всю factory-группу (`registry_builder.py:139-153`), а не только выбранную модель.

## CAP-INSTALL-CATALOG-002 — статус ≠ metadata ≠ backend ≠ initialization

`src/core/installables/types.py:11-30,137-199`: категории TTS/voices/ASR/RAG/beats/backend/dependency; статусы `unknown`, `not_installed`, `installed`, `ready`, `needs_reinstall`, `backend_missing`, `failed`. Протокол каждого `InstallableComponent` содержит `status`, `build_install_plan`, `build_uninstall_plan`, `build_initialize_plan` и метаданные. Опционально реализуется набор методов конфигурации.

`src/services/installable_catalog_service.py:26-72` хранит status cache с ключом `(component_id, context_fingerprint)`, inflight future, revision и claim (`awaited`, `consumed`, `orphaned`), чтобы late probe мог обновить UI. `:376-415` строит install preview по плану и отдельно вычисляет backend readiness: видимая карточка не доказывает наличие backend или готовность inference. `:549-620` динамические schema/settings при отсутствии component handler возвращают пустой список/словарь, ошибку логируют; сохранение валидирует специализированные device settings и затем invalidates статус.

`catalog_manifest.py:25-40` объявляет backend и compatibility дважды в ru/en с проверкой согласованности; это metadata-policy, не аппаратная диагностика. Поддержка GPU может ограничить install preview независимо от наличия карточки.

## Ценность для новой реализации, без утверждения Rust-архитектуры

- `REQ-INSTALL-CATALOG-001`: различать видимую каталожную декларацию, доступность import/implementation, installed artifacts, backend compatibility, initialize и inference-ready; несоответствия должны иметь отдельные причины.
- `REQ-INSTALL-CATALOG-002`: при смене env/model settings и восстановлении неисправной фабрики должна существовать явная операция повторной проверки; stale failures и status probes не должны жить бесконечно.
- `REQ-INSTALL-CATALOG-003`: результаты поздней проверки должны согласовываться с актуальными ревизией и hardware/settings context, чтобы не перезаписывать более новые результаты и не выдавать failed load за unknown component.
- `REQ-INSTALL-CATALOG-004`: динамические custom RAG карточки и невидимые агрегатные IDs должны иметь определённый контракт обнаружения; изменение списка не должно оставлять неочищенные кэши/разрешения.

**Проверки к выполнению:** force-error loader → cached failure → `invalidate` → success; параллельные `require` и `invalidate`; несколько IDs с одним loader; settings backend switch во время inflight probe; custom model changes, service closed; timeout leading to late UI event. Никакие из этих тестов в данном проходе **не выполнялись**.

**Связано:** [installer](../01-functional/installations.md), [installation plans](../01-functional/installer-component-plans.md), [AI imports](../04-dependencies/ai-worker-python-core-import-boundaries.md), [coverage ledger](../00-research/audit-coverage-ledger.md).
