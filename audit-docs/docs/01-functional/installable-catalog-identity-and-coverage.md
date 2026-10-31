# AI Hub: идентичность и охват устанавливаемых компонентов

**Статус исследования:** `ACTIVE` для каталога и UI; конкретные компоненты `CONDITIONAL` по выбранной модели, устройству, настройкам и установке. Источник: локальный `CodeNow.zip` без `.git` для повторной проверки SHA. Документ описывает *набор возможностей*, а не перенос Python installers в Rust.

## CAP-INSTALL-ID-001 — стабильный каталог пользовательских компонентов

`src/installables/catalog_manifest.py:42-902` содержит **31 статическую** не-RAG карточку. Каждая карточка объявляет `id`, `item_id`, `category`, RU/EN metadata, language list, backend и строку динамического loader. Импорт модуля со списком карточек не обязан загрузить inference implementation (`src/installables/catalog_manifest.py:17-39`, `src/installables/registry_builder.py`; см. [lazy loading](installable-catalog-lazy-registry-and-status.md)).

| Категория | Кол-во статических карточек | Подтверждённые идентификаторы | Функциональное назначение |
|---|---:|---|---|
| Backend | 3 | `backend:cpu`, `backend:cuda`, `backend:onnx` | Совместное окружение исполнения нейросетей, не веса конкретной модели (`:43-113`) |
| TTS | 12 | `edge_tts_rvc_cuda`, `silero_rvc_cuda`, `edge_tts_rvc_onnx`, `silero_rvc_onnx`, `omnivoice`, `medium`, `medium+`, `medium+low`, `high`, `high_clf5`, `high+low`, `high_clf5+low` (все с `tts:`) | Выбираемые движки синтеза/конверсии речи; отличаются backend, языками и voice pipeline (`:115-487`) |
| ASR | 5 | `asr:google`, `asr:gigaam`, `asr:gigaam_onnx`, `asr:whisper`, `asr:whisper_onnx` | Варианты speech-to-text и их модели/среды (`:488-619`) |
| Beat | 1 | `beats:beat_this` | Музыкальная beat extraction (`:620-643`) |
| Dependency | 2 | `dependency:ffmpeg`, `dependency:opencv` | Внешний media executable и обработка изображений/камера (`:644-695`) |
| Voice assets | 8 | `voices:all`, `voices:CrazyMita`, `voices:MitaKind`, `voices:CappieMita`, `voices:Mila`, `voices:ShorthairMita`, `voices:SleepyMita`, `voices:GhostMita` | Отдельные архивы голосовых ассетов персонажей и batch-команда (`:696-902`) |

**Подтверждение числа:** 3 + 12 + 5 + 1 + 2 + 8 = 31. `voices:all` — не восьмой персонаж, а batch-операция над семью именованными наборами. Названия карточек не следует трактовать как перечисление всех поддерживаемых AI model files/конфигураций.

## CAP-INSTALL-ID-002 — динамическая часть RAG

`src/installables/catalog_manifest.py:909-1042`: `all_model_specs()` создаёт карточки предустановленных local embedding/reranker models, `custom_active_model_specs()` добавляет выбранные пользователем custom-модели **при каждом чтении каталога**, а агрегаты `rag:embeddings` / `rag:reranker` доступны для lookup/settings-driven installation, но *не показываются как обычные отдельные карточки в сетке*. Поэтому общее число карточек UI не равно постоянным 31; статический снимок metadata не может заменить runtime model identity.

`catalog_entries()` возвращает базовые карточки с custom additions; `catalog_by_id()` поддерживает также aggregate lookup. Функционально это три разных идентификатора: карточка предустановленного checkpoint, карточка custom checkpoint и агрегат «эффективная выбранная модель». Требования к RAG-настройкам и модельным файлам: [RAG install](asr-rag-beat-install-plans.md), [component probes](installable-component-probe-and-operation-contracts.md).

## CAP-INSTALL-ID-003 — описание, совместимость, наличие и readiness не равны друг другу

`src/services/installable_catalog_service.py:125-197,206-316`: метаданные выбираются по языку, `compatibility` рассчитывается по аппаратному inventory и объявленным требованиям, `status` запрашивается отдельно (возможно асинхронно). `ready_item_ids(category)` принимает исключительно `status.ready`, а не `installed` или наличие карточки. `install_preview()` показывает необходимость backend dependency прежде чем установка модели начата (`:371-454`).

Пользовательский путь: открыть категорию → увидеть список независимо от готовности всех движков → дождаться status → оценить совместимость → получить план и предупреждение о дополнительном backend → установить/обновить/удалить → повторно проверить readiness. Шесть категорий визуально могут иметь разные стратегии probe, а одни и те же ассеты могут принадлежать нескольким моделям.

### Требования к будущему функциональному паритету

- `REQ-INSTALL-ID-001`: сохранить ID категорий и различие движка, backend, model artifact и voice asset; не проектировать единый boolean installed для всего.
- `REQ-INSTALL-ID-002`: поддержать независимую от импортирования inference metadata discovery и отдельные статус/compatibility/readiness.
- `REQ-INSTALL-ID-003`: поддержать динамические RAG checkpoint IDs, текущие кастомные модели и невидимые aggregate lookup IDs; не фиксировать число карточек в GUI.
- `REQ-INSTALL-ID-004`: обеспечить просмотр плана required backend до принятия установки модели и отдельную проверку результата после операции.

### Проверки и пределы

Будущие fixtures: все 31 ID и RU/EN metadata; категория и backend stable across locale; custom RAG появляется после смены настроек; aggregate lookup работает без UI-карточки; voice asset не делает engine ready; отсутствующий backend показан отдельно от model artifact. **Не проверены:** реальные Windows GPU, installer downloads, загрузка всех inference моделей и вывод всех карточек в Qt. Никаких старых ошибок здесь не исследовалось.
