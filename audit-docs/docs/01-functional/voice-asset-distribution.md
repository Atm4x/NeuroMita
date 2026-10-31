# Распространение и обновление голосов персонажей: ассеты отдельно от TTS engines

**Статус:** `CONDITIONAL`; голоса доступны в AI Hub, если соответствующие компоненты зарегистрированы. **Доказательства:** `src/installables/voice_assets.py:40-357`, `src/utils/voice_assets_installer.py:32-329`. Это статический source audit `CodeNow.zip`, без скачиваний или распаковки удалённых ZIP. Привязка к версии — исходный checkpoint (`releases/38172493`), не подтверждена содержимым Git history внутри ZIP.

## Functional capability CAP-VOICE-ASSET-001 — отдельные voice bundles

### Назначение и сценарий

Пользователь устанавливает голос конкретного персонажа либо все голоса из каталога. Голосовой bundle содержит **артефакты**, не отдельный TTS engine: `.pth`/`.onnx`, возможные `.index`, reference `.wav`/`.txt` и `_Cuts`. Даже установленный движок TTS/RVC может не иметь необходимых assets для выбранного персонажа. Это независимое от inference требование новой NeuroMita.

`voice_assets.py:50-58` на этой ревизии перечисляет семь имён: `CrazyMita`, `MitaKind`, `CappieMita`, `Mila`, `ShorthairMita`, `SleepyMita`, `GhostMita`. `create_voice_asset_installable_components` создаёт агрегатную карточку `voices:all` и по одной на каждый bundle (`:354-357`). Список — **поставляемый catalog**, не обязательная целевая структура Rust.

### Вход, выход, состояние

Входы: `short_name`, `clean`, optional refresh; remote GitHub release/tag из `NEUROMITA_VOICE_REPO`/`NEUROMITA_VOICE_TAG`, optional `NEUROMITA_MODELS_DIR`; текущий `manifest.json` с `voices/<short_name>/{date,sha256,size}` (`voice_assets_installer.py:32-60,71-103`).

Состояния: `not_installed`, `installed`, `update_available`, `download_pending`, `cached_zip`, `extracting`, `version_recorded`, `uninstalling`. Код реализует не все как единый enum: это функциональная реконструкция из отдельных проверок и планов.

`voice_assets.py:170-212`: installed устанавливается по `is_installed(short_name)`, update — по удалённому manifest, clean/update определяют план. `voice_assets_installer.py:198-214` считает installed, если **существует хотя бы один** `.pth` или `.onnx`, даже без reference или другого backend variant; это намеренная кросс-платформенная эвристика, не доказательство inference-ready.

### Установка одного bundle

1. `fetch_remote_manifest(force)` использует in-memory TTL 120s; при HTTP/parse failure возвращает старый кэш либо `None` (`voice_assets_installer.py:63-93`). Отсутствие manifest — не явное hard failure; он влияет на решение об update и запись version metadata.
2. При обычном installed+no-update возвращается `already_installed`. При `clean` `voice_assets.py:101-118` удаляет cache и текущие assets перед скачиванием; при update удаляет только ZIP cache (старые assets сохраняются до extraction, `:121-136`).
3. `download_http` получает ZIP в `Models/.voice_cache/<ShortName>.zip` (`voice_assets.py:68-75`).
4. `extract_bundle` создаёт `.stage_<ShortName>` под Models, принимает ZIP с root либо единственной обёрткой `Models/`/`<ShortName>/`; отбрасывает записи с `..` и запрещает direct path traversal; затем копирует ZIP members в staging и переносит каждый файл в финальное место через `os.replace` (`voice_assets_installer.py:217-289`).
5. При успешном `extract_bundle`, `record_installed_version` записывает *поля удалённого manifest*, не пересчитывает digest скачанного ZIP (`voice_assets.py:78-98`, `voice_assets_installer.py:125-148`).
6. После извлечения ZIP cache удаляется независимо от успеха extraction (`voice_assets.py:78-91`). Если extract частично не удался, retry скачивает ZIP заново.

### Полное множество и uninstall

`AllVoicesComponent` считает `installed_n/total/updates`, строит последовательность install steps только для недостающих/устаревших, а при clean — для всех (`voice_assets.py:238-323`). Это **многоартефактная последовательность**, не единая транзакция: при ошибке на voice N уже скачанные голоса 1..N−1 могут остаться установленными.

`VoiceAssetComponent.build_uninstall_plan`: individual removal вызывает `remove_assets`, но wrapper `_remove` возвращает `True` **независимо от bool результата** (`voice_assets.py:214-232`), тогда как aggregate `_remove` корректно агрегирует неудачи (`:325-348`). `remove_assets` перечисляет известные filename/paths, подавляет отдельные unlink failures, но в финале проверяет, остался ли `.pth/.onnx`, и возвращает `False` (`voice_assets_installer.py:292-329`). Следовательно, индивидуальная карточка способна показать success даже при оставшихся model files — статически подтверждённая **потеря результата**, не испытанный runtime дефект.

### Согласованность, безопасность, восстановление

- `is_update_available` сравнивает manifest SHA или date с сохранённым *метаданным* локального файла версий (`voice_assets_installer.py:158-179`); в исследованном downloader/extractor path **нет проверки фактического SHA256 байтов ZIP**. Сравнение версий ≠ криптографическая проверка скачанного содержимого. Перед целевым дизайном уточнить, гарантирует ли generic `download_http` отдельный checksum (в объявленном action передан только URL и dest; `voice_assets.py:68-75`).
- Staging защищает от битого ZIP во время первоначальной распаковки, но **финальный commit per file**, а не atomic bundle: часть файлов уже заменена, если `os.replace` на позднем файле упал (`voice_assets_installer.py:262-269`). Новая реализация должна иметь явный atomic publication boundary либо observable partial outcome.
- Обычный `clean` удаляет старые assets **до** нового download. Failure после clean означает потерю прежней установленной версии, хотя обычное update сохраняет её до phase extract (`voice_assets.py:101-136`). Нельзя смешивать эти политики.
- Установленность по существованию `.pth/.onnx` потенциально принимает нулевой/повреждённый файл как installed; `voice_assets_installer.py:198-214`. Не делать из этого вывода, что вся текущая загрузка небезопасна: generic downloader и model loading не испытаны.
- `versions_store_path` на `.voice_versions.json`, запись через temporary file+`os.replace`, ошибки сохранения **подавляются** (`voice_assets_installer.py:108-148`). После успешного extraction отсутствие версии не обязательно помешает `installed`, но может порождать повторные обновления.
- `extract_bundle` применяет `rel.lstrip('/')` и фильтр `..` в `Path.parts`, но безопасность against symlinks, special ZIP entries, duplicate paths, ресурсные лимиты/ZIP-bombs/диск/symlinked output dir нужно проверять отдельно; заявлять доказанную устойчивость ко всем malformed ZIP нельзя.

## Requirements / acceptance

| ID | Требование | Проверка |
|---|---|---|
| `REQ-ASSET-001` | Хранить voice engine и voice bundle раздельно; engine ready не означает presence voice assets | без голосов / только `.pth` / только `.onnx` / reference missing |
| `REQ-ASSET-002` | Install/update/clean/uninstall имеют разный rollback и результат; success возвращает проверенное состояние assets | отказ после каждого шага, locked file, partial commit |
| `REQ-ASSET-003` | Manifest version, фактический content integrity и installed/ready являются разными predicates | старый manifest, плохой digest, corrupted ZIP, stale cache |
| `REQ-ASSET-004` | Для aggregate установки явно возвращать per-voice outcomes, не скрывать частичные успехи | fail voice 3/7, retry, отмена, delete |
| `REQ-ASSET-005` | Права владения файлов, допустимые ZIP paths, staging/atomic publication и bounded extraction проверяемы | traversal, symlink, duplicated member, ZIP bomb, crash |

## Источники и непроверенное

`voice_assets.py` / `voice_assets_installer.py` прочитаны по всем основным ветвям; **не** запускались GitHub endpoints, реальные voice bundles, remote version schema, download action implementation и Python/Windows locked-file behavior. Каталог семи bundles и пользовательские статусы подтверждены только для данной ревизии. Неисследовано: voice ownership на стороне target inference, full dependency/license facts внешних моделей, перенастройка paths из GUI, live migration конфликтующих файлов.
