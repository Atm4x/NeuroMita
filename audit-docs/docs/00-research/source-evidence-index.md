# Индекс доказательств

Все Python paths относятся к HEAD `38172493fa0d1caf1a5225bc1c559f095f18bb7a`. Строка указывает начало символа; детали внутри символа следует читать целиком. Источники не заменены копиями исходного кода.

## Pass 13: новые свидетельства

| Source / проверка | Что подтверждает | Спецификация |
|---|---|---|
| CodeNow.zip SHA-256: 1024 .py и 160 non-Python файлов | Совпадение представленного source snapshot с рабочим деревом | [Baseline/import](pass13-import-and-source-baseline.md) |
| RAG repositories/retrievers, embedding_presets, graph_store | Model-key/character filtering, lexical без vector, legacy embedding gate, graph provenance | [RAG](../01-functional/rag-mixed-model-recall-and-provenance.md) |
| memory_manager.apply_ttl_cleanup; history_manager.apply_history_ttl_cleanup; graph_store.apply_graph_ttl_cleanup; pipeline/config; rag_utils | Разные TTL outcomes, defaults, maintenance и cached normalization | [Settings semantics](../02-ui/memory-rag-settings-consumer-semantics.md) |
| AppWindowBase history callbacks; ModelController load/load_more; presentation_coordinator | End receiver, ticket/revision, live replay и более узкий older-page policy | [Paging](../02-ui/history-page-fencing-and-live-replay.md) |
| DatabaseManager export/import + восемь extracted methods на временной SQLite | Scope/статусы/даты, new IDs/remap, repeat-import и rollback | [DB exchange](../01-functional/world-db-exchange-isolated-validation.md) |
| prompt_editor node parser/codegen/controller/editor/runner | Standalone authoring, partial AST, loss of unsupported RUN, metadata и preview boundary | [Editor](../02-ui/prompt-editor-authoring-and-node-workflow.md) |
| Dialog factories/controllers/model forms; voice_action_windows; torch_compile_runtime | Draft vs durable save, skip vs compile, HKLM long-path action, unproven VCR notification | [Dialogs Pass 13](../02-ui/dialog-class-reachability-and-action-outcomes.md) |
| ASR/TTS/backend/RAG installable methods и callbacks | Ready predicate, initialize/compile, uninstall/no-op/shared ownership по семействам | [31-ID matrix addition](../06-design-input/installables-component-by-component-parity-matrix.md) |
| 131 dist-info METADATA; selected RECORD; direct/delay import six PE binaries | Наблюдаемые parent edges и native imports локальной venv, не release lock | [Wheel/PE](../04-dependencies/installed-wheel-metadata-and-native-evidence.md) |
| Upstream Rust manifests/API + crates.io version/license metadata (2026-10-31) | Реальные alternative paths и границы/провенанс, без build/parity promise | [Niche](../04-dependencies/core-niche-alternatives-and-parity-gates.md), [common](../04-dependencies/core-library-alternatives-and-native-costs.md) |
| reminder_tool + Character reminder/timer ops + capability/tool gates | Tool friendly due, structured ISO и numeric delay имеют разные пути | [Reminder follow-up](../01-functional/reminders-and-timers.md) |
| legacy_memory_recovery inspect/recover на synthetic folder/files/ZIP | Digest/counts/warnings, character/path rejection и ordered directives; без DB import | [Compatibility fixture](../01-functional/compatibility-imports.md) |
| HistoryManager snapshot reserve/resolve/update/save + Character.load_history | Row ownership/reuse, variables merge, embedding invalidation и отсутствие немедленного live-variable refresh в UI restore chain | [Snapshot follow-up](../01-functional/history.md) |
| AI Hub schema renderer/settings VM/facade/catalog.save_component_settings | Draft→validation→save/invalidate; migration-on-load и empty-on-error | [AI Hub follow-up](../02-ui/ai-hub.md) |
| DbTablePage context menu/edit/delete + variables schema | Direct SQL actions требуют id; composite-key variables не дают успешный generic write | [DB menu](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| All 131 local METADATA / 84 root-name reverse sweep | 82/84 metadata, конкретные transitives/aliases/extras, без resolver activation | [Metadata follow-up](../04-dependencies/installed-wheel-metadata-and-native-evidence.md) |

## Накопительный индекс предыдущих проходов

| ID | Источник | Подтверждает |
|---|---|---|
| E-001 | `src/__main__.py:60 StartupOptions`, `:82 _consume_startup_options` | Режимы и CLI/env |
| E-002 | `src/__main__.py:125 _run_gui` | Shell-first UI, backend attachment и teardown |
| E-003 | `src/__main__.py:330 main` | Выбор host и compiler helper |
| E-004 | `src/startup/runtime_bootstrap.py:522 initialize_runtime` | Общая подготовка до host |
| E-005 | `src/startup/runtime_bootstrap.py:99 _configure_paths` | Изоляция core/AI paths, миграция layout |
| E-006 | `src/startup/runtime_bootstrap.py:314 _run_update_checks` | Recovery и update gates |
| E-007 | `src/startup/gui_backend_loader.py:14 GuiBackendLoader` | Фоновая сборка backend, stop и доставка на UI thread |
| E-008 | `src/startup/headless_runtime.py:20 HeadlessRuntimeHost` | Headless lifecycle и диагностика |
| E-009 | `src/controllers/main_controller.py:66 __init__` | Обязательный runtime-граф |
| E-010 | `src/controllers/main_controller.py:299 _configure_optional_features` | 12 optional registrations и predicates |
| E-011 | `src/controllers/main_controller.py:667 close_app` | Порядок best-effort остановки |
| E-012 | `src/services/runtime_features.py:20 FeatureState`, `:59 RuntimeFeatureManager` | Состояния, поколения, DAG и ownership |
| E-013 | `src/controllers/gui/composition_root.py:11 GuiCompositionRoot` | Shell services, attach и close |
| E-014 | `scripts/run.py:794 ensure_core_ready`, `:816 main` | Проверка core, запуск -S, restart 42 |
| E-015 | `src/core/app_paths.py:7 base_dir` и остальные path helpers | Централизованные пути данных |
| E-016 | `src/utils/Testing/test_headless_runtime.py` | Ожидания headless, options и path independence; прочитан, не запускался |
| E-017 | `src/utils/Testing/test_shutdown_paths.py` | Ожидания deferred window close, AI queues и loop stop; прочитан, не запускался |
| E-018 | `src/utils/Testing/test_runtime_features.py` | Ожидания DAG/dedup/disable; прочитан, не запускался |

## Продолжение индекса по функциональным документам

Новые источники зафиксированы таблицами/разделами evidence в соответствующих документах; не создавать впечатления, что E-001—018 покрывают весь уже прочитанный код.

| Группа | Документы с точными символами/диапазонами и границами просмотра |
|---|---|
| Dialogue/prompt/providers orchestration | [llm-and-generation](../01-functional/llm-and-generation.md), [prompt-system](../01-functional/prompt-system.md), [llm-requests](../03-runtime/llm-requests.md) |
| Persistence/characters/memory | [history](../01-functional/history.md), [compression](../01-functional/history-compression.md), [characters](../01-functional/characters.md), [memory](../01-functional/memory.md), [persistence](../03-runtime/persistence.md) |
| Retrieval/derived knowledge | [rag](../01-functional/rag.md), [knowledge-graph](../01-functional/knowledge-graph.md), [reminders](../01-functional/reminders-and-timers.md) |
| AI lifecycle/management | [ai-ipc](../03-runtime/ai-ipc.md), [environments](../03-runtime/ai-environments.md), [installations](../01-functional/installations.md), [AI Hub](../02-ui/ai-hub.md) |
| Audio/input/Telegram | [voice-output](../01-functional/voice-output.md), [speech-input](../01-functional/speech-input.md), [telegram-voice](../01-functional/telegram-voice.md) |
| Unity обе стороны | [transport](../03-runtime/unity-transport.md), [retry outbox](../03-runtime/unity-retry-outbox.md), [media](../03-runtime/unity-media-transfer.md), [admission](../01-functional/unity-dialogue-admission.md), [auto dialogue](../01-functional/unity-auto-dialogue.md) |

Revision scope Unity указан в [repository-map](repository-map.md). Номера строк необходимо сверять при смене ревизии. Отсутствие runtime проверки явно отмечено: чтение тестов не считается их прохождением.

Дополнительные source inventories и границы Python-прохода: [images/capture](../01-functional/images-and-capture.md), [tools](../01-functional/tools-and-web.md), [beat](../01-functional/music-beats.md), [DSL/packs](../01-functional/prompt-language-and-packs.md), [desktop games](../01-functional/desktop-mini-games.md), [standalone web](../01-functional/standalone-web-surface.md), [navigation/help/gallery](../02-ui/navigation-gallery-and-help.md), [updates](../01-functional/launcher-and-updates.md), [diagnostics](../01-functional/diagnostics-and-data-export.md), [local IPC](../03-runtime/local-control-ipc.md), [i18n](../02-ui/localization-and-preferences.md), [providers](../01-functional/provider-configuration.md), [accounts](../01-functional/account-authentication.md), [settings](../03-runtime/settings-and-preferences-store.md), [maintenance](../01-functional/data-maintenance.md), [compatibility imports](../01-functional/compatibility-imports.md), [voice controls](../02-ui/voice-controls.md), [jobs/events](../03-runtime/background-tasks-and-events.md). Случайные rg hits и truncated output не считаются полным чтением файла.

## Новые группы исходников: Python protocol, AI install and release

| Функциональная область | Просмотренные исходники и относящаяся документация |
|---|---|
| Chat Completions / Responses | `src/handlers/llm_providers/protocols/{chat_completions,responses}/*.py`, `openai_http_base.py`, `responses_provider.py`, `protocols/history.py`; [состояния/ошибки](../03-runtime/openai-protocol-state-machines.md) |
| ASR/RAG/Beat install | `src/handlers/asr_models/{google_recognizer,gigaam_recognizer,gigaam_onnx_recognizer,whisper_recognizer,whisper_onnx_recognizer}.py`, `src/managers/rag/install_spec.py`, `src/game_connections/services/beat_install.py`; [планы](../01-functional/asr-rag-beat-install-plans.md) |
| Character voice assets | `src/installables/voice_assets.py`, `src/utils/voice_assets_installer.py`; [извлечение и удаление](../01-functional/voice-asset-distribution.md) |
| Installer lifecycle/recovery | `src/controllers/install_controller.py:476-615,788-867,896-1501`, `src/utils/pip_installer.py:830-1173`, `src/core/runtime_environments.py:453-670,1244-1308`; [контракты](../03-runtime/installer-recovery-and-uninstall.md) |
| Build/launch/release | `build.py:34-502`, `scripts/launcher.c:32-276`, `scripts/run.bat:1-17`, `scripts/run.py:62-864`, `src/release_contract.py:171-436`; [дистрибутив](../03-runtime/build-and-release-distribution.md) |
| Preliminary dependencies | `requirements.txt`, AST 720 `src/*.py` files; crosschecked `scripts/run.py:62-94,647-778`; [матрица](../04-dependencies/python-import-reachability.md) |

Источник ZIP не содержит `.git` и prompt_editor submodule; следовательно ранее зафиксированный revision SHA — *historical provenance*, не независимо проверенный commit. Никакие реальное распаковывание release assets, установка AI dependencies, login, voice inference, GPU или native launcher build не выполнялись.

Дополнительный cost source: `src/managers/context_counter.py:11-147`, `src/managers/model_pricing_manager.py:18-359`, `src/controllers/model_controller.py:992-1154,1914-1958`, `src/ui/windows/app_window_base.py:908-975`; [token budget и pricing](../01-functional/token-budget-and-pricing.md).


## Дополнительная проверка непривязанного к Core функционала и platform paths

| Группа | Фактические источники / границы | Документ |
|---|---|---|
| `HOI4` standalone эксперимент | `src/connetors/hoi4/{hoi4_server,hoi4_connector,hoi4_cheats}.py`, `src/connetors/hoi4/Mod/neuro-mita/{Events,common/on_actions}`; `rg` по всему остальному `src` не выявил Core registration, только `ProjectStructureForLLM.txt`; нельзя доказать отсутствие внешнего launcher | [HOI4 прототип](../01-functional/hoi4-standalone-prototype.md) |
| Path ownership, RAG path disagreement | `src/core/app_paths.py:7-93`, `src/core/runtime_environments.py:683-715`, `src/managers/rag/install_spec.py:76-82`, `src/handlers/ai_engine/rag_runtime.py:24-30`, `src/handlers/embedding_handler.py:37-46`; без теста release startup | [Filesystem](../03-runtime/filesystem-paths-and-native-loaders.md) |
| Unicode native loader compatibility | `src/utils/native_paths.py:13-61`, GigaAM `decoding.py:18-25`, `silero_vad_compat.py:12-29`, tests `test_asr_handler.py`; Windows runtime не тестировался | [Filesystem](../03-runtime/filesystem-paths-and-native-loaders.md) |
| Logging paths and flush semantics | `src/main_logger.py:29-55,169-208`; fatal worker `os._exit(70)` ранее исследован в `runtime_failure_policy.py` | [Filesystem](../03-runtime/filesystem-paths-and-native-loaders.md) |

Дополнительный network source: `src/core/networking/http_clients.py:17-237`, `src/core/networking/errors.py:13-374`, `src/handlers/llm_providers/http_transport.py:25-95`, `src/utils/Testing/test_http_client_registry.py`; [HTTP ownership/error audit](../03-runtime/network-client-ownership-and-errors.md).

## Settings / schema / GUI / service ownership — дополнительный source index

| Functional evidence | Изученные диапазоны | Документация |
|---|---|---|
| Общий конфиг, async saver, подписки | `src/managers/settings_manager.py:20-253`, `src/core/settings_registry.py:15-379` | [settings](../01-functional/settings-storage-and-migrations.md), [observers](../03-runtime/typed-services-and-settings-observers.md) |
| Обновление/test-release migration | `src/services/update_contour.py:10-201`; legacy journal, marker, persisted choice | [settings](../01-functional/settings-storage-and-migrations.md) |
| API preset identity/files/import/export | `src/controllers/api_presets_controller.py:77-101,127-201,241-263,435-465,587-646,690-798,990-1125,1128-1227` | [settings](../01-functional/settings-storage-and-migrations.md) |
| Model schema compatibility | `src/model_settings/{schema,repository,service,migration,bundled_json_compat}.py`, `src/managers/model_config_loader.py:11-271` | [settings](../01-functional/settings-storage-and-migrations.md) |
| Windows DPAPI account records | `src/handlers/llm_providers/chatgpt_plan_auth.py:71-92,490-555`; network/auth tests не запускались | [settings](../01-functional/settings-storage-and-migrations.md) |
| 12 settings categories; lazy access | `src/ui/pages/settings/{section_registry,section_access,settings_page_widget}.py`; `src/ui/settings/settings_binding.py:12-271`; 5 active builder static-key groups | [settings UI](../02-ui/settings-navigation-and-lazy-pages.md) |
| ServiceRegistry/typed ownership and event distinctions | `src/core/services.py:24-227`, `src/startup/api_configuration.py:13-65`, `src/core/events.py:17-405,430-523`, `src/core/serial_dispatcher.py:24-165` | [typed services](../03-runtime/typed-services-and-settings-observers.md) |

Новые документы не подтверждают remote provider calls, Windows-only runtime или сохранённые пользовательские credential values. Никаких реальных секретов из пользовательских конфигов не извлекалось.

## Новые GUI и graph source доказательства — granular continuation

| Направление | Исходники | Подробный документ |
|---|---|---|
| 83 literal GUI setting keys и dynamic consumers | `src/ui/settings/{general_settings,dialogue_settings,game_settings,debug_settings,model_interaction_settings}.py`, `src/controllers/gui/settings_page_view_model.py` и target consumers | [settings key matrix](../02-ui/settings-key-consumer-evidence.md) |
| Graph GC/merge/retype | `src/managers/rag/graph/{entity_gc.py,entity_typing.py}`, `src/controllers/gui/rag_memory_controller.py` | [graph maintenance](../01-functional/graph-maintenance-and-entity-lifecycle.md) |
| Graph viewer Qt actions | `src/ui/dialogs/{db_viewer,graph_view_widget}.py` и controller | [graph viewer](../02-ui/graph-viewer-interactions.md) |
| Sandbox controls / game connection effect | `src/ui/pages/sandbox_page.py:957-975`, `src/controllers/gui/{sandbox_page_view_model,sandbox_page_controller}.py` | [sandbox](../02-ui/sandbox-page-functional-contract.md) |
| Chat attachment / temp staging | `src/controllers/gui/{chat_panel_view_model,app_shell_controller}.py`, `src/controllers/chat_controller.py:1266-1297`, `src/ui/widgets/chat_panel.py` | [composer](../02-ui/chat-composer-and-attachments.md) |
| Chat presentation and message actions | `src/ui/chat/{presentation_coordinator,message_renderer,message_widget}.py`, `src/controllers/gui/chat_message_actions_view_model.py` | [reconciliation/actions](../02-ui/chat-stream-history-and-message-actions.md) |
| Structured output mode and renderer | `src/ui/chat/{structured_panel,message_renderer}.py`, `src/ui/settings/debug_settings.py:43-73` | [structured](../02-ui/structured-ai-results-presentation.md) |
| Gallery files/cache/viewer | `src/services/photo_gallery.py:11-70`, `src/controllers/gui/gallery_page_view_model.py:19-133`, `src/ui/pages/gallery_page.py:32-281`, `src/ui/widgets/gallery_grid.py:24-191`, `src/ui/dialogs/gallery_viewer.py:25-208` | [gallery](../02-ui/gallery-lifecycle-and-photo-viewer.md) |
| Character library/action routing | `src/ui/settings/character_settings/ui.py:140-584`, `src/controllers/gui/character_settings_logic.py:275-298,515-638,894-1000,1670-2135`, `src/controllers/gui/character_settings_view_model.py:11-35` | [characters](../02-ui/character-library-and-maintenance-actions.md) |

Эта дополнительная секция означает проверенные статические входы/callback, а не исполненные Qt/unit/integration tests.

### Дополнительный granular News/Logs source

`src/controllers/gui/news_page_view_model.py:17-67`, `src/ui/pages/news_page.py:19-132`, `src/controllers/gui/logs_page_view_model.py:18-81`, `src/ui/pages/logs_page.py:33-191`; [контракты и источники](../02-ui/news-and-logs-live-ui-contracts.md). Remote GitHub API/UI OS open не выполнялись.

### Home launcher UI evidence

`src/controllers/gui/home_page_view_model.py:76-183,283-373,459-670,671-790`, `src/ui/pages/home_page.py:146-244,330-412,515-583`, [контракт update action/result](../02-ui/home-launcher-update-and-game-state.md). Source only; real updater/Unity not executed.

### Wiki/localized markdown source

`src/ui/pages/wiki_page.py:136-220,529-857`, `src/ui/windows/guide_dialog.py:14-85`, `src/ui/widgets/guide_widget.py` — [navigation and Unicode-anchor semantics](../02-ui/wiki-navigation-localization-and-anchors.md). Pure slug regex проверен на кириллице; QTextDocument offscreen tests не запускались.

### Guide / representative QDialog lifecycle proof

`src/ui/widgets/guide_widget.py:15-208,701-713,790-987,1003-1240,1249-1920`, `src/ui/windows/guide_dialog.py:14-85`: [Guide](../02-ui/guide-walkthrough-and-image-focus.md). **Only 13 pages in `_init_pages` registered**; historical classes left unregistered.

`src/ui/dialogs/background_task_dialog.py:93-296`, `src/controllers/gui/character_settings_logic.py:1816-1914`, `src/ui/dialogs/message_processing_dialog.py:39-348`, `src/controllers/gui/protocol_pipeline_gui_controller.py:13-60`, `src/ui/dialogs/export_dialog.py:23-256`, `src/ui/dialogs/db_export_dialog.py:16-135`, `src/ui/dialogs/styled_message.py:39-90`: [Dialog lifecycle](../02-ui/dialog-interaction-and-background-task-contracts.md). Только source evidence, не GUI E2E.

## Новый проход: world lore, environment, GameMaster и group projection

| Домен | Конкретный исходник/диапазоны | Доказанное поведение / документ |
|---|---|---|
| Per-character world lore | `src/domain/world_character_relations.py:10-242`; `src/domain/world_contexts/*_house.json`; `src/controllers/model_controller.py:1409-1429` | семь world resources, normalized IDs, owner/former/visitor/individual context, request-local snapshot → [world-awareness](../01-functional/character-world-and-environment-awareness.md) |
| Реальная среда персонажа | `src/services/character_environment_context.py:22-304`; `src/controllers/main_controller.py:151-160`; `src/controllers/prompt_controller.py:243-284,1204-1212`; `src/controllers/gui/presentation_hub.py:1030-1045` | installed vs connected world, voice readiness by method, update, model self-awareness → [environment-awareness](../01-functional/character-world-and-environment-awareness.md) |
| Источник player text | `src/services/contracts.py:577-600`; `src/controllers/prompt_controller.py:286-312` | app/game/none, conditional transition system message → [message source](../01-functional/character-world-and-environment-awareness.md) |
| Действующий GM task | `src/game_connections/handlers/actions/create_task.py:542-588`; `src/controllers/chat_controller.py:784-928`; `src/controllers/prompt_controller.py:848-925,1218-1257`; `src/controllers/server_controller.py:458-481` | GM observe/command, policy, structured intent, runtime-events directive; automatic enable gate → [scene director](../01-functional/game-master-scene-direction.md) |
| New control plane, неподтверждённый production | `src/domain/game_master.py:8-46`; `src/schemas/game_master_response.py:12-49`; `src/services/game_master_{services,scheduler,directive_registry,context_builder,action_executor}.py`; `src/services/dialogue_transcript_service.py` | rule lifetime/priority/target, routing, bounded conversation transcript; точка создания в production не установлена → [GM alternatives](../01-functional/game-master-scene-direction.md) |
| Session/projection | `src/services/contracts.py:522-576,603-733`; `src/services/dialogue_runtime_state.py:15-117`; `src/controllers/chat_controller.py:518-529`; `src/controllers/gui/chat_panel_view_model.py:39-75`; `src/ui/chat/dialogue_presentation.py:6-40`; `src/ui/widgets/chat_panel.py:99-114` | identity и typed snapshot, event → presentation, disconnect clearing, group title → [conversation projection](../03-runtime/conversation-session-projections.md) |
| Unity state vs prompt provenance | `src/game_connections/handlers/actions/create_task.py:344-393`; `src/managers/game_state_manager.py:8-61`; `src/controllers/model_controller.py:306-329`; `src/controllers/prompt_controller.py:654-834,1026-1079,1118-1183` | per-character sticky fields vs transient runtime_events/TV; static rules/intent/catalog vs dynamic capabilities/world/turn events; connected gate → [Unity world state projection](../03-runtime/unity-world-state-prompt-projections.md) |

Этот срез — статическое чтение конкретной source snapshot из `CodeNow.zip`, без fetch новой ревизии и без запусков Python/Unity/CUDA.

## 2026-10-31: независимые functional evidence paths

| Источник Python `src/` | Проверенная цепочка | Документ |
|---|---|---|
| `controllers/model_controller.py`, `schemas/structured_response.py`, `characters/character.py` | trusted structured response→character/Unity effect consumers | [effects](../01-functional/structured-character-actions-and-side-effects.md) |
| `installables/catalog_manifest.py:42-1059`, `registry_builder.py`, `services/installable_catalog_service.py` | static/dynamic installables and readiness/status differences | [installable catalog](../01-functional/installable-catalog-and-runtime-readiness-matrix.md) |
| `services/remote_voice_repository.py`, `services/remote_voice_service.py`, `handlers/remote_voice/fish_audio.py` | remote voice credentials, character-scoped presets and request routing | [remote voice](../01-functional/remote-voice-presets-and-character-routing.md) |
| `handlers/asr_models/registry.py`, `ui/settings/microphone_settings.py` and ASR presentation/VM | ASR engine selection and model gallery | [ASR UI](../02-ui/asr-model-gallery-and-settings-workflows.md) |
| `ui/settings/voiceover_settings.py`, `handlers/voice_models/*` | local TTS/VC model selection and compiled package dialogs | [voice UI](../02-ui/local-voice-model-management-and-compile-dialogs.md) |
| `ui/settings/api_settings/*`, `ui/settings/api_settings/dialogs/model_parameters_dialog.py` | model provider preset/profile + parameter schema editor | [API UI](../02-ui/api-presets-and-model-parameter-editor-workflows.md) |
| `controllers/gui/rag_preset_view_model.py`, `embed_provider_view_model.py`, `rag_install_view_model.py` | RAG pipeline/user embedding settings | [RAG UI](../02-ui/rag-pipeline-and-embedding-provider-user-workflows.md) |
| `ui/windows/app_window_base.py:332-387`, `ui/dialogs/context_viewer_dialog.py:193-1599` | message action→request/response inspection and copy | [context viewer](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `controllers/gui/character_settings_logic.py:1512-1523`, `ui/dialogs/db_viewer.py:85-1660` | scoped/global DB viewer, edit, multimedia metadata | [DB viewer](../02-ui/context-and-sqlite-data-inspection-workflows.md) |
| `managers/finetune_collector.py:25-420`, `ui/settings/data_settings.py:89-420`, `ui/dialogs/export_dialog.py:23-260` | sample capture, rating, retention, export | [fine-tuning data](../01-functional/fine-tuning-data-capture-curation-and-export.md) |
| `services/hardware_inventory_service.py:75-442`, `controllers/gui/ai_engine_settings_view_model.py:18-262`, `controllers/ai_engine_controller.py:2325-2437`, `services/ai_environment_maintenance_service.py:20-179` | GPU inventory, shared/split topology and full reset | [AI administration](../01-functional/hardware-acceleration-and-ai-engine-administration.md) |
| `managers/rag/rag_utils.py:58-334`, `managers/rag/pipeline/query_builder.py:11-80`, `utils/__init__.py:316-502` | Cyrillic lexeme/stem/FTS and separate TTS numeral/text processing | [linguistics](../01-functional/language-normalization-rag-morphology-and-speech-numerals.md) |
| `__main__.py`, `controllers/main_controller.py`, UI registries, installable registry/dynamic imports (AST scan) | known composition vs optional loader distinction | [dynamic boundaries](../04-dependencies/dynamic-loader-reachability-and-core-ai-boundaries.md) |

Проверка статическая, не приравнивать пути импортов к факту исполнения условной ветки. Не запускались Windows/GPU/Qt/remote APIs; не внесены изменения в `src`.

## Character catalog и полный requirements snapshot (30-minute functional pass)

| Функциональный объект | Конкретная source evidence | Подтверждённый контракт |
|---|---|---|
| 9 действующих characters, stable/display/storage/voice identity | `src/managers/character_manager.py:27-51`; `src/characters/__init__.py:9-194,232-256`; `src/ui/character_names.py:5-26` | Регистрируются 8 обычных персонажей + GameMaster, пользовательские начальные значения и особые `secret_exposed` rules; [catalog](../01-functional/registered-character-catalog-and-identity-contracts.md) |
| Ленивые Character runtimes, available vs loaded vs current | `src/managers/character_manager.py:57-199`; `src/characters/character.py:93-173,213-250` | Промпты/конфиг инициализируются при materialize, history/memory загружаются при ensure; первоначальный unknown ID → `Crazy` |
| Граница `gui_only` | `src/services/character_registry.py:8-81`; `src/controllers/character_controller.py:19-42` | Registry в GUI-only хранит только выбранный ID; не выдаёт фальшивую загруженную модель персонажа |
| Runtime commands: select/reload/clear | `src/controllers/character_controller.py:52-114`; `src/managers/character_manager.py:201-227` | Переключение и bulk clearing поддерживают loaded и unloaded, user-facing status события |
| 84 объявленных зависимостей, 32 direct mappings / 52 без прямого AST import | `requirements.txt:1-90` + 720 AST-parsed `src/**/*.py`; `src/core/install_requirements.py`; `scripts/run.py` | Разделение wheel manifest / direct usage / optional native/AI environment, без ложного вывода «unused»; [ledger](../04-dependencies/full-requirements-runtime-evidence-ledger.md) |


## Новый functional evidence (локальный Python snapshot, без исполнения UI)

| Source path / ranges | Подтверждает | Документ |
|---|---|---|
| `src/managers/rag/pipeline/repositories/{history_repo,memory_repo}.py:25-289`, `pipeline/retrievers/{vector,fts,keyword_only}.py`, `rag_manager.py:480-1395` | Корпусы, идентификаторы кандидатов, lexical/vector/sentence retrieval и modes reindex | [RAG](../01-functional/rag-storage-retrieval-and-indexing-modes.md) |
| `src/core/backends/installable_component.py:18-105`, `src/installables/{ffmpeg_component,opencv_component,voice_assets}.py`, RAG `install_spec.py` | Инсталляционный каталог: readiness/installed и раздельные операции компонентов | [Probes/actions](../01-functional/installable-component-probe-and-operation-contracts.md) |
| `src/handlers/asr_models/{registry,speech_recognizer_base}.py`, `src/handlers/voice_models/base_model.py` | ASR engine discovery, model install, TTS model variants, required backends и worker activation | [AI managed backend](../01-functional/asr-tts-managed-backend-operational-contracts.md) |
| `src/ui/settings/api_settings/dialogs/models_loaded_dialog.py:38-492`, `src/controllers/gui/api_settings/test_mixin.py:80-209`, `voiceover_controller.py:1600-1673` | API models list/test/actions, voice modal hide/cancel | [UI dialogs](../02-ui/api-model-discovery-and-conditional-dialogs.md) |
| `src/ui/settings/game_settings.py:35-247,249-386,462-640` | Ручные mini-games, Unity target selection, Beat cache status/reindex | [Games and Beat](../02-ui/game-settings-manual-launch-and-beat-cache.md) |
| `src/ui/settings/screen_analysis_settings.py:23-493`, `src/utils/image_cleanup.py:25-163`, `src/game_connections/handlers/actions/create_task.py:657-673` | Screen/webcam/Unity camera, orphan images, image provenance and snapshot task | [Screen/images](../02-ui/screen-camera-image-management-user-contracts.md) |

## Дополнение: external runtime registration

| Source path | Behaviour | Specification |
|---|---|---|
| `src/controllers/main_controller.py:114-180,305-343,483-504`, `model_controller.py:60-68,1480-1508`, `src/web/server.py:1-37`, `src/connetors/hoi4/hoi4_connector.py` | Реальные / optional / standalone границы внешних интеграций | [External routes](../01-functional/external-integration-entrypoints-and-reachability.md) |


## Дополнение: RAG scoring pipeline

| Source | Behaviour | Spec |
|---|---|---|
| `src/managers/rag/rag_manager.py:821-1102`, `pipeline/{query_builder,types,combiner,reranker,cross_encoder}.py` | QueryState, retrieval buckets, 5 combiners, enrich/linear/CE/graph minimum, public outputs и asynchronous access stats | [RAG rank](../01-functional/rag-query-fusion-reranking-and-result-contracts.md) |


## Дополнение: RAG generation-time injection

| Source | Behaviour | Spec |
|---|---|---|
| `src/controllers/model_controller.py:1384-1405,1996-2120`; `src/controllers/prompt_controller.py:960-961,1080-1081,1156-1185` | RAG gating, source-specific prompt templates, fresh Unity dynamic context after retrieval | [RAG prompt](../01-functional/rag-context-injection-and-source-rendering.md) |

- `src/core/runtime_ipc.py:18-90`; `src/services/runtime_ipc_service.py:25-231`; `src/controllers/main_controller.py:121-127,218,684-686`; `src/controllers/ai_engine_controller.py:1973-2011`; `src/ui/settings/general_settings.py:185-222`; `src/utils/Testing/test_runtime_ipc.py:53-137`: registered conditional local control-plane and six allowed commands. [IPC contract](../01-functional/local-runtime-ipc-external-control-contract.md).

- `src/ui/windows/app_window_base.py:246,1660-1710`; `src/ui/widgets/eula_widget.py:10-25,166-248`; `src/localization/eula_texts.py:419-435`: first-run EULA gate, language before consent, accept/reject and Guide→Wiki. [First run](../02-ui/first-run-agreement-language-and-guide-flow.md).

- `src/services/hardware_inventory_service.py:25-373`; `src/infrastructure/audio/windows_endpoint_identity.py:13-108`; `src/services/unity_process_guard.py:11-134`; `src/handlers/llm_providers/chatgpt_plan_auth.py:525-555`; `src/utils/native_paths.py:13-61`: native Windows system capabilities and AI loader ownership. [Native boundaries](../04-dependencies/native-system-api-and-ai-library-ownership.md).


## Следующий functional pass: components, statuses, UI indicators

| Source | Проверенный контракт | Документ |
|---|---|---|
| `src/installables/catalog_manifest.py:42-902,909-1042`, `src/installables/registry_builder.py` | 31 fixed non-RAG + dynamic preset/custom RAG + aggregate lookup | [Catalog identity](../01-functional/installable-catalog-identity-and-coverage.md) |
| `src/services/installable_catalog_service.py:39-124,206-316,616-709,774-924`, `src/controllers/gui/ai_hub_view_model.py:110-145,300-416` | Context-fingerprinted probe, bounded pending/stale, status event, selective UI refresh | [Status observation](../03-runtime/installable-status-observation-and-invalidation.md) |
| `src/controllers/installable_controller.py:165-275`, `src/controllers/gui/install_gui_controller.py:22-168,235-392` | Admission, FIFO, task ID dedup, queued/running cancel, headless/UI, quiesce | [Install queue](../03-runtime/install-operation-admission-queue-and-completion.md) |
| `src/ui/windows/ai_hub/dialog.py:390-399,743-1003,1113-1225`, `src/controllers/gui/ai_hub_view_model.py:71-298,418-542` | GUI action→intent→result/checking/queue/dirty form | [AI Hub actions](../02-ui/ai-hub-interaction-traceability-checklist.md) |
| `src/controllers/gui/status_controller.py:17-205`, `src/ui/windows/app_window_base.py:1335-1412`, `src/ui/widgets/mita_status_widget.py:21-240`, `src/ui/widgets/status_indicators_widget.py:10-120` | Generation/compression/tool errors, activity count, message voice marker and independent status chips | [Status UI](../02-ui/generation-progress-error-and-voice-indicators.md) |


## Dialogue actor identity / turn provenance (2026-10-31 continuation)

- `src/services/contracts.py:523-570`, `src/domain/dialogue_identity.py:6-24`, `src/services/dialogue_identity_resolver.py:15-95`: distinction actor instance ↔ character identity, authoritative sender resolution. [Контракт](../01-functional/dialogue-actor-and-message-identity-contracts.md).
- `src/services/dialogue_target_resolver.py:13-114`, `src/domain/conversation_message_ids.py:6-28`, `src/managers/conversation_event_writer.py:235-304,370-465`: unique target resolution, message/turn ID and conversation fanout/provenance. [Контракт](../01-functional/dialogue-actor-and-message-identity-contracts.md).
- `src/services/dialogue_runtime_state.py:12-81`, `src/services/dialogue_transcript_service.py:12-113`: ephemeral UI snapshot vs not-proven-live GM transcript; client disconnect reset. [Контракт](../01-functional/dialogue-actor-and-message-identity-contracts.md).


- `src/services/llm_stream.py:7-44`, `src/handlers/llm_providers/streaming.py:90-311`, `src/services/stream_presentation.py:10-136`, `src/controllers/chat_controller.py:571-670`: typed provider event and separate display lifecycle, role switch/flush. [Stream contract](../03-runtime/llm-stream-event-and-presentation-lifecycle.md).


## Pass 11 — новые исходные маршруты

- `src/controllers/prompt_controller.py:400-485; src/DSL/dsl_engine.py:422-1004`: prompt building, author DSL, controlled side effects. [Контракт](../01-functional/dsl-executable-prompt-contract.md).
- `src/characters/character.py:409-631; src/DSL/post_dsl_engine.py:43-376`: post-generation transformation and custom state. [Контракт](../01-functional/post-dsl-response-rules-and-debug-state.md).
- `src/managers/game_manager.py:11-173; src/modules/Chess/game_instance.py:143-239; src/modules/SeaBattle/seabattle_instance.py`: two rulesets and game-bound character reactions. [Контракт](../01-functional/minigame-chess-seabattle-state-and-character-reactions.md).
- `src/managers/action_memory.py:10-178; src/controllers/history_controller.py:248-302,1325-1355,1822-1830`: retained requested action context across summary. [Контракт](../01-functional/structured-action-history-and-compression-bridge.md).
- `src/managers/core_memory_triggers.py:24-136; src/controllers/model_controller.py:1380-1407`: deterministic story state distinct from access control. [Контракт](../01-functional/exact-core-memory-triggers-and-session-activation.md).
- `src/services/microphone_selection.py; src/services/microphone_monitor.py; src/infrastructure/audio/portaudio_catalog.py`: physical microphone selection, monitoring and hotplug. [Контракт](../01-functional/microphone-physical-identity-backends-and-monitoring.md).
- `src/controllers/speech_controller.py; src/managers/speaking_window.py; src/game_connections/handlers/actions/speech_state.py`: microphone gating against local+Unity playback. [Контракт](../01-functional/asr-speech-arbitration-and-unity-speaking-leases.md).
- `src/core/events.py`: event fact/command/progress distinction. [Контракт](../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md).
- `src/game_connections/server.py; src/controllers/server_controller.py`: seven inbound Unity request families and ownership. [Контракт](../03-runtime/unity-ingress-seven-actions-and-state-outcomes.md).
- `src/controllers/gui/intent_view_model.py:18-387; src/controllers/gui/gallery_page_view_model.py:43-128`: freshness, exclusive side effects, refresh coalescing. [Контракт](../02-ui/intent-workloads-and-visible-state-consistency.md).
- `src/core/events.py` и AST вызовов `.subscribe/.emit/.try_emit`: [producer/consumer event callsite matrix](event-producer-consumer-callsite-index.md); статическая, не E2E.

- `src/__main__.py:59-122,317-352`, `src/startup/headless_runtime.py:14-157`, `src/controllers/main_controller.py:65-110,169-190,192-291`, `src/services/telegram_auth_service.py:34-71`: [headless capability/readiness](../03-runtime/headless-core-functional-surface-and-readiness.md).
- `src/controllers/gui/intent_view_model.py:18-387` + 52 callsites в `src/controllers/gui/*_view_model.py`: [синтаксический индекс GUI операций](gui-async-operation-callsite-index.md).
- `src/utils/command_parser.py:23-305`, `src/DSL/path_resolver.py:154-236`, `src/services/game_master_services.py`, `src/web/server.py`, `src/handlers/ai_engine/inprocess_engine.py`: [недоказанные и самостоятельные пути](standalone-and-unproven-runtime-reachability.md).

- `src/installables/catalog_manifest.py:42-1042`, `src/installables/registry_builder.py:13-154`: [31-component exact identity/validation matrix](../06-design-input/installables-component-by-component-parity-matrix.md); dynamic RAG separate, machine E2E absent.

## Pass 12 — навигация по новым source-evidence маршрутам

- `src/controllers/gui/window_composition_controller.py:35-205`, `src/controllers/gui/protocol_pipeline_gui_controller.py:14-44`, `src/controllers/gui/api_settings/controller.py:233-280`, `src/ui/window_manager.py:16-225`: 6+1 зарегистрированных окон и различение `ProtocolPipelineDialog` / активного `MessageProcessingDialog`. [Документ](../02-ui/dialog-class-reachability-and-action-outcomes.md).
- `src/controllers/model_controller.py:797-912,2815-2820`, `src/controllers/gui/view_event_controller.py:6-58`, `src/controllers/capture_controller.py:198-219,335-391`, `src/controllers/chat_controller.py:410,1240+`: события со строковым именем, paging history, периодические изображения и GUI loader. [Source-event index](raw-string-event-reachability-and-ui-bridges.md).
- `src/controllers/graph_controller.py:117-373`, `src/controllers/gui/rag_memory_controller.py:139-439,1136-1245`: inline/utility/batch paths graph extraction, source-provenance tagging. [Graph ingestion](../01-functional/graph-ingestion-manual-realtime-inline-and-provenance.md).
- `src/controllers/gui/rag_memory_controller.py:682-1814`: 15 сборщиков 100 дескрипторов/99 unique memory+RAG settings; [UI descriptions](../02-ui/memory-rag-registered-settings-source-index.md), [99-key external consumer matrix](rag-settings-direct-consumer-evidence-index.md).
- `src/ui/widgets/chat_panel.py:307-333`, `src/controllers/gui/character_settings_logic.py:973-1251,1405-2256`, `src/controllers/gui/api_settings/model_settings_controller.py:52-74`, `src/ui/settings/game_settings.py:98-137,336-356`: системные file/input dialogs и scopes destructive/long-running actions. [File/input](../02-ui/native-dialogs-and-file-input-output-workflows.md), [confirmations](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md).
- `src/ui/settings/rag_preset_widget.py:34-186`, `src/controllers/gui/rag_preset_view_model.py:37-245`, `src/managers/rag/pipeline/config.py:20-121`: состояние, намерения, snapshot user presets, Apply и модели. [RAG preset flow](../02-ui/rag-preset-complete-user-journey-and-model-readiness.md).
- `src/ui/{pages,settings,dialogs,windows,widgets}/**/*.py`, `src/controllers/gui/**/*.py`: 517 AST signal `.connect()` callsites / 75 files вне Testing/not_used; [индекс](gui-signal-registration-callsite-index.md). Это не E2E confirmation активных окон.
- `src/utils/ffmpeg_installer.py`, `src/utils/audio_converter.py`, `src/utils/archive_utils.py`, `src/services/hardware_inventory_service.py`, `src/handlers/ai_engine/worker_process.py`: external executables и Windows native loader как самостоятельные conditional resource boundaries. [Dependencies](../04-dependencies/external-executables-and-native-loader-functional-boundaries.md).

- `src/managers/rag/readiness.py:73-100`; `src/controllers/embedding_controller.py:34-304`; `src/controllers/reranker_controller.py:97-139`; `src/managers/rag/pipeline/cross_encoder.py:52-173`; `src/utils/Testing/test_rag_restart_state.py:44-217` → [RAG readiness lifecycle](../01-functional/rag-model-runtime-readiness-and-worker-generation.md).
- `src/managers/rag/rag_manager.py`, `src/managers/rag/pipeline/types.py`, `src/utils/Testing/test_rag_search_golden.py`, `test_rag_units_golden.py` → [RAG deterministic surface](../01-functional/rag-deterministic-golden-surface-and-result-types.md).

- `src/managers/history_ui_projector.py:8-138`, `src/controllers/model_controller.py:794-923,2825-2857`, `src/utils/Testing/test_history_ui_projector_multi_mita.py`, `test_dialogue_sender_identity.py` → [UI history identity and paging](../01-functional/history-ui-projection-actor-identity-and-paging.md).
- `src/utils/Testing/test_*.py`: 250 файлов, AST 2177 test function declarations → [исходный test inventory](test-suite-static-validation-map.md).

- `src/managers/provider_manager.py:15-46`; `src/handlers/asr_models/registry.py:8-48`; `src/managers/tools/tool_manager.py:14-103`; `src/managers/tools/dialects/registry.py:16-88`; `src/installables/registry_builder.py:13-76`; `src/ui/pages/main_page_registry.py:10-56`; `src/ui/pages/settings/section_registry.py:16-189`; `src/handlers/ai_engine/worker_process.py:250-280` → [dynamic registry contract](../04-dependencies/dynamic-import-registries-and-runtime-capability-contracts.md).

- Статический индекс 24 production dynamic import/native load callsites в 18 исходниках: [отчёт](production-dynamic-import-callsite-index.md), 0 AST parse errors; не означает 24 достигнутых runtime routes.
