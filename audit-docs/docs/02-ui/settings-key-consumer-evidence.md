# Settings key → consumer: literal AST evidence index

**Source:** static AST scan `src/**/*.py` in `CodeNow.zip` (2026-10-30), excluding tests, `not_used` and Python caches. This is an **evidence index**, not execution proof. The table includes **83 literal `key` fields** found in five *registered* settings builders; many additional manual/derived/viewmodel settings are outside this sample. A literal occurrence in a source file does not itself prove the path is reachable or that the value is consumed. A missing literal does **not** prove a key unused, since identifiers can be composed dynamically (e.g. `TOOL_ENABLED_*`).

Classification:

- `CORE_LITERAL`: another exact string in non-GUI, non-service source file; inspect actual `.get()`/`.set()` and registration before classifying ACTIVE.
- `SERVICE_LITERAL`: another exact string only in `src/services/` among non-GUI references; possible service-level consumer/definition.
- `GUI_LITERAL`: another exact string in GUI; may be only display code.
- `DYNAMIC_CORE_KEY`: complete key generated from a dynamic prefix in verified `ModelController` path.
- `NO_OTHER_LITERAL`: no exact string found outside defining builder in this bounded scan; **UNRESOLVED**, not LEGACY.

| Key | Declared UI source | Static evidence category | Other candidate location |
|---|---|---|---|
| `HIDE_PRIVATE` | `src/ui/settings/general_settings.py:163` | GUI_LITERAL | `src/ui/settings/model_interaction_settings.py:122`; `src/ui/settings/model_interaction_settings.py:124` |
| `RUNTIME_IPC_ENABLED` | `src/ui/settings/general_settings.py:193` | SERVICE_LITERAL | `src/services/runtime_ipc_service.py:25` |
| `RUNTIME_IPC_PORT` | `src/ui/settings/general_settings.py:205` | SERVICE_LITERAL | `src/services/runtime_ipc_service.py:26` |
| `CHAT_FONT_SIZE` | `src/ui/settings/general_settings.py:228` | GUI_LITERAL | `src/ui/chat/message_renderer.py:171`; `src/controllers/gui/settings_controller.py:113` |
| `CHAT_MAX_BUBBLE_WIDTH` | `src/ui/settings/general_settings.py:236` | GUI_LITERAL | `src/ui/chat/message_renderer.py:343`; `src/ui/chat/message_renderer.py:669` |
| `SHOW_CHAT_TIMESTAMPS` | `src/ui/settings/general_settings.py:247` | GUI_LITERAL | `src/ui/pages/sandbox_page.py:2179`; `src/ui/pages/sandbox_page.py:2315` |
| `SHOW_THINK_IN_GUI` | `src/ui/settings/general_settings.py:257` | CORE_LITERAL | `src/controllers/chat_controller.py:571` |
| `SHOW_SYSTEM_MESSAGES` | `src/ui/settings/general_settings.py:269` | GUI_LITERAL | `src/ui/pages/sandbox_page.py:2180`; `src/ui/pages/sandbox_page.py:2326` |
| `SHOW_TOKEN_INFO` | `src/ui/settings/general_settings.py:281` | GUI_LITERAL | `src/ui/pages/sandbox_page.py:2181`; `src/ui/pages/sandbox_page.py:2345` |
| `MEMORY_PROFILE` | `src/ui/settings/general_settings.py:319` | GUI_LITERAL | `src/ui/settings/memory_profile.py:81`; `src/ui/settings/memory_profile.py:87` |
| `LANGUAGE` | `src/ui/settings/language_settings.py:72` | CORE_LITERAL | `src/handlers/screen_handler.py:12`; `src/handlers/camera_handler.py:10` |
| `WORLD_HIERARCHY_TREE` | `src/ui/settings/game_settings.py:427` | CORE_LITERAL | `src/controllers/server_controller.py:148` |
| `IGNORE_GAME_REQUESTS` | `src/ui/settings/game_settings.py:437` | CORE_LITERAL | `src/controllers/server_controller.py:135`; `src/controllers/server_controller.py:393` |
| `GAME_BLOCK_LEVEL` | `src/ui/settings/game_settings.py:445` | CORE_LITERAL | `src/controllers/server_controller.py:136`; `src/controllers/server_controller.py:259` |
| `ENABLE_GAMES` | `src/ui/settings/game_settings.py:476` | CORE_LITERAL | `src/managers/game_manager.py:58` |
| `ALLOW_GAMES_WHEN_CONNECTED` | `src/ui/settings/game_settings.py:486` | CORE_LITERAL | `src/managers/game_manager.py:62` |
| `ENABLE_GAME_CHESS` | `src/ui/settings/game_settings.py:497` | SERVICE_LITERAL | `src/services/settings_service.py:68` |
| `ENABLE_GAME_SEABATTLE` | `src/ui/settings/game_settings.py:505` | SERVICE_LITERAL | `src/services/settings_service.py:69` |
| `BEAT_SYNC_ENABLED` | `src/ui/settings/game_settings.py:564` | CORE_LITERAL | `src/controllers/server_controller.py:149`; `src/controllers/server_controller.py:399` |
| `SEPARATE_PROMPTS` | `src/ui/settings/model_interaction_settings.py:26` | CORE_LITERAL | `src/controllers/model_controller.py:1452` |
| `MODEL_MESSAGE_ATTEMPTS_COUNT` | `src/ui/settings/model_interaction_settings.py:28` | CORE_LITERAL | `src/managers/model_config_loader.py:195`; `src/managers/model_config_loader.py:136` |
| `MODEL_MESSAGE_ATTEMPTS_TIME` | `src/ui/settings/model_interaction_settings.py:30` | CORE_LITERAL | `src/managers/model_config_loader.py:196`; `src/managers/model_config_loader.py:138` |
| `ENABLE_STREAMING` | `src/ui/settings/model_interaction_settings.py:32` | CORE_LITERAL | `src/handlers/chat_handler.py:323`; `src/controllers/chat_controller.py:569` |
| `SCHEMA_REASONING` | `src/ui/settings/model_interaction_settings.py:35` | CORE_LITERAL | `src/controllers/model_controller.py:1517` |
| `TEXT_WAIT_TIME` | `src/ui/settings/model_interaction_settings.py:52` | NO_OTHER_LITERAL | — |
| `VOICE_WAIT_TIME` | `src/ui/settings/model_interaction_settings.py:55` | NO_OTHER_LITERAL | — |
| `TOOLS_ON` | `src/ui/settings/model_interaction_settings.py:63` | CORE_LITERAL | `src/controllers/model_controller.py:1478` |
| `TOOL_ENABLED_calculator` | `src/ui/settings/model_interaction_settings.py:69` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_ENABLED_web_search` | `src/ui/settings/model_interaction_settings.py:72` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_ENABLED_google_search` | `src/ui/settings/model_interaction_settings.py:75` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_ENABLED_web_reader` | `src/ui/settings/model_interaction_settings.py:78` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_ENABLED_memory_search` | `src/ui/settings/model_interaction_settings.py:81` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_ENABLED_reminder` | `src/ui/settings/model_interaction_settings.py:90` | DYNAMIC_CORE_KEY | `src/controllers/model_controller.py:1488` (key synthesized) |
| `TOOL_MAX_DEPTH` | `src/ui/settings/model_interaction_settings.py:98` | CORE_LITERAL | `src/controllers/model_controller.py:2296`; `src/controllers/model_controller.py:1481` |
| `TOOL_RESULT_MSG_MODE` | `src/ui/settings/model_interaction_settings.py:107` | CORE_LITERAL | `src/controllers/model_controller.py:2656` |
| `GOOGLE_API_KEY` | `src/ui/settings/model_interaction_settings.py:121` | CORE_LITERAL | `src/managers/tools/builtin/google_search.py:42` |
| `GOOGLE_CSE_ID` | `src/ui/settings/model_interaction_settings.py:123` | CORE_LITERAL | `src/managers/tools/builtin/google_search.py:43` |
| `REACT_ENABLED` | `src/ui/settings/model_interaction_settings.py:150` | CORE_LITERAL | `src/controllers/chat_controller.py:282`; `src/game_connections/handlers/actions/create_task.py:617` |
| `REACT_L2_ENABLED` | `src/ui/settings/model_interaction_settings.py:163` | CORE_LITERAL | `src/controllers/chat_controller.py:286`; `src/game_connections/handlers/actions/create_task.py:623` |
| `REACT_PROVIDER_L2` | `src/ui/settings/model_interaction_settings.py:172` | CORE_LITERAL | `src/controllers/model_controller.py:973` |
| `ENABLE_IMAGE_ANALYSIS` | `src/ui/settings/screen_analysis_settings.py:36` | CORE_LITERAL | `src/controllers/capture_controller.py:14`; `src/controllers/capture_controller.py:174` |
| `AUTO_ATTACH_IMAGES` | `src/ui/settings/screen_analysis_settings.py:37` | CORE_LITERAL | `src/controllers/capture_controller.py:15`; `src/controllers/capture_controller.py:231` |
| `ENABLE_SCREEN_ANALYSIS` | `src/ui/settings/screen_analysis_settings.py:46` | CORE_LITERAL | `src/controllers/capture_controller.py:14`; `src/controllers/capture_controller.py:52` |
| `SCREEN_CAPTURE_INTERVAL` | `src/ui/settings/screen_analysis_settings.py:59` | CORE_LITERAL | `src/controllers/capture_controller.py:15`; `src/controllers/capture_controller.py:245` |
| `SCREEN_CAPTURE_QUALITY` | `src/ui/settings/screen_analysis_settings.py:60` | CORE_LITERAL | `src/controllers/capture_controller.py:15`; `src/controllers/capture_controller.py:155` |
| `SCREEN_CAPTURE_FPS` | `src/ui/settings/screen_analysis_settings.py:61` | CORE_LITERAL | `src/controllers/capture_controller.py:16`; `src/controllers/capture_controller.py:247` |
| `SCREEN_CAPTURE_HISTORY_LIMIT` | `src/ui/settings/screen_analysis_settings.py:62` | CORE_LITERAL | `src/controllers/capture_controller.py:16`; `src/controllers/capture_controller.py:248` |
| `SCREEN_CAPTURE_TRANSFER_LIMIT` | `src/ui/settings/screen_analysis_settings.py:63` | CORE_LITERAL | `src/controllers/capture_controller.py:17`; `src/controllers/capture_controller.py:249` |
| `SCREEN_CAPTURE_WIDTH` | `src/ui/settings/screen_analysis_settings.py:64` | CORE_LITERAL | `src/controllers/capture_controller.py:17`; `src/controllers/capture_controller.py:156` |
| `SCREEN_CAPTURE_HEIGHT` | `src/ui/settings/screen_analysis_settings.py:65` | CORE_LITERAL | `src/controllers/capture_controller.py:18`; `src/controllers/capture_controller.py:157` |
| `SEND_IMAGE_REQUESTS` | `src/ui/settings/screen_analysis_settings.py:66` | CORE_LITERAL | `src/controllers/capture_controller.py:19`; `src/controllers/capture_controller.py:262` |
| `IMAGE_REQUEST_INTERVAL` | `src/ui/settings/screen_analysis_settings.py:67` | CORE_LITERAL | `src/controllers/capture_controller.py:19`; `src/controllers/capture_controller.py:365` |
| `EXCLUDE_GUI_WINDOW` | `src/ui/settings/screen_analysis_settings.py:68` | CORE_LITERAL | `src/controllers/capture_controller.py:18`; `src/controllers/capture_controller.py:197` |
| `EXCLUDE_WINDOW_TITLE` | `src/ui/settings/screen_analysis_settings.py:69` | CORE_LITERAL | `src/controllers/capture_controller.py:18`; `src/controllers/capture_controller.py:197` |
| `ENABLE_CAMERA_CAPTURE` | `src/ui/settings/screen_analysis_settings.py:80` | CORE_LITERAL | `src/controllers/capture_controller.py:14`; `src/controllers/capture_controller.py:55` |
| `CAMERA_DEVICE` | `src/ui/settings/screen_analysis_settings.py:81` | NO_OTHER_LITERAL | — |
| `CAMERA_CAPTURE_INTERVAL` | `src/ui/settings/screen_analysis_settings.py:86` | CORE_LITERAL | `src/controllers/capture_controller.py:289` |
| `CAMERA_CAPTURE_QUALITY` | `src/ui/settings/screen_analysis_settings.py:87` | CORE_LITERAL | `src/controllers/capture_controller.py:290` |
| `CAMERA_CAPTURE_FPS` | `src/ui/settings/screen_analysis_settings.py:88` | CORE_LITERAL | `src/controllers/capture_controller.py:291` |
| `CAMERA_CAPTURE_HISTORY_LIMIT` | `src/ui/settings/screen_analysis_settings.py:89` | CORE_LITERAL | `src/controllers/capture_controller.py:292` |
| `CAMERA_CAPTURE_TRANSFER_LIMIT` | `src/ui/settings/screen_analysis_settings.py:90` | CORE_LITERAL | `src/controllers/capture_controller.py:293` |
| `CAMERA_CAPTURE_WIDTH` | `src/ui/settings/screen_analysis_settings.py:91` | CORE_LITERAL | `src/controllers/capture_controller.py:294` |
| `CAMERA_CAPTURE_HEIGHT` | `src/ui/settings/screen_analysis_settings.py:92` | CORE_LITERAL | `src/controllers/capture_controller.py:295` |
| `IMAGE_QUALITY_REDUCTION_ENABLED` | `src/ui/settings/screen_analysis_settings.py:104` | CORE_LITERAL | `src/managers/model_config_loader.py:198`; `src/managers/model_config_loader.py:141` |
| `IMAGE_QUALITY_REDUCTION_START_INDEX` | `src/ui/settings/screen_analysis_settings.py:105` | CORE_LITERAL | `src/managers/model_config_loader.py:199`; `src/managers/model_config_loader.py:143` |
| `IMAGE_QUALITY_REDUCTION_USE_PERCENTAGE` | `src/ui/settings/screen_analysis_settings.py:106` | CORE_LITERAL | `src/managers/model_config_loader.py:200`; `src/managers/model_config_loader.py:145` |
| `IMAGE_QUALITY_REDUCTION_MIN_QUALITY` | `src/ui/settings/screen_analysis_settings.py:107` | CORE_LITERAL | `src/managers/model_config_loader.py:201`; `src/managers/model_config_loader.py:147` |
| `IMAGE_QUALITY_REDUCTION_DECREASE_RATE` | `src/ui/settings/screen_analysis_settings.py:108` | CORE_LITERAL | `src/managers/model_config_loader.py:202`; `src/managers/model_config_loader.py:149` |
| `IMAGE_INLINE_DESCRIPTION` | `src/ui/settings/screen_analysis_settings.py:121` | CORE_LITERAL | `src/controllers/prompt_controller.py:1270`; `src/controllers/model_controller.py:1827` |
| `IMAGE_DESCRIPTION_ENABLED` | `src/ui/settings/screen_analysis_settings.py:133` | CORE_LITERAL | `src/controllers/prompt_controller.py:225`; `src/controllers/model_controller.py:1569` |
| `IMAGE_DESCRIPTION_PROVIDER` | `src/ui/settings/screen_analysis_settings.py:145` | CORE_LITERAL | `src/handlers/image_description_handler.py:109`; `src/controllers/prompt_controller.py:226` |
| `IMAGE_DESCRIPTION_DETAIL` | `src/ui/settings/screen_analysis_settings.py:159` | CORE_LITERAL | `src/handlers/image_description_handler.py:135`; `src/handlers/image_description_handler.py:176` |
| `IMAGE_CLEANUP_TTL_ENABLED` | `src/ui/settings/screen_analysis_settings.py:330` | NO_OTHER_LITERAL | — |
| `IMAGE_CLEANUP_TTL_DAYS` | `src/ui/settings/screen_analysis_settings.py:340` | NO_OTHER_LITERAL | — |
| `IMAGE_CLEANUP_MAX_PER_CHAR` | `src/ui/settings/screen_analysis_settings.py:348` | NO_OTHER_LITERAL | — |
| `MITA_CAMERA_ENABLED` | `src/ui/settings/screen_analysis_settings.py:382` | CORE_LITERAL | `src/controllers/server_controller.py:156` |
| `MITA_CAMERA_CONTINUOUS` | `src/ui/settings/screen_analysis_settings.py:394` | CORE_LITERAL | `src/controllers/server_controller.py:157` |
| `MITA_CAMERA_ON_DEMAND` | `src/ui/settings/screen_analysis_settings.py:407` | CORE_LITERAL | `src/controllers/server_controller.py:158` |
| `MITA_CAMERA_INTERVAL` | `src/ui/settings/screen_analysis_settings.py:422` | CORE_LITERAL | `src/controllers/server_controller.py:159` |
| `MITA_CAMERA_MAX_FRAMES` | `src/ui/settings/screen_analysis_settings.py:434` | CORE_LITERAL | `src/controllers/server_controller.py:160` |
| `MITA_CAMERA_FRAMES_TO_SEND` | `src/ui/settings/screen_analysis_settings.py:448` | CORE_LITERAL | `src/controllers/server_controller.py:161` |
| `MITA_CAMERA_JPEG_QUALITY` | `src/ui/settings/screen_analysis_settings.py:460` | CORE_LITERAL | `src/controllers/server_controller.py:162` |
| `MITA_CAMERA_USE_FILE_TRANSFER` | `src/ui/settings/screen_analysis_settings.py:472` | CORE_LITERAL | `src/controllers/server_controller.py:163` |

## Coverage and explicit gaps

Static result: `CORE_LITERAL` 60, `DYNAMIC_CORE_KEY` 6, `GUI_LITERAL` 7, `NO_OTHER_LITERAL` 6, `SERVICE_LITERAL` 4. Counts refer to this **sample**, not to all setting keys.

- `TEXT_WAIT_TIME`, `VOICE_WAIT_TIME` have no other literal occurrence in this scan. Must inspect generic binding consumers or config aliases before declaring inactive.
- `IMAGE_CLEANUP_TTL_ENABLED`, `IMAGE_CLEANUP_TTL_DAYS`, `IMAGE_CLEANUP_MAX_PER_CHAR` currently show only UI declarations/dependencies in this bounded scan; no evidence of effective cleanup by these keys. Similar open gap already identified in images-and-capture.
- `TOOL_ENABLED_*` are read via composed key in `src/controllers/model_controller.py:1488`; exact-literal search alone would misclassify all six as unused.
- `HIDE_PRIVATE` is consumed in GUI presentation but masks fields rather than protecting persisted secret values.
- Future task: for each candidate source, resolve actual read/write call sites, domain effects, defaults, migration and platform gates; manual sections + dynamic keys extend inventory.

## Traceability

[Registered settings sections](settings-navigation-and-lazy-pages.md) · [Settings persistence/schema](../01-functional/settings-storage-and-migrations.md) · [Capability progress](../00-research/audit-coverage-ledger.md).

## Условия полного покрытия и требования будущей реализации

`REQ-SET-KEY-001`: вести source-derived mapping для каждого **реально зарегистрированного** UI control и его стабильного key, включая dynamically composed names и effect consumer, а не приравнивать отсутствие literal к неактивному функционалу.

`REQ-SET-KEY-002`: при изменении настроек различать `UI mirror`, `in-memory accepted`, `durably saved`, `consumer applied`, `restart required` и failure outcome; не считать call `.set()` доказательством того, что side effect исполнен.

`REQ-SET-KEY-003`: проверять все builder/action paths, значения default/migration, локализацию UI labels и aliases stable IDs, не допуская зависимости Core behavior от переведённых строк.

**Validation backlog:** раскрыть все оставшиеся зарегистрированные builders и dynamic keys; для кандидатов `NO_OTHER_LITERAL` проверить lookup через computed key, settings snapshots/service access, обратные callbacks и feature gate, прежде чем присваивать `LEGACY`/`UNUSED`. Провести UI action tests с runtime listeners и restart. Текущий список из 83 ключей — **sampled subset**, а не завершённая матрица.
