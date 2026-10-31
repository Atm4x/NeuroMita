# Settings: реестр страниц, доступность, lazy loading и изменение параметров

**Назначение:** восстановить пользовательские сценарии settings UI, а не её QWidget иерархию. **Состояние аудита:** основной navigation/lazy-loading контур подтверждён; отдельные action/validation/UI-renderer всех controls остаются `PARTIAL`. GUI framework comparison отсутствует по пользовательскому решению.

## CAP-UI-SET-001 — доступные настройки (ACTIVE)

`src/ui/pages/settings/section_registry.py:15-173` регистрирует **12 разделов**. `section_access.py:6-66` генерирует visibility keys для каждого кроме `general`,`language`; `settings_page_widget.py:162-208,246-265` применяет карту. `min_mode` в registry сейчас служит initial visibility defaults; старый интерфейс Basic/Advanced/Full заменён отдельными toggles и `apply_interface_mode` сохраняется как compatibility alias.

| Section key | Пользовательское назначение | По умолчанию виден? | Основной builder / источник | Важная функциональность |
|---|---|---|---|---|
| `general` | Приватность, чат, IPC, UI panels, memory profile | всегда | `ui/settings/general_settings.py:135-320` | Visibility toggles, privacy masking, local IPC, chat preferences |
| `language` | Язык и пользовательские переводы | всегда | `ui/settings/language_settings.py:54-118` | LANGUAGE selector и reload локализаций |
| `api` | LLM providers/presets/secrets/model params | да | `ui/settings/api_settings:*`, `controllers/gui/api_settings/*` | Preset editor/test/import/export/schema |
| `characters` | Персонажи/профили/история | да | `ui/settings/character_settings:*` | Backend-dependent section |
| `voice` | Голос/локальная озвучка | нет | `ui/settings/voiceover_settings:*` | `local_voice`,`voice_models` feature preparation |
| `microphone` | ASR, devices, diagnostics | нет | `ui/settings/microphone_settings:*` | `speech` feature preparation |
| `ai_engine` | Hardware, worker mode, environments, AI Hub | нет | `ui/settings/ai_engine_settings.py:130-465` | Hardware refresh, Hub, mode apply, environment reset |
| `game` | Unity/game settings, mini-games, beat | нет | `ui/settings/game_settings.py:417-574` | `ENABLE_GAMES`, game variants, BeatSync |
| `models` | Генерация, tools, RAG | нет | `ui/settings/model_interaction_settings.py:6-190` | Backend-dependent; native/structured options |
| `screen` | Capture/camera/image transformation | нет | `ui/settings/screen_analysis_settings.py:23-492` | Screen, camera, Unity camera, TTL presentation |
| `updates` | Python + Unity updates | да | `controllers/gui/updates_settings_controller.py:39-715` | Check/install, contour, launch, auto-update |
| `data_collection` | Finetune export/rating/clear | нет | `ui/settings/data_settings.py:33-320` | Dataset browsing/export/clear |

*«Да/нет» означает initial visibility при отсутствии сохранённых ключей, а не feature installation readiness. Пользователь может включить/скрыть страницы.* `section_access.py:10-25`. Значения устанавливаются через `SECTION_<CATEGORY>_ENABLED` (`28-66`). Legacy `SECTION_DEVELOPER_ENABLED` однократно мигрирует в `SECTION_DATA_COLLECTION_ENABLED` только если нового ключа нет (`32-51`).

## CAP-UI-SET-002 — navigation/scoped availability

`src/ui/pages/settings/settings_page_widget.py:268-334,558-726`:

- При активации settings открывается первый видимый раздел. Прямой переход `show_category(category,force=True)` может открыть скрытый в tabs раздел — важный deep-link контракт для дочерних экранов.
- Если раздел скрыт и переход не forced, происходит переход к первому видимому; если целевой не зарегистрирован, запрос игнорируется. Действия «Home», «Wiki», «Updates» из header — независимые navigation intents.
- Deep link `subsection` ищет collapsible section по локализованному заголовку, раскрывает и скроллит к нему; если не найден — начало страницы. Это пользовательский UX, но **не** требование использовать локализованный текст как стабильный внутренний ID. `settings_page_widget.py:336-399`.
- Все section shells создаются сразу, но body строится по требованию. У каждой страницы `idle/loading/ready/error`, `_loading_sections` подавляет повторное построение, `_pending_section_scroll` сохраняет актуальный deep-link scroll.
- Sections `characters` и `models` требуют backend, `voice` и `microphone` запрашивают соответствующие optional features; `voice` также имеет deferred feature preparation, отдельный indicator состояния/ошибки. `settings_page_widget.py:49-63,603-671`.
- `SettingsSectionFailed` отображает ошибку и снимает loading flag; `SettingsSectionReady` ставит Qt queued signal для построения на GUI thread (`633-645,673-725`). Провал сборки widget не должен приравниваться к отсутствию domain service.

## CAP-UI-SET-003 — изменение, отображение и lifetime binding

`src/ui/settings/settings_binding.py:12-72,87-188,190-246`:

- Qt settings mirror получает `SettingsService.snapshot()` и подписку на изменения. До backend он может отображать ранее сохранённое значение.
- `set` оптимистически меняет local snapshot и вызывает typed service update; на synchronous exception восстанавливает прежнее UI-значение и публикует `write_failed`. Disk save асинхронный, поэтому поздний I/O failure в эту ветку не попадает.
- Двусторонние связи строятся на ключах, владельцах widgets и callback suppression; widget destruction и page close должны отписывать callbacks. В новом GUI сохраняется **поведение**, не Qt implementation.

## Подтверждённые key groups (частичный инвентарь)

Для этих групп `key` найден напрямую в config dict у **зарегистрированного** builder; количество не равно всему числу настроек домена, поскольку некоторые UI controls составляются программно и runtime keys хранятся в других файлах.

| Группа | Явных статических key entries | Примеры ключей и источник |
|---|---:|---|
| `general` | 10 | `HIDE_PRIVATE`, `RUNTIME_IPC_ENABLED`, `RUNTIME_IPC_PORT`, `CHAT_FONT_SIZE`, `SHOW_TOKEN_INFO`, `MEMORY_PROFILE`; `general_settings.py:163-320` |
| `language` | 1 | `LANGUAGE`; `language_settings.py:72` |
| `game` | 8 | `IGNORE_GAME_REQUESTS`, `ENABLE_GAMES`, `ENABLE_GAME_CHESS`, `ENABLE_GAME_SEABATTLE`, `BEAT_SYNC_ENABLED`; `game_settings.py:427-564` |
| `models` | 21 | `ENABLE_STREAMING`, `TOOLS_ON`, `TOOL_ENABLED_*`, `TOOL_MAX_DEPTH`, `REACT_ENABLED`, `GOOGLE_API_KEY`; `model_interaction_settings.py:26-172` |
| `screen` | 43 | `SCREEN_CAPTURE_*`, `CAMERA_CAPTURE_*`, `IMAGE_DESCRIPTION_*`, `IMAGE_CLEANUP_TTL_*`, `MITA_CAMERA_*`; `screen_analysis_settings.py:36-472` |
| `ai_engine`, `data_collection`, `updates` | **не оценено этим методом** | Виджеты созданы вручную, ключи/кнопки проходят через viewmodels и signal handlers; нельзя трактовать 0 dict entries как отсутствие controls |

Из этих статических групп найдено **83 literal `key` entries** в пяти active builders (10+1+8+21+43). Это измеренный *частичный список* GUI keys, **не процент** общего охвата настроек. В частности privacy `HIDE_PRIVATE` в UI описан как **маска полей, а не шифрование** (`general_settings.py:163-175`). Деталь at-rest см. [settings and migrations](../01-functional/settings-storage-and-migrations.md).

## Поведенческие сценарии и отказоустойчивость

1. Пользователь скрывает `models`, затем deep-link с другой страницы `force=True` открывает его без включения чекбокса; direct UI update должен уважать различие visibility vs navigation target.
2. Первый вход в `voice` делает background feature preparation; UI остаётся loading и может показать feature unavailable. Вызов сразу во время подготовки не должен инициировать вторую сборку.
3. Пользователь меняет `RUNTIME_IPC_PORT` при disabled toggle: control `depends_on` и `validation` прописаны в general builder; это только UI validation, runtime service contract отдельный.
4. Изменение в settings mirror показывает optimistic state; отказ storage durable write не перехватывается текущим mirror `set`.
5. Экспорт API preset включает credential values; privacy checkbutton не предотвращает экспорт. Это различие обязательно отдельно описывать пользователю при проектировании нового UI.

## Requirements и неразобранные ветви

- `REQ-UISET-001`: Сохранить все 12 зарегистрированных settings categories и действующие действия каждого, но не копировать Widget tree.
- `REQ-UISET-002`: Сохранять per-section visibility preferences, forced deep-links, legacy key migration и скролл к подразделам без идентификации по переводу.
- `REQ-UISET-003`: Различать section loading, dependency preparation, unavailable feature и failure UI building.
- `REQ-UISET-004`: Typed state binding, unsubscribe/close, реакция на runtime изменения и feedback о durable failures.
- `REQ-UISET-005`: Для каждого поля построить trace `UI key → settings storage → consumer/effect`; статический список literal keys — только начало.

**Далее:** в `ai_engine` исследовать все кнопки reset/mode/restart и backend outcomes; в `data_collection` — confirmation/clear/export; `updates` — progress/exit; `models` — dynamic RAG/embedding/graph controls; `screen` — источники кадров и consumer TTL; полный UI key-to-runtime cross-check. Не проводить отдельное сравнение Slint/Qt в этом аудите.
