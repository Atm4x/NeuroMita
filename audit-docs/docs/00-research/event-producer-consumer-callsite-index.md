# Static event producer/consumer callsite index

**Evidence source:** AST parse of the current CodeNow Python `src/**/*.py`, excluding `src/utils/Testing/`, `src/ui/not_used/` and `src/Lib/` (the dedicated runtime audit addresses their individual status). This is a **snapshot of explicit syntax**, not a proof of runtime registration, callback execution, or end-to-end reachability. Dynamic names/string literals, aliases and registration loops are not captured. Re-run from the relevant revision before declaring full coverage.

**Static measurements:** 717 Python modules parsed; 288 event constants defined by nested `Events` classes (`src/core/events.py:524+`), 288 distinct wire names; 202 event constants explicitly passed to `.emit(...)`, `.try_emit(...)` or `.subscribe(...)` in the scanned modules; **117** names have syntactic examples of both emission and subscription; **13** emission-only; **72** subscription-only in this limited scan. `Events.*` constants never referenced by direct matched calls are not implicitly active.

**Important interpretation:** `emit-only` does not imply an unhandled event; callback registration can use an intermediate alias, raw name or GUI signal. `subscribe-only` does not imply an unreachable action; producers can emit using dynamic event variables. `both` is a *candidate route* that still needs an active composition root and conditions. `get_*`/`_get_` names are rejected by the current EventBus as query-like, even where legacy declarations/subscriptions exist (see `src/core/events.py:170-180,390-405`).

## Candidate routes with both direct producer and consumer callsites

| Event | Wire value | Example producer | Example subscriber |
|---|---|---|---|
| `AI.ENGINE_EVENT` | `ai_engine_event` | `src/controllers/ai_engine_controller.py:1619` (+5) | `src/handlers/asr_handler.py:177` |
| `AI.SERVICE_RESTARTED` | `ai_service_restarted` | `src/controllers/ai_engine_controller.py:1644` (+1) | `src/controllers/embedding_controller.py:156` (+3) |
| `ApiPresets.DELETE_CUSTOM_PRESET` | `delete_custom_preset` | `src/controllers/gui/api_settings/editor_mixin.py:723` | `src/controllers/api_presets_controller.py:436` |
| `ApiPresets.PRESET_DELETED` | `preset_deleted` | `src/controllers/api_presets_controller.py:1142` | `src/controllers/gui/api_settings/controller.py:202` |
| `ApiPresets.PRESET_SAVED` | `preset_saved` | `src/controllers/api_presets_controller.py:1120` | `src/controllers/gui/api_settings/controller.py:201` |
| `ApiPresets.SAVE_PRESETS_ORDER` | `save_presets_order` | `src/controllers/gui/api_settings/editor_mixin.py:755` | `src/controllers/api_presets_controller.py:444` |
| `ApiPresets.SAVE_PRESET_STATE` | `save_preset_state` | `src/controllers/gui/api_settings/editor_mixin.py:298` | `src/controllers/api_presets_controller.py:440` |
| `ApiPresets.SET_CURRENT_PRESET_ID` | `set_current_preset_id` | `src/controllers/gui/api_settings/editor_mixin.py:637` | `src/controllers/api_presets_controller.py:442` (+1) |
| `ApiPresets.TEST_CONNECTION` | `test_connection` | `src/controllers/gui/api_settings/test_mixin.py:109` | `src/controllers/api_presets_controller.py:439` |
| `ApiPresets.TEST_FAILED` | `test_failed` | `src/controllers/api_presets_controller.py:1276` (+2) | `src/controllers/gui/api_settings/controller.py:199` |
| `ApiPresets.TEST_RESULT` | `test_result` | `src/controllers/api_presets_controller.py:1332` (+5) | `src/controllers/gui/api_settings/controller.py:198` |
| `Audio.CANCEL_MODEL_LOADING` | `cancel_model_loading` | `src/controllers/gui/voiceover_controller.py:168` (+6) | `src/controllers/gui/audio_model_controller.py:14` (+1) |
| `Audio.CHANGE_VOICE_LANGUAGE` | `change_voice_language` | `src/controllers/gui/voiceover_controller.py:271` | `src/controllers/local_voice_controller.py:74` |
| `Audio.DELETE_SOUND_FILES` | `delete_sound_files` | `src/controllers/gui/app_shell_controller.py:114` | `src/controllers/audio_controller.py:59` (+1) |
| `Audio.FINISH_MODEL_LOADING` | `finish_model_loading` | `src/controllers/local_voice_controller.py:262` (+1) | `src/controllers/gui/audio_model_controller.py:13` (+1) |
| `Audio.MITA_SPEAKING_WINDOW` | `mita_speaking_window` | `src/controllers/audio_controller.py:69` (+1) | `src/controllers/speech_controller.py:185` |
| `Audio.UPDATE_MODEL_LOADING_STATUS` | `update_model_loading_status` | `src/controllers/local_voice_controller.py:251` (+5) | `src/controllers/gui/audio_model_controller.py:12` (+1) |
| `Audio.VOICEOVER_REQUESTED` | `voiceover_requested` | `src/controllers/chat_controller.py:930` | `src/controllers/audio_controller.py:56` |
| `Capture.STOP_CAMERA_CAPTURE` | `stop_camera_capture` | `src/controllers/gui/app_shell_controller.py:113` | `src/controllers/capture_controller.py:73` (+1) |
| `Capture.STOP_SCREEN_CAPTURE` | `stop_screen_capture` | `src/controllers/gui/app_shell_controller.py:112` | `src/controllers/capture_controller.py:72` (+1) |
| `Capture.UPDATE_LAST_IMAGE_REQUEST_TIME` | `update_last_image_request_time` | `src/controllers/chat_controller.py:1183` (+1) | `src/controllers/capture_controller.py:70` |
| `Character.CLEAR_ALL_HISTORIES` | `character_clear_all_histories` | `src/controllers/gui/character_settings_logic.py:1000` | `src/controllers/character_controller.py:42` |
| `Character.CLEAR_HISTORY` | `character_clear_history` | `src/controllers/gui/character_settings_logic.py:988` (+1) | `src/controllers/character_controller.py:41` |
| `Character.CURRENT_CHANGED` | `character_current_changed` | `src/controllers/character_controller.py:70` (+1) | `src/controllers/gui/character_settings_logic.py:562` (+2) |
| `Character.HISTORY_CLEARED` | `character_history_cleared` | `src/controllers/character_controller.py:108` (+1) | `src/controllers/gui/app_shell_controller.py:53` |
| `Character.RELOAD_ALL_DATA` | `character_reload_all_data` | `src/controllers/gui/character_settings_logic.py:296` (+1) | `src/controllers/character_controller.py:38` |
| `Character.RELOAD_DATA` | `character_reload_data` | `src/controllers/gui/character_settings_logic.py:298` (+1) | `src/controllers/character_controller.py:37` |
| `Character.SET_CURRENT` | `character_set_current` | `src/controllers/gui/sandbox_page_controller.py:55` (+2) | `src/controllers/character_controller.py:35` (+1) |
| `Chat.CANCEL_ACTIVE_GENERATIONS` | `chat_cancel_active_generations` | `src/controllers/gui/app_shell_controller.py:188` | `src/controllers/chat_controller.py:405` |
| `Chat.CLEAR_CHAT` | `clear_chat` | `src/controllers/gui/app_shell_controller.py:139` | `src/controllers/chat_controller.py:411` (+1) |
| `Chat.CLEAR_STAGED_IMAGES` | `clear_staged_images` | `src/controllers/gui/app_shell_controller.py:343` (+1) | `src/controllers/chat_controller.py:414` (+1) |
| `Chat.GENERATION_ACTIVITY_CHANGED` | `chat_generation_activity_changed` | `src/controllers/chat_controller.py:386` | `src/controllers/gui/chat_panel_view_model.py:75` (+1) |
| `Chat.INSERT_SYSTEM_MESSAGE` | `chat_insert_system_message` | `src/controllers/gui/app_shell_controller.py:451` | `src/controllers/chat_controller.py:421` |
| `Chat.LOAD_SNAPSHOT` | `chat_load_snapshot` | `src/controllers/gui/app_shell_controller.py:466` | `src/controllers/chat_controller.py:423` |
| `Chat.SAVE_SNAPSHOT` | `chat_save_snapshot` | `src/controllers/gui/app_shell_controller.py:461` | `src/controllers/chat_controller.py:422` |
| `Chat.SEND_MESSAGE` | `send_message` | `src/controllers/chat_controller.py:1404` (+11) | `src/controllers/chat_controller.py:404` (+1) |
| `Chat.STAGE_IMAGE` | `stage_image` | `src/controllers/gui/chat_panel_view_model.py:299` | `src/controllers/chat_controller.py:413` (+1) |
| `Core.LOOP_READY` | `loop_ready` | `src/controllers/loop_controller.py:38` | `src/controllers/telegram_controller.py:60` |
| `Dialogue.RUNTIME_STATE_CHANGED` | `dialogue_runtime_state_changed` | `src/services/dialogue_runtime_state.py:105` | `src/controllers/gui/chat_panel_view_model.py:68` |
| `EmbeddingPresets.PRESET_DELETED` | `embed_preset_deleted` | `src/controllers/embedding_presets_controller.py:418` (+1) | `src/controllers/embedding_controller.py:155` |
| `EmbeddingPresets.PRESET_SAVED` | `embed_preset_saved` | `src/controllers/embedding_presets_controller.py:353` (+1) | `src/controllers/embedding_controller.py:154` |
| `GUI.APPEND_STREAM_CHUNK_UI` | `append_stream_chunk_ui` | `src/controllers/chat_controller.py:579` | `src/controllers/gui/chat_controller.py:13` |
| `GUI.CLEAR_CHAT_MESSAGE_ERROR` | `clear_chat_message_error` | `src/controllers/chat_controller.py:1400` (+1) | `src/controllers/gui/chat_controller.py:17` |
| `GUI.CLEAR_USER_INPUT` | `clear_user_input` | `src/controllers/gui/chat_controller.py:30` | `src/controllers/gui/chat_controller.py:10` |
| `GUI.CLOSE_WINDOW` | `close_window` | `src/controllers/gui/voice_model_controller.py:334` (+1) | `src/controllers/gui/window_manager_controller.py:9` |
| `GUI.FINISH_STREAM_UI` | `finish_stream_ui` | `src/controllers/chat_controller.py:1060` (+1) | `src/controllers/gui/chat_controller.py:14` |
| `GUI.HIDE_MITA_VOICING` | `hide_mita_voicing` | `src/controllers/audio_controller.py:296` (+1) | `src/controllers/gui/status_controller.py:35` |
| `GUI.INSERT_TEXT_TO_INPUT` | `insert_text_to_input` | `src/controllers/chat_controller.py:1361` (+1) | `src/controllers/gui/chat_controller.py:23` |
| `GUI.PRELOAD_SETTINGS_SECTIONS` | `preload_settings_sections` | `src/controllers/gui/presentation_hub.py:152` | `src/controllers/gui/settings_sidebar_controller.py:12` |
| `GUI.PREPARE_STREAM_UI` | `prepare_stream_ui` | `src/controllers/chat_controller.py:599` (+1) | `src/controllers/gui/chat_controller.py:12` |
| `GUI.RELOAD_CHAT_HISTORY` | `reload_chat_history` | `src/controllers/chat_controller.py:1326` (+6) | `src/controllers/gui/settings_controller.py:17` |
| `GUI.REMOVE_LAST_CHAT_WIDGETS` | `remove_last_chat_widgets` | `src/controllers/chat_controller.py:1580` (+4) | `src/controllers/gui/settings_controller.py:20` |
| `GUI.SEND_TEXT_MESSAGE` | `send_text_message` | `src/controllers/speech_controller.py:1122` | `src/controllers/gui/chat_controller.py:24` |
| `GUI.SET_SETTINGS_ICON_INDICATOR` | `set_settings_icon_indicator` | `src/controllers/gui/asr_events_controller.py:385` | `src/controllers/gui/settings_sidebar_controller.py:11` |
| `GUI.SHOW_ERROR_MESSAGE` | `show_error_message` | `src/controllers/gui/beat_settings_controller.py:113` (+18) | `src/controllers/gui/dialog_controller.py:9` |
| `GUI.SHOW_INFO_MESSAGE` | `show_info_message` | `src/controllers/chat_controller.py:1841` (+10) | `src/controllers/gui/dialog_controller.py:8` |
| `GUI.SHOW_MITA_VOICING` | `show_mita_voicing` | `src/controllers/audio_controller.py:116` | `src/controllers/gui/status_controller.py:34` |
| `GUI.SHOW_WINDOW` | `show_window` | `src/controllers/gui/api_settings/controller.py:265` (+8) | `src/controllers/gui/window_manager_controller.py:8` |
| `GUI.UPDATE_CHAT_FONT_SIZE` | `update_chat_font_size` | `src/controllers/gui/settings_controller.py:116` | `src/controllers/gui/settings_controller.py:14` |
| `GUI.UPDATE_CHAT_UI` | `update_chat_ui` | `src/controllers/chat_controller.py:1005` (+6) | `src/controllers/gui/chat_controller.py:11` |
| `GUI.UPDATE_DEBUG_INFO` | `update_debug_info` | `src/controllers/chat_controller.py:1021` | `src/controllers/gui/system_controller.py:14` |
| `GUI.UPDATE_STATUS` | `update_status` | `src/controllers/chat_controller.py:1020` | `src/controllers/gui/status_controller.py:21` |
| `GUI.UPDATE_STATUS_COLORS` | `update_status_colors` | `src/controllers/capture_controller.py:232` (+24) | `src/controllers/gui/status_controller.py:20` |
| `GUI.UPDATE_TOKEN_COUNT` | `update_token_count` | `src/controllers/chat_controller.py:1022` (+2) | `src/controllers/gui/chat_controller.py:15` |
| `GUI.VOICEOVER_MODEL_SELECTED` | `voiceover_model_selected` | `src/controllers/gui/voiceover_settings_logic.py:118` | `src/controllers/gui/voiceover_controller.py:62` |
| `GUI.VOICEOVER_REFRESH` | `voiceover_refresh` | `src/controllers/audio_controller.py:404` (+8) | `src/controllers/gui/voiceover_controller.py:61` (+1) |
| `History.MESSAGES_COMMITTED` | `history_messages_committed` | `src/controllers/model_controller.py:788` | `src/controllers/gui/chat_controller.py:26` |
| `History.MESSAGE_COMPLETED` | `history_message_completed` | `src/controllers/model_controller.py:1964` (+1) | `src/controllers/graph_controller.py:72` (+1) |
| `Install.CATALOG_CHANGED` | `install_catalog_changed` | `src/services/ai_environment_maintenance_service.py:162` | `src/controllers/gui/microphone_settings_controller.py:65` (+1) |
| `Install.COMPONENT_STATUS` | `install_component_status` | `src/services/installable_catalog_service.py:812` | `src/controllers/gui/voiceover_controller.py:115` (+1) |
| `Install.TASK_FAILED` | `install_task_failed` | `src/controllers/gui/install_gui_controller.py:412` (+2) | `src/controllers/gui/asr_events_controller.py:54` (+6) |
| `Installable.INSTALL` | `installable_install` | `src/managers/rag/install_spec.py:840` | `src/controllers/installable_controller.py:38` |
| `Model.LOAD_HISTORY` | `load_history` | `src/controllers/gui/app_shell_controller.py:121` | `src/controllers/model_controller.py:261` |
| `Model.LOAD_MORE_HISTORY` | `load_more_history` | `src/controllers/gui/app_shell_controller.py:130` | `src/controllers/model_controller.py:262` |
| `Model.ON_COMPRESSION_FINISHED` | `on_compression_finished` | `src/controllers/model_controller.py:1313` | `src/controllers/gui/status_controller.py:24` |
| `Model.ON_COMPRESSION_STARTED` | `on_compression_started` | `src/controllers/model_controller.py:1253` | `src/controllers/gui/status_controller.py:23` |
| `Model.ON_FAILED_RESPONSE` | `on_failed_response` | `src/controllers/chat_controller.py:1049` (+13) | `src/controllers/gui/status_controller.py:27` |
| `Model.ON_FAILED_RESPONSE_ATTEMPT` | `on_failed_attempt_for_response` | `src/managers/llm_request_runner.py:230` (+1) | `src/controllers/gui/status_controller.py:26` |
| `Model.ON_STARTED_RESPONSE_GENERATION` | `on_started_response_generation` | `src/controllers/model_controller.py:1742` (+1) | `src/controllers/gui/status_controller.py:22` |
| `Model.ON_SUCCESSFUL_RESPONSE` | `on_successful_response` | `src/controllers/model_controller.py:1960` (+2) | `src/controllers/gui/status_controller.py:25` |
| `Model.ON_TOOL_EXECUTING` | `on_tool_executing` | `src/controllers/model_controller.py:2616` | `src/controllers/gui/status_controller.py:28` |
| `RAG.INDEX_CHANGED` | `rag_index_changed` | `src/controllers/gui/character_settings_logic.py:1269` (+1) | `src/controllers/gui/rag_install_view_model.py:74` |
| `RAG.MODEL_CHANGED` | `rag_model_changed` | `src/controllers/embedding_controller.py:294` | `src/controllers/embedding_controller.py:150` |
| `Server.ASR_TEXT_UNDELIVERED` | `asr_text_undelivered` | `src/controllers/server_controller.py:801` | `src/controllers/speech_controller.py:194` |
| `Server.CLIENT_DISCONNECTED` | `server_client_disconnected` | `src/controllers/server_controller.py:354` | `src/controllers/speech_controller.py:193` (+1) |
| `Server.ECHO_CHAT_MESSAGE_REQUESTED` | `echo_chat_message_requested` | `src/game_connections/handlers/actions/create_task.py:448` | `src/controllers/server_controller.py:185` |
| `Server.SEND_ASR_CAPTURE_STATE` | `send_asr_capture_state` | `src/controllers/speech_controller.py:683` (+4) | `src/controllers/server_controller.py:191` |
| `Server.SEND_ASR_TEXT` | `send_asr_text` | `src/controllers/speech_controller.py:1022` (+1) | `src/controllers/server_controller.py:190` |
| `Server.SEND_TASK_UPDATE` | `send_task_update` | `src/controllers/chat_controller.py:1467` (+1) | `src/controllers/server_controller.py:188` |
| `Server.SET_GAME_DATA` | `set_game_data` | `src/game_connections/handlers/actions/create_task.py:393` | `src/controllers/model_controller.py:257` |
| `Server.STOP_SERVER` | `stop_server` | `src/controllers/gui/app_shell_controller.py:115` | `src/controllers/gui_fallback_controller.py:28` (+1) |
| `Speech.ASR_CAPTURE_CHANGED` | `asr_capture_changed` | `src/controllers/speech_controller.py:669` (+1) | `src/controllers/gui/chat_panel_view_model.py:53` (+1) |
| `Speech.ASR_CAPTURE_PROGRESS` | `asr_capture_progress` | `src/handlers/asr_handler.py:476` (+1) | `src/controllers/speech_controller.py:192` |
| `Speech.ASR_FAILED` | `asr_failed` | `src/handlers/asr_handler.py:136` (+1) | `src/controllers/gui/asr_events_controller.py:48` (+1) |
| `Speech.ASR_MODEL_INITIALIZED` | `asr_model_initialized` | `src/handlers/asr_handler.py:112` (+2) | `src/controllers/gui/asr_events_controller.py:47` (+1) |
| `Speech.ASR_MODEL_INIT_STARTED` | `asr_model_init_started` | `src/handlers/asr_handler.py:415` (+1) | `src/controllers/gui/asr_events_controller.py:46` (+1) |
| `Speech.ASR_PTT_STATE` | `asr_ptt_state` | `src/game_connections/handlers/actions/asr_ptt_state.py:23` | `src/controllers/speech_controller.py:186` |
| `Speech.MICROPHONE_TEST_CHANGED` | `microphone_test_changed` | `src/services/microphone_monitor.py:114` (+1) | `src/controllers/speech_controller.py:187` |
| `Speech.REFRESH_ASR_STATUS` | `refresh_asr_status` | `src/controllers/gui/microphone_settings_logic.py:89` | `src/controllers/gui/asr_events_controller.py:49` |
| `Speech.RESTART_SPEECH_RECOGNITION` | `restart_speech_recognition` | `src/controllers/gui/microphone_settings_controller.py:853` (+3) | `src/controllers/speech_controller.py:199` |
| `Speech.SET_MICROPHONE` | `set_microphone` | `src/controllers/gui/microphone_settings_controller.py:851` (+2) | `src/controllers/speech_controller.py:196` |
| `Speech.SET_RECOGNIZER_OPTION` | `set_recognizer_option` | `src/controllers/gui/microphone_settings_controller.py:961` | `src/controllers/speech_controller.py:203` |
| `Speech.SPEECH_TEXT_RECOGNIZED` | `speech_text_recognized` | `src/handlers/asr_handler.py:516` (+1) | `src/controllers/speech_controller.py:184` |
| `Speech.STOP_SPEECH_RECOGNITION` | `stop_speech_recognition` | `src/controllers/main_controller.py:604` (+1) | `src/controllers/speech_controller.py:198` |
| `Task.TASK_STATUS_CHANGED` | `task_status_changed` | `src/controllers/task_controller.py:36` | `src/controllers/server_controller.py:187` |
| `Task.UPDATE_TASK_STATUS` | `update_task_status` | `src/controllers/audio_controller.py:270` (+12) | `src/controllers/task_controller.py:16` |
| `Telegram.SET_SILERO_CONNECTED` | `set_silero_connected` | `src/controllers/telegram_controller.py:254` (+8) | `src/controllers/gui/voiceover_controller.py:119` (+1) |
| `Telegram.START_SILERO` | `telegram_start_silero` | `src/controllers/gui/voiceover_controller.py:476` | `src/controllers/gui/voiceover_controller.py:124` (+1) |
| `VoiceModel.MODEL_COMPILE_FINISHED` | `voice_model_compile_finished` | `src/controllers/voice_model_controller.py:974` | `src/controllers/gui/ai_hub_settings_view_model.py:46` |
| `VoiceModel.MODEL_COMPILE_STARTED` | `voice_model_compile_started` | `src/controllers/voice_model_controller.py:915` | `src/controllers/gui/ai_hub_settings_view_model.py:43` |
| `VoiceModel.MODEL_INSTALL_FINISHED` | `voice_model_install_finished` | `src/controllers/voice_model_controller.py:979` | `src/controllers/gui/voice_model_controller.py:92` (+1) |
| `VoiceModel.MODEL_INSTALL_STARTED` | `voice_model_install_started` | `src/controllers/voice_model_controller.py:824` | `src/controllers/gui/voice_model_controller.py:91` |
| `VoiceModel.MODEL_UNINSTALL_FINISHED` | `voice_model_uninstall_finished` | `src/controllers/voice_model_controller.py:969` | `src/controllers/gui/voice_model_controller.py:94` (+1) |
| `VoiceModel.MODEL_UNINSTALL_STARTED` | `voice_model_uninstall_started` | `src/controllers/voice_model_controller.py:853` | `src/controllers/gui/voice_model_controller.py:93` |
| `VoiceModel.OPEN_DOC` | `open_voice_model_doc` | `src/controllers/gui/voice_model_controller.py:72` | `src/controllers/voice_model_controller.py:76` |
| `VoiceModel.REFRESH_MODEL_PANELS` | `refresh_voice_model_panels` | `src/controllers/gui/sandbox_page_controller.py:154` (+4) | `src/controllers/gui/voice_model_controller.py:95` (+1) |
| `VoiceModel.REFRESH_SETTINGS_DISPLAY` | `refresh_voice_settings_display` | `src/controllers/voice_model_controller.py:984` | `src/controllers/gui/voice_model_controller.py:96` |

## One-sided or dynamically routed candidates

| Event | Wire value | Syntactic status | Evidence |
|---|---|---|---|
| `AI.RESTART_SERVICE` | `ai_restart_service` | subscriber only | `src/controllers/ai_engine_controller.py:912` |
| `ApiPresets.EXPORT_PRESET` | `export_preset` | subscriber only | `src/controllers/api_presets_controller.py:437` |
| `ApiPresets.IMPORT_PRESET` | `import_preset` | subscriber only | `src/controllers/api_presets_controller.py:438` |
| `ApiPresets.LOAD_PRESET_STATE` | `load_preset_state` | subscriber only | `src/controllers/api_presets_controller.py:441` |
| `ApiPresets.PRESET_IMPORTED` | `preset_imported` | producer only | `src/controllers/api_presets_controller.py:1218` |
| `ApiPresets.SAVE_CUSTOM_PRESET` | `save_custom_preset` | subscriber only | `src/controllers/api_presets_controller.py:435` |
| `ApiPresets.UPDATE_PRESET_MODELS` | `update_preset_models` | subscriber only | `src/controllers/api_presets_controller.py:443` |
| `Audio.CHECK_MODEL_INITIALIZED` | `check_model_initialized` | subscriber only | `src/controllers/gui_fallback_controller.py:37` (+1) |
| `Audio.CHECK_MODEL_INSTALLED` | `check_model_installed` | subscriber only | `src/controllers/local_voice_controller.py:71` |
| `Audio.INIT_VOICE_MODEL` | `init_voice_model` | subscriber only | `src/controllers/gui_fallback_controller.py:39` |
| `Audio.OPEN_VOICE_MODEL_SETTINGS` | `open_voice_model_settings` | subscriber only | `src/controllers/local_voice_controller.py:68` |
| `Audio.OPEN_VOICE_MODEL_SETTINGS_DIALOG` | `open_voice_model_settings_dialog` | subscriber only | `src/controllers/gui/audio_model_controller.py:16` (+1) |
| `Audio.REFRESH_TRITON_STATUS` | `refresh_triton_status` | subscriber only | `src/controllers/local_voice_controller.py:69` |
| `Audio.REFRESH_VOICE_MODULES` | `refresh_voice_modules` | producer only | `src/controllers/gui/voice_model_controller.py:344` |
| `Audio.SELECT_VOICE_MODEL` | `select_voice_model` | subscriber only | `src/controllers/gui_fallback_controller.py:38` (+1) |
| `Audio.SET_WAITING_ANSWER` | `set_waiting_answer` | subscriber only | `src/controllers/audio_controller.py:62` |
| `Audio.SHOW_TRITON_DIALOG` | `show_triton_dialog` | subscriber only | `src/controllers/gui/voice_model_controller.py:102` |
| `Audio.SHOW_VC_REDIST_DIALOG` | `show_vc_redist_dialog` | subscriber only | `src/controllers/gui/voice_model_controller.py:101` |
| `Capture.CAPTURE_SCREEN` | `capture_screen` | subscriber only | `src/controllers/capture_controller.py:71` (+1) |
| `Character.DATA_RELOADED` | `character_data_reloaded` | producer only | `src/controllers/character_controller.py:86` (+1) |
| `Character.RELOAD_PROMPTS` | `character_reload_prompts` | subscriber only | `src/controllers/character_controller.py:39` |
| `Chat.DELETE_MESSAGE` | `chat_delete_message` | subscriber only | `src/controllers/chat_controller.py:416` |
| `Chat.DELETE_MESSAGES_FROM` | `chat_delete_messages_from` | subscriber only | `src/controllers/chat_controller.py:417` |
| `Chat.REGENERATE` | `chat_regenerate` | subscriber only | `src/controllers/chat_controller.py:418` |
| `Chat.REGENERATE_FROM` | `chat_regenerate_from` | subscriber only | `src/controllers/chat_controller.py:419` |
| `Chat.RETRY_LAST` | `chat_retry_last` | subscriber only | `src/controllers/chat_controller.py:420` |
| `EmbeddingPresets.TEST_RESULT` | `embed_test_result` | producer only | `src/controllers/embedding_presets_controller.py:491` (+2) |
| `GUI.CHECK_AND_INSTALL_FFMPEG` | `check_and_install_ffmpeg` | subscriber only | `src/controllers/gui/system_controller.py:15` |
| `GUI.CHECK_TRITON_DEPENDENCIES` | `check_triton_dependencies` | subscriber only | `src/controllers/gui/audio_model_controller.py:11` |
| `GUI.CHECK_USER_ENTRY_EXISTS` | `check_user_entry_exists` | subscriber only | `src/controllers/gui/chat_controller.py:25` |
| `GUI.CLEAR_USER_INPUT_UI` | `clear_user_input_ui` | subscriber only | `src/controllers/gui/chat_controller.py:9` |
| `GUI.CLOSE_ALL_WINDOWS` | `close_all_windows` | subscriber only | `src/controllers/gui/window_manager_controller.py:10` |
| `GUI.CLOSE_LOADING_POPUP` | `close_loading_popup` | subscriber only | `src/controllers/main_controller.py:659` |
| `GUI.SHOW_EULA_DIALOG` | `show_eula_dialog` | subscriber only | `src/controllers/gui/dialog_controller.py:12` |
| `GUI.SHOW_GUIDE` | `show_guide` | subscriber only | `src/controllers/gui/dialog_controller.py:13` |
| `GUI.SHOW_LOADING_POPUP` | `show_loading_popup` | subscriber only | `src/controllers/main_controller.py:656` |
| `GUI.SWITCH_VOICEOVER_SETTINGS` | `switch_voiceover_settings` | subscriber only | `src/controllers/gui/settings_controller.py:9` |
| `GUI.UPDATE_TOKEN_COUNT_UI` | `update_token_count_ui` | subscriber only | `src/controllers/gui/chat_controller.py:16` |
| `GUI.VOICEOVER_MODEL_INITIALIZE` | `voiceover_model_initialize` | subscriber only | `src/controllers/gui/voiceover_controller.py:65` |
| `GUI.VOICEOVER_MODEL_REINITIALIZE` | `voiceover_model_reinitialize` | subscriber only | `src/controllers/gui/voiceover_controller.py:68` |
| `History.COMPRESSED` | `history_compressed` | producer only | `src/controllers/history_controller.py:767` |
| `History.SAVE_AFTER_RESPONSE` | `save_history_after_response` | subscriber only | `src/controllers/history_controller.py:84` |
| `Install.CANCEL_QUEUED` | `install_cancel_queued` | subscriber only | `src/controllers/gui/install_gui_controller.py:63` |
| `Install.CANCEL_RUNNING` | `install_cancel_running` | subscriber only | `src/controllers/gui/install_gui_controller.py:64` |
| `Install.QUEUE_CHANGED` | `install_queue_changed` | producer only | `src/controllers/gui/install_gui_controller.py:187` |
| `Install.RUN_BLOCKING` | `run_install_blocking` | subscriber only | `src/controllers/install_controller.py:214` |
| `Install.RUN_HEADLESS` | `run_install_headless` | subscriber only | `src/controllers/gui/install_gui_controller.py:61` |
| `Install.RUN_WITH_UI` | `run_install_with_ui` | subscriber only | `src/controllers/gui/install_gui_controller.py:60` |
| `Install.TASK_FINISHED` | `install_task_finished` | subscriber only | `src/controllers/embedding_controller.py:151` (+8) |
| `Install.TASK_LOG` | `install_task_log` | subscriber only | `src/controllers/gui/install_gui_controller.py:62` |
| `Install.TASK_PROGRESS` | `install_task_progress` | subscriber only | `src/controllers/gui/asr_events_controller.py:52` (+2) |
| `Install.TASK_STARTED` | `install_task_started` | subscriber only | `src/controllers/gui/asr_events_controller.py:51` (+2) |
| `Installable.INITIALIZE` | `installable_initialize` | subscriber only | `src/controllers/installable_controller.py:40` |
| `Installable.UNINSTALL` | `installable_uninstall` | subscriber only | `src/controllers/installable_controller.py:39` |
| `Model.ADD_TEMPORARY_SYSTEM_INFO` | `add_temporary_system_info` | subscriber only | `src/controllers/model_controller.py:258` |
| `Model.CALCULATE_COST` | `calculate_cost` | subscriber only | `src/controllers/gui_fallback_controller.py:26` (+1) |
| `Model.ON_TOOL_DONE` | `on_tool_done` | producer only | `src/controllers/model_controller.py:2637` |
| `Model.PEEK_TEMPORARY_SYSTEM_INFOS` | `peek_temporary_system_infos` | subscriber only | `src/controllers/model_controller.py:259` |
| `Model.RELOAD_PROMPTS_ASYNC` | `reload_prompts_async` | subscriber only | `src/controllers/model_controller.py:266` |
| `Protocols.BUILD_HTTP_REQUEST` | `build_protocol_http_request` | subscriber only | `src/controllers/protocols_controller.py:63` |
| `Reminder.CHANGED` | `reminder_changed` | producer only | `src/managers/reminder_manager.py:157` |
| `Server.GAME_DIALOGUE_TARGET_CHANGED` | `game_dialogue_target_changed` | producer only | `src/game_connections/handlers/actions/create_task.py:389` |
| `Server.LOAD_SERVER_SETTINGS` | `load_server_settings` | subscriber only | `src/controllers/server_controller.py:183` |
| `Server.SET_DIALOG_ACTIVE` | `set_dialog_active` | subscriber only | `src/controllers/main_controller.py:663` |
| `Server.SET_ID_SOUND` | `set_id_sound` | producer only | `src/handlers/telegram_handler.py:293` |
| `Server.SET_PATCH_TO_SOUND_FILE` | `set_patch_to_sound_file` | producer only | `src/handlers/telegram_handler.py:289` |
| `Settings.SAVE_SETTING` | `save_setting` | subscriber only | `src/controllers/settings_controller.py:31` |
| `Speech.APPLY_RECOGNIZER_SETTINGS` | `apply_recognizer_settings` | subscriber only | `src/controllers/speech_controller.py:204` |
| `Speech.ASR_MODEL_INSTALL_PROGRESS` | `asr_model_install_progress` | producer only | `src/handlers/asr_models/gigaam_onnx_recognizer.py:319` |
| `Speech.INSTALL_ASR_MODEL` | `install_asr_model` | subscriber only | `src/handlers/asr_handler.py:189` |
| `Speech.REFRESH_MICROPHONE_LIST` | `refresh_microphone_list` | subscriber only | `src/controllers/speech_controller.py:201` |
| `Speech.SET_INSTANT_SEND_STATUS` | `set_instant_send_status` | subscriber only | `src/controllers/speech_controller.py:183` |
| `Speech.START_SPEECH_RECOGNITION` | `start_speech_recognition` | subscriber only | `src/controllers/speech_controller.py:197` |
| `Task.CREATE_TASK` | `create_task` | subscriber only | `src/controllers/task_controller.py:15` |
| `Task.NOTIFY_TASK_UPDATE` | `notify_task_update` | subscriber only | `src/controllers/task_controller.py:17` |
| `Task.TASK_CREATED` | `task_created` | producer only | `src/controllers/task_controller.py:23` |
| `Telegram.PROMPT_FOR_TG_CODE` | `prompt_for_tg_code` | subscriber only | `src/controllers/gui/dialog_controller.py:10` |
| `Telegram.PROMPT_FOR_TG_PASSWORD` | `prompt_for_tg_password` | subscriber only | `src/controllers/gui/dialog_controller.py:11` |
| `Telegram.STOP_SILERO` | `telegram_stop_silero` | subscriber only | `src/controllers/gui/voiceover_controller.py:127` (+1) |
| `VoiceModel.CLEAR_DESCRIPTION` | `clear_voice_model_description` | subscriber only | `src/controllers/gui/voice_model_controller.py:99` |
| `VoiceModel.CLOSE_DIALOG` | `close_voice_model_dialog` | subscriber only | `src/controllers/gui/voice_model_controller.py:89` |
| `VoiceModel.INSTALL_MODEL` | `install_voice_model` | subscriber only | `src/controllers/gui/voice_model_controller.py:86` |
| `VoiceModel.SAVE_SETTINGS` | `save_voice_model_settings` | subscriber only | `src/controllers/gui/voice_model_controller.py:88` |
| `VoiceModel.UNINSTALL_MODEL` | `uninstall_voice_model` | subscriber only | `src/controllers/gui/voice_model_controller.py:87` |
| `VoiceModel.UPDATE_DESCRIPTION` | `update_voice_model_description` | subscriber only | `src/controllers/gui/voice_model_controller.py:98` |

## Using this index for functional parity

1. A candidate route reaches `ACTIVE` only if its producer, consumer and activation path are confirmed (feature flag/GUI setup/composition). The extensive contracts documented in `../03-runtime/event-facts-command-routes-and-subscriber-lifetimes.md` provide examples.
2. For single-sided rows, search direct string literals, aliases, Qt signals, helper methods and delegated services; do not automatically label any route broken or obsolete.
3. Record whether the action changes durable state, ephemeral UI state, task queue or an external subsystem. Use a separately named requirement and a behavior-oriented validation fixture.
4. Distinguish the 12 conditional `RuntimeFeatureManager` registrations (`../03-runtime/optional-features.md`) from always-created controllers; raw syntax does not establish startup availability.

**Open:** full dynamic route inventory; callback reachability across GUI-only/headless/full runtime; payload schemas for every event; integration proof that all retained capabilities are observable. This document is not sufficient by itself to promote workstream 20 to PRIMARY.
