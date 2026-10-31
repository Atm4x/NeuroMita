# Настройки приложения, API-пресеты и совместимость конфигурации

**Срез:** Python Core из `CodeNow.zip`, статический анализ 2026-10-30. **Статус:** ACTIVE; отдельные типы схем, аутентификация и компоненты — CONDITIONAL. Это инвентаризация функции, не предложение копировать Python-контроллеры в Rust. Не запускались Windows, provider network, GUI или реальные пользовательские конфиги.

## Функциональные возможности

| Capability | Статус | Назначение | Исходный путь |
|---|---|---|---|
| `CAP-SET-001` | ACTIVE | Читать/обновлять общие параметры, сообщать об изменениях, сохранять JSON | `src/managers/settings_manager.py:36-79,136-253`, `src/core/settings_registry.py:45-171` |
| `CAP-SET-002` | ACTIVE | Мигрировать контур обновления лишь при первом выборе, сохранить пользовательский выбор | `src/services/update_contour.py:36-49,65-201` |
| `CAP-SET-003` | CONDITIONAL | Отдельно хранить и мигрировать пользовательские API-пресеты, fallback и модели | `src/controllers/api_presets_controller.py:77-100,136-201,247-263,587-646,690-798` |
| `CAP-SET-004` | CONDITIONAL | Настраивать schema-based параметры модели с сохранением совместимости поколений | `src/model_settings/{schema,repository,service,migration}.py` |
| `CAP-SET-005` | CONDITIONAL | Держать ChatGPT Plan OAuth account records отдельно и защищать через Windows DPAPI | `src/handlers/llm_providers/chatgpt_plan_auth.py:71-92,490-555` |
| `CAP-SET-006` | CONDITIONAL | Скрывать отдельные credentials в GUI, не меняя способ хранения/отправки | `src/ui/settings/general_settings.py:162-182`, `src/controllers/gui/api_settings/editor_mixin.py:365-369` |

## Конфигурационные домены и фактическое владение

1. `Settings/settings.json`: общий процессный registry; `SettingsManager` хранит глобальную ссылку `instance`, fallback statically читает файл до инициализации (с кэшем по mtime). `src/managers/settings_manager.py:20-34,36-63,65-79,104-134`. Содержит произвольные JSON-значения без схемы всего документа; загрузка валидирует лишь `dict` как root (`136-152`).
2. `Settings/api_presets.json`: user preset entity: `id`, `base`, `url`, `test_url`, `key`, `reserve_keys`, `fallbacks`, `model_settings`, overrides; используется `asdict` без удаления поля `key`. `src/controllers/api_presets_controller.py:77-101,793-798`. Это **обычный JSON с секретами**, не эквивалент DPAPI. Не писать реальные пользовательские значения в audit.
3. `Settings/APIModelSchemas/*.json`: внешние schema definitions, поверх встроенных Python definitions. При сканировании игнорируются g4f, fingerprint известной заводской копии, rejected invalid/dialect conflict; valid revision >= current может переопределить. `src/model_settings/repository.py:16-68`. Подтверждена возможность пользовательских импортов/экспортов `70-104`.
4. `Settings/chatgpt_plan_auth.json`: отдельный OAuth vault. При загрузке plaintext `account/accounts` отвергаются; envelope `protected_accounts` или старый `protected_account` расшифровывается Windows DPAPI. На другой платформе auth отказывается стартовать (`chatgpt_plan_auth.py:74-76,491-555`).
5. `Settings/distribution.json` — **не** preference, а первичный сигнал происхождения дистрибутива. При наличии persisted `UPDATE_CONTOUR` не переопределяет выбор пользователя (`update_contour.py:65-104,183-201`).
6. `Settings/presets.json` — старый формат API-пресетов; legacy import переносит только custom list/order в новый файл, оставляя отдельное происхождение значений (`api_presets_controller.py:740-759`).

## Жизненный цикл общих настроек

```mermaid
sequenceDiagram
    participant Caller as GUI / Runtime
    participant Registry as SettingsRegistry
    participant Observer as Subscribers
    participant Saver as SettingsSaver
    participant Disk as settings.json
    Caller->>Registry: set/update_many(key,value)
    Registry-->>Caller: in-memory revision
    Registry-)Observer: asynchronous SettingChange
    Registry-)Saver: debounce save request
    Saver->>Disk: write .tmp + fsync + os.replace
    Note over Caller,Disk: set accepted != durable write; observers != disk ACK
```

- Изменения по одному ключу либо в batch увеличивают `revision`, но `update_many` создаёт **ревизию на каждый изменённый ключ**, не один transaction revision (`settings_registry.py:103-171`). `replace_all` меняет state и revision разом; `notify=False` по умолчанию, вызов `load_settings` выбирает именно его (`settings_registry.py:173-202`, `settings_manager.py:164-169`).
- Уведомления вызываются после выхода из registry lock, проходят `SerialDispatcher` на 4 stripes с неограниченными очередями; callbacks ошибок не возвращают записавшему. `settings_registry.py:68-75,270-348`; `serial_dispatcher.py:24-29`.
- `SettingsManager` coalesces запросы записи (`Queue(maxsize=1)`, `SAVE_DEBOUNCE_SEC=0.5`), пишет snapshot в `.tmp`, fsync и replace. При обычной ошибке запись только логируется, вызвавший `set` не узнаёт о durable failure. `settings_manager.py:28-40,174-225`.
- Shutdown ждёт writer thread не более двух секунд и затем пытается записать файл сам. Если writer всё ещё работает, общая гарантия single-writer/coherent ordering из этих исходников не доказана: отдельного file lock вокруг `_write_file` нет (`settings_manager.py:227-253`). Это **архитектурный риск**, не воспроизведённая потеря настроек.
- Повреждённый JSON копируется в `.corrupt-<epoch>.json`, после чего загрузка даёт `{}`. OSError на чтении возвращает `{}` без гарантии backup; defaults формируются потребителями, а не глобальным schema root (`settings_manager.py:136-162`).
- Снимки — shallow `dict(...)`, вложенные изменяемые объекты возвращаются по ссылке. Прямая мутация вложенного списка/dict не увеличит revision и может обойти уведомление и запись. Это **статически установленная семантика** `settings_registry.py:60,82-101,103-171`, но её реальная распространённость в callers не измерена.

## Контур обновлений: точные приоритеты

`src/services/update_contour.py:144-201`:

1. Уже сохранённое `UPDATE_CONTOUR` (`test`/`release`) выигрывает при любом внешнем маркере.
2. `distribution.json` с распознаваемой schema version и contour.
3. Старые updater journals, в т.ч. указание репозитория и проверка версии относительно `2026.07.22`.
4. Legacy `UPDATE_REPO` / `UPDATE_CHANNEL` / `TESTER_CODE`.
5. Safe default — `release`, target `VinerX/NeuroMita`, `stable`; `test` — `Atm4x/NeuroMita`, `stable` (`36-49,169-180`).

При первой инференции поле записывается в загруженный dict и позднее сохраняется. Миграция не должна повторно переопределять сознательный выбор пользователя после обновления приложения.

## API-пресеты, модельные схемы, импорт/экспорт

- API preset и schema parameter — **две разные сущности**. Preset содержит endpoint/credential/fallback, schema описывает типизированные поля и mapping dialect request (`model_settings/service.py:28-79`; `schema.py:101-216`).
- `schema_version=1`, unique field ids, numeric/type bounds, отсутствие overlapping parameter paths и protected protocol roots; Gemini допускает `generationConfig` и исключает response schemas. `schema.py:75-95,101-178`. `compile` добавляет только enabled поля после validation `184-216`.
- `model_settings` имеет document `version=1`, schema id, values/enabled, optional `support_overrides` и `sparse_response`. Свойства capabilities могут менять поддержку structured tools и streaming (`service.py:37-79`).
- Миграция legacy generation settings учитывает provider dialect, thinking levels/budget, OpenRouter, DeepSeek, safe_mode; часть параметров теряет включённость по provider profile (`migration.py:1-150`). Факт наличия глобального параметра **не** гарантирует отправку в каждый API.
- Внешние schema files читаются при изменении `(filename,mtime_ns,size)`. Сохранённые заводские JSON по fingerprint игнорируются, пользовательские overrides остаются значимыми (`repository.py:26-62`, `bundled_json_compat.py:7-29`).
- API preset import создаёт **новый id** и сохраняет пользовательскую запись; export передаёт весь effective preset (включая API key и reserve_keys) и полный schema override в обычный JSON на выбранный путь (`api_presets_controller.py:1168-1227,819-873`). Это подтверждённый функциональный путь переноса конфигурации и **секретных данных**. Диалог предупреждения о секретах и внешние ACL этим исходником не доказаны.
- `delete_custom` и `save_order` возвращают success без проверки `_save_presets()` (`api_presets_controller.py:1128-1165`). Возможна разница между in-memory и durable outcome; не утверждать фактическую потерю без fault injection.

## Важные различия security semantics

| Действие | Что реально происходит | Что НЕ доказано |
|---|---|---|
| Hide private | Скрывает в GUI Telegram ID/hash/phone, Google key/CSE; сам UI прямо сообщает, что не шифрует | Защита `settings.json` at rest |
| API key в preset | Persist через `asdict` и `json.dump` | OS credential store / encryption |
| API preset export | Сохраняет credential fields в файл | Redaction перед export |
| ChatGPT Plan OAuth | Protected accounts DPAPI на Windows, отказ unprotected payload | Переносимость токенов между OS/пользователями |
| JSON settings write | Atomic `os.replace` для файла | Durable multi-file transaction с presets/auth/DB |

## Требования к переписыванию с нуля (без выбора конкретной архитектуры)

- `REQ-SET-001`: Различать persisted preference, runtime operational state, distribution origin и credential vault.
- `REQ-SET-002`: Сохранять пользовательские значения и порядок миграций, различать отсутствующее/invalid/explicit `UPDATE_CONTOUR`.
- `REQ-SET-003`: Сохранять API preset identity, fallback order, model-specific parameters и переносимые import/export formats; явно классифицировать секреты.
- `REQ-SET-004`: Указывать разные outcomes «изменено в памяти», «извещены observers», «durably written»; error не скрывать через их смешение.
- `REQ-SET-005`: Для изменений списков/словарей иметь наблюдаемую revision semantics, включая batch и reloading.
- `REQ-SET-006`: Поддерживать strict schema validation, per-dialect mapping, schema revision/override/import/export и legacy thinking modes.
- `REQ-SET-007`: Отделять masking интерфейса от at-rest/in-transit protection, предусмотреть безопасный сценарий export/import secrets.

## Валидационные сценарии (для будущих тестов)

1. Load отсутствующего settings.json, некорректного JSON, отказ чтения, `.corrupt-*.json` fallback.
2. `set(A)`, повторное `set(A)`, `update_many(A,B)`, `replace_all(notify=False)`, observers/revision и cleanup.
3. Два быстрых изменения + обычный debounce; отказ `os.replace`; shutdown на зависшем writer.
4. `UPDATE_CONTOUR` explicit vs distribution marker vs journal vs старый `TESTER_CODE`; invalid schema marker.
5. Migrated preset model_settings по разным dialects, no-op downgrade, import/export custom definitions.
6. API preset export redaction policy должен быть сознательно выбран; оригинал экспортирует ключи.
7. DPAPI vault portability, locked file/auth fatal startup; не тестировать реальными token values.

## Вне покрытия / вопросы

- Нет исчерпывающей карты всех ключей `settings.json` и проверок каждого consumer (см. [UI surface](../02-ui/settings-navigation-and-lazy-pages.md)).
- Не проверено, какие mutable вложенные settings реально меняют в обход `set/update_many`.
- Не проверена фактическая Windows ACL/DPAPI backup/restore portability.
- Не производился fault-injection для concurrent saver и записи отдельных JSON хранилищ.
- Какие форматы экспортов считать публичной совместимостью — решение после сравнения реальных user backups, а не догадка из типов Python.
