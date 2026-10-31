# Устройства ускорения и пользовательское администрирование Python AI Engine

> Срез локального Python Core из CodeNow.zip. Фокус — продуктовые функции и наблюдаемые контракты. Выбор новой Rust-архитектуры и внедрение CUDA inference в Rust **не проводятся**.

## CAP-AI-HARDWARE — инвентаризация доступных GPU

**Статус:** `CONDITIONAL` (Windows-путь + поддержка DXGI/CUDA драйвера); регистрация production-сервиса подтверждена. Источники: `src/__main__.py:189`, `src/services/hardware_inventory_service.py:75-138,141-227,234-350,353-442`, `src/controllers/gui/ai_engine_settings_view_model.py:55-104`, `src/ui/settings/ai_engine_settings.py:130-208,466-659`.

Пользователь открывает вкладку AI Engine и видит физические видеокарты, объём выделенной видеопамяти, производителя, наличие NVIDIA CUDA и список ускорителей. Исходная реализация получает адаптеры через Windows `dxgi.dll` COM интерфейс `CreateDXGIFactory1`/`EnumAdapters1`/`GetDesc1`, исключает программные адаптеры. Независимо запрашивает CUDA Driver API в `nvcuda.dll`: версию драйвера, ordinal-список `cuda:N`, имя устройства, compute capability `sm_XY` (`hardware_inventory_service.py:75-227`). Ни PyTorch, ни AI worker для этой диагностики не запускаются.

Сопоставление DXGI-карты и CUDA ordinal делается по LUID; при отсутствии LUID возможно только однозначное совпадение нормализованных имён. Несопоставленные CUDA-устройства всё равно включаются в общий список. В многокарточной конфигурации физический `adapter index` и логический `cuda ordinal` имеют **различную идентичность** — эти адреса не должны быть взаимозаменяемы. Результат содержит `platform`, `adapters`, `accelerators`, `primary`, `vendor`, `cuda` с `available/devices/driver_version` и диагностическую ошибку (`:234-350,400-442`).

Сервис возвращает копию snapshot и кэширует его с TTL по умолчанию **120 секунд**; пользовательская кнопка «Обновить» передаёт `refresh=True` и заставляет выполнить новое чтение. GUI отображает загрузку, ошибку, найденные ускорители и название backend. На не-Windows платформе `source=unsupported` — не экстраполировать Windows UI на другие ОС (`:353-442`, `ai_engine_settings_view_model.py:89-104`, `ai_engine_settings.py:165-208`).

## CAP-AI-ADMIN — состояние топологии/установленных backend и переключение

**Статус:** `ACTIVE` у текущего GUI при наличии соответствующего сервиса. Источники: `src/controllers/gui/ai_engine_settings_view_model.py:18-195`, `src/ui/settings/ai_engine_settings.py:395-658`.

Вкладка AI Engine — не только экран диагностики. Она запрашивает **независимые проекции**: физические ускорители (`HardwareInventoryService`), топологию запущенного AI Engine (`AIEngineAdministrationService.topology_snapshot`), состояние операций обслуживания (`AIEnvironmentMaintenanceService.snapshot`) и список/install status backend из `InstallableCatalogService.list_rows(category='backend',status_category='backend')`. Модель UI хранит для каждого источника собственные `loading` и `error`, плюс глобальный `busy` и `reset_running`. Изменение installable catalog публикуется в UI и отдельно обновляет backend list (`ai_engine_settings_view_model.py:18-166`).

Пользователь может запросить смену режима/топологии AI Engine (`switch_mode → switch_topology`) и затем получает новую топологию или ошибку. Это **операция управления процессами/размещением AI Engine**, а не просто выбор визуальной карточки. Реальные режимы **`shared` и `split`** (другие значения отклоняются). `switch_topology` сериализует switch, маркирует его как временное состояние, останавливает текущие worker-процессы, устанавливает новый mode, запускает новый набор worker. При неуспехе пытается восстановить прежний mode и процессы. При наличии переменной окружения `NEUROMITA_AI_ENGINE_MODE` пользовательское переключение запрещено; успешный выбор сохраняет `AI_ENGINE_MODE` в настройки. `topology_snapshot` содержит mode, override, признак suspended и таблицу workers с назначенными сервисами и alive-state (`src/controllers/ai_engine_controller.py:2325-2437`).

## CAP-AI-ENV-MAINTENANCE — сброс управляемых окружений

**Статус:** `ACTIVE`, при наличии сервиса обслуживания. Источники: `src/controllers/gui/ai_engine_settings_view_model.py:197-256`, `src/ui/settings/ai_engine_settings.py:440-465`.

Пользователь инициирует «сброс AI окружений». При уже выполняемом сбросе, занятом AI Engine или фоновой maintenance операции второе действие не запускается. UI сначала показывает `validating`, затем получает последовательные status snapshots из `AIEnvironmentMaintenanceService.reset_all(progress=...)`: **validating → draining_installs → stopping_workers → deleting → reconciling → restarting → completed** либо `failed`. Реальное исполнение останавливает очередь установок (`quiesce`, ожидание до 30 секунд), входит в maintenance-session AI Engine, удаляет управляемое AI-окружение, инвалидирует каталог и выходит из maintenance-session с возобновлением worker; затем возобновляет очередь и публикует `CATALOG_CHANGED`. Снимок даёт `path`, `exists`, `size_bytes`, `state`, `busy`, `revision`, `message`, `error` (`src/services/ai_environment_maintenance_service.py:20-179`). После завершения UI принудительно обновляет топологию, состояние обслуживания и каталог backend; ошибка отображается отдельно от статуса оборудования. Важно сохранить различие `инвентаризация железа` / `установленность backend` / `работающий AI Engine` / `операция maintenance`: ни один сигнал не эквивалентен другим.

## Контракт для parity и разграничение

`REQ-AI-HW-01`: показывать обнаруженные физические ускорители с доступным назначением `cuda:N`, не смешивая DXGI-индекс и CUDA ordinal. `REQ-AI-HW-02`: поддерживать cached и forced refresh, loading/error, отсутствие драйвера, AMD/Intel без CUDA, несколько NVIDIA. `REQ-AI-ADMIN-01`: показывать отдельно рабочую топологию AI Engine, доступные backend и maintenance progress; поддерживать пользовательское переключение режима при наличии сервиса. `REQ-AI-ADMIN-02`: поддерживать подтверждаемое обслуживание/сброс AI окружений с прогрессом и повторной оценкой готовности.

Граница с Python AI Engine: эти возможности описывают управление и платформенные сведения Core; они не требуют портирования PyTorch, ONNX, ASR, TTS или CUDA inference. Реализация может быть другой, однако должны сохраниться пользователю доступные операции и семантика состояний.

**Оставшиеся доказательства:** привязка `shared`/`split` к точному распределению service names по worker-слотам, Windows live test нескольких GPU, отсутствие драйвера, диагностика AMD/Intel, platform fallback. Имена API и источники здесь проверены статически; аппаратные тесты не выполнялись.
