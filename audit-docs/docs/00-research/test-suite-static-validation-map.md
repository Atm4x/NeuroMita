# Карта имеющихся тестовых свидетельств для functional parity (Pass 12)

**Метод:** статический AST-index реального тестового каталога `src/utils/Testing/test_*.py` из `CodeNow.zip`. Группы назначены **по имени файла эвристически**, а не по runtime call graph; `test_` функций посчитано рекурсивно, в том числе вложенных. Этот документ **не** означает, что тесты запускались или прошли, и не подтверждает реальный Unity/Windows/Qt/CUDA E2E.

- Рассмотрено файлов из `src/utils/Testing`: **250**; отдельно `src/controllers/gui/api_settings/test_mixin.py` имеет префикс `test_`, но находится вне каталога Testing и не приравнивается к отдельному test suite.
- AST: **2177** function definitions `test_*` (включая методы unittest и вложенные функции), из них **13** `async def`; всего **3857** function definitions и **626** classes. Динамическая parametrization, subtests и discovery tooling могут изменить фактическое число runtime cases.
- Файлов с нулём объявлений `test_*`: 3 (`test_multimita_live_socket.py`, `test_sandbox_status_row.py`, `test_tr_combobox.py`).
- Не удалось распарсить AST: 0 (нет).

## Группы по теме имени файла — ориентир для проверки паритета

| Группа | Файлов | `test_*` объявлений | Степень доказательности |
|---|---:|---:|---|
| AI Engine / worker / IPC | 33 | 247 | Индекс исходников, не evidence of pass |
| Configuration / localization / prompts | 15 | 153 | Индекс исходников, не evidence of pass |
| GUI / windows / chat surfaces | 33 | 226 | Индекс исходников, не evidence of pass |
| History / memory / persistence | 15 | 119 | Индекс исходников, не evidence of pass |
| Installers / AI Hub | 11 | 108 | Индекс исходников, не evidence of pass |
| Misc runtime / reliability | 11 | 76 | Индекс исходников, не evidence of pass |
| Providers / LLM protocol | 27 | 281 | Индекс исходников, не evidence of pass |
| RAG / graph / embeddings | 14 | 82 | Индекс исходников, не evidence of pass |
| Unclassified — needs manual reachability | 18 | 88 | Индекс исходников, не evidence of pass |
| Unity / game / tools | 23 | 198 | Индекс исходников, не evidence of pass |
| Update / release / packaging | 14 | 163 | Индекс исходников, не evidence of pass |
| Voice / ASR / audio | 36 | 436 | Индекс исходников, не evidence of pass |

## Подробный static inventory

Указано `filename (test functions)`; ссылка на относительный путь источника теста задаётся префиксом `src/utils/Testing/`. Это позволяет следующему агенту выбирать корректные адресные тесты для конкретной функциональной ветви вместо случайного запуска всех 250 модулей.

### AI Engine / worker / IPC

`test_ai_contour_boundaries.py` (4); `test_ai_engine_administration.py` (8); `test_ai_engine_runtime_switch.py` (12); `test_ai_engine_scheduling.py` (8); `test_ai_environment_switching.py` (20); `test_ai_hub_device_display_labels.py` (1); `test_ai_hub_dialog_unsaved_close.py` (2); `test_ai_hub_install_queue_ui.py` (5); `test_ai_hub_localization.py` (2); `test_ai_hub_multibackend_ui.py` (9); `test_ai_hub_progress_rendering.py` (5); `test_ai_hub_queue_admission.py` (3); `test_ai_hub_refresh_timeout.py` (3); `test_ai_hub_settings_states.py` (13); `test_ai_hub_status_refresh.py` (5); `test_ai_hub_unsaved_settings.py` (3); `test_ai_removal_regressions.py` (12); `test_ai_surface_locale_coverage.py` (1); `test_ai_worker_admission.py` (7); `test_ai_worker_logging.py` (2); `test_backend_service.py` (12); `test_gpu_utils.py` (5); `test_headless_runtime.py` (6); `test_runtime_capabilities.py` (2); `test_runtime_environments.py` (45); `test_runtime_failure_policy.py` (4); `test_runtime_features.py` (8); `test_runtime_ipc.py` (4); `test_runtime_safety_fixes.py` (8); `test_service_state_isolation.py` (6); `test_task_worker_lifecycle.py` (4); `test_torch_compile_runtime.py` (11); `test_worker_environment_paths.py` (7)

### Configuration / localization / prompts

`test_app_paths_prompts.py` (10); `test_architecture_contracts.py` (19); `test_dsl_random.py` (5); `test_localization.py` (4); `test_preset_model_settings.py` (22); `test_project_prompts.py` (16); `test_prompt_linter.py` (7); `test_prompt_system_state.py` (38); `test_release_preset_names.py` (2); `test_release_prompt_contracts.py` (2); `test_safe_eval.py` (12); `test_settings_dependencies.py` (5); `test_settings_loading_ui.py` (2); `test_settings_registry.py` (8); `test_settings_section_headers.py` (1)

### GUI / windows / chat surfaces

`test_base_styles.py` (3); `test_chat_api.py` (6); `test_chat_presentation_coordinator.py` (31); `test_chat_request_pipeline.py` (18); `test_chat_retry.py` (4); `test_context_viewer_actor_labels.py` (4); `test_dialogue_presentation.py` (6); `test_dialogue_runtime_inspector_settings.py` (3); `test_dialogue_runtime_state.py` (2); `test_dialogue_sender_identity.py` (6); `test_dialogue_target_resolution.py` (2); `test_gui_standard_contour_smoke.py` (1); `test_gui_startup_order.py` (3); `test_gui_task_supervisor.py` (20); `test_gui_thread_affinity.py` (14); `test_guide_window_manager.py` (4); `test_home_action_plan.py` (14); `test_intent_mvvm_contract.py` (6); `test_intent_view_model_runtime.py` (7); `test_message_processing_dialog.py` (7); `test_model_controller_settings_lifecycle.py` (2); `test_news_release_loading.py` (5); `test_passive_ui_boundary.py` (18); `test_persistent_error_banner.py` (2); `test_photo_gallery.py` (11); `test_player_message_source.py` (4); `test_sandbox_page_controller.py` (6); `test_sandbox_status_row.py` (0); `test_send_message_capture.py` (6); `test_status_controller.py` (7); `test_tr_combobox.py` (0); `test_window_action_adapters.py` (2); `test_window_manager_hide_on_close_guard.py` (2)

### History / memory / persistence

`test_character_history_clear.py` (8); `test_conversation_event_writer.py` (6); `test_data_collection_settings_section.py` (3); `test_finetune_sample_usage.py` (3); `test_history_controller_compression.py` (24); `test_history_epoch_guard.py` (11); `test_history_manager_atomicity.py` (12); `test_history_ui_projector_multi_mita.py` (5); `test_last_interaction_gap.py` (21); `test_legacy_memory_recovery.py` (6); `test_memory_dedup.py` (4); `test_memory_forget.py` (2); `test_memory_manager_shutdown.py` (2); `test_release_history_loading.py` (4); `test_working_state_and_action_memory.py` (8)

### Installers / AI Hub

`test_ffmpeg_installer_log.py` (1); `test_install_on_demand_contract.py` (3); `test_install_ui_and_pip_fallback.py` (13); `test_installable_catalog_loaders.py` (4); `test_installable_catalog_service.py` (24); `test_installable_controller.py` (6); `test_installer_architecture.py` (27); `test_installer_windows_resilience.py` (6); `test_opencv_installables.py` (13); `test_pip_installer_raw_stream.py` (2); `test_pip_uninstall_targets.py` (9)

### Misc runtime / reliability

`test_async_runner_lifecycle.py` (3); `test_console_logging.py` (6); `test_daemon_executor.py` (2); `test_error_utils.py` (4); `test_event_bus.py` (24); `test_performance_trace.py` (6); `test_performance_trace_integration.py` (8); `test_shutdown_paths.py` (5); `test_task_supervisor.py` (4); `test_timer_scheduler.py` (7); `test_trace_context.py` (7)

### Providers / LLM protocol

`test_api_configuration_startup.py` (2); `test_api_endpoint_policy.py` (13); `test_api_model_completion_theme.py` (1); `test_api_preset_default_selection.py` (2); `test_api_settings_check_button.py` (2); `test_context_counter.py` (17); `test_declarative_model_profiles.py` (14); `test_endpoint_settings_ui.py` (11); `test_gemini_message_order.py` (8); `test_gemini_usage.py` (4); `test_http_client_registry.py` (5); `test_lazy_chat_token_count.py` (8); `test_llm_failure_context.py` (1); `test_llm_http_transport.py` (37); `test_message_content_codec.py` (8); `test_openai_schema_compat.py` (7); `test_param_mapper.py` (24); `test_provider_display_metadata.py` (2); `test_provider_errors.py` (10); `test_reasoning_channel.py` (6); `test_sparse_structured_response.py` (26); `test_stream_message_binding.py` (10); `test_structured_response_capabilities.py` (13); `test_structured_response_intents.py` (18); `test_structured_response_parser.py` (20); `test_structured_response_sandbox.py` (5); `test_structured_stream_filter.py` (7)

### RAG / graph / embeddings

`test_embedding_index_actions.py` (1); `test_entity_typing.py` (9); `test_gemini_embedding_provider.py` (5); `test_memory_islands.py` (12); `test_rag_model_catalog.py` (5); `test_rag_preset_model_downloads.py` (3); `test_rag_preset_view_model.py` (4); `test_rag_readiness.py` (9); `test_rag_reindex_batch_size.py` (1); `test_rag_restart_state.py` (11); `test_rag_runtime_context.py` (2); `test_rag_search_golden.py` (4); `test_rag_units_golden.py` (14); `test_seed_islands.py` (2)

### Unclassified — needs manual reachability

`test_character_environment_context.py` (10); `test_character_serialization.py` (4); `test_character_services.py` (6); `test_character_settings_view_model.py` (5); `test_character_settings_workspace.py` (3); `test_character_stats.py` (5); `test_db_viewer_character_filter.py` (3); `test_debug_dump_tokens.py` (4); `test_live_dialogue_echo_identity.py` (4); `test_local_message_pipeline.py` (10); `test_local_voice_controller_lifecycle.py` (12); `test_local_voice_runtime_context.py` (4); `test_multimita_live_socket.py` (0); `test_reaction_batch_prompt.py` (5); `test_reminder_controller_lifecycle.py` (4); `test_shared_image_transfer.py` (3); `test_telegram_credentials_gate.py` (2); `test_windows_endpoint_identity_status.py` (4)

### Unity / game / tools

`test_beat_service.py` (6); `test_character_command_routing.py` (25); `test_character_game_state_isolation.py` (5); `test_chess_move_reactions.py` (13); `test_core_memory_triggers.py` (9); `test_game_link_target.py` (7); `test_game_master_control_plane.py` (15); `test_game_master_target_resolution.py` (3); `test_game_settings_loading.py` (1); `test_get_music_beats_action.py` (2); `test_manual_game_launch.py` (7); `test_mini_game_public_context.py` (5); `test_seabattle_lifecycle_reactions.py` (8); `test_seabattle_window_reactions.py` (6); `test_tool_manager_lazy.py` (1); `test_tv_observation.py` (13); `test_unity_dialogue_routing_boundary.py` (18); `test_unity_dialogue_turn_simulator.py` (22); `test_unity_process_guard.py` (7); `test_unity_retry_store.py` (14); `test_unity_target_policy.py` (1); `test_warm_prompt_game_state.py` (1); `test_world_character_context.py` (9)

### Update / release / packaging

`test_app_icon_path.py` (1); `test_distribution_metadata_stamp.py` (5); `test_launcher_bootstrap.py` (22); `test_native_launcher_contract.py` (4); `test_network_errors.py` (8); `test_release_assets.py` (23); `test_release_catalog.py` (5); `test_release_changelog.py` (3); `test_release_contract.py` (11); `test_release_deletion.py` (8); `test_release_google_asr.py` (3); `test_release_revisions.py` (26); `test_update_contour.py` (13); `test_update_transaction.py` (31)

### Voice / ASR / audio

`test_asr_audio_devices.py` (23); `test_asr_device_routing.py` (3); `test_asr_environment_context.py` (2); `test_asr_game_capture.py` (15); `test_asr_handler.py` (21); `test_asr_language_capabilities.py` (14); `test_asr_ptt.py` (28); `test_asr_radio.py` (14); `test_asr_session_routing.py` (19); `test_asr_settings_service.py` (2); `test_asr_status_sync.py` (4); `test_edge_tts_rvc_installables.py` (31); `test_f5_tts_installables.py` (15); `test_fish_speech_installables.py` (16); `test_instant_voice_merge.py` (3); `test_microphone_identity_runtime.py` (4); `test_microphone_localization.py` (2); `test_microphone_monitor.py` (7); `test_microphone_selection_service.py` (15); `test_microphone_settings_ui.py` (27); `test_num2words2_integration.py` (4); `test_omnivoice_installables.py` (5); `test_remote_voice.py` (19); `test_remote_voice_delivery.py` (2); `test_remote_voice_ui.py` (11); `test_rvc_half_precision_policy.py` (7); `test_speaking_window.py` (12); `test_speech_reconciler.py` (13); `test_tts_service.py` (6); `test_voice_assets.py` (25); `test_voice_device_selection.py` (9); `test_voice_failure.py` (3); `test_voice_installation_status.py` (2); `test_voice_model_controller.py` (26); `test_voiceover_gui_controller.py` (20); `test_whisper_recognizer.py` (7)

## Критерии использования

1. При появлении новой `CAP-*` сначала искать подтверждённый **production runtime path**, затем тест, и не наоборот.
2. Тесты с fake workers, временной БД и mock Qt являются полезными контрактными фикстурами, но не подтверждают реальное устройство, credentials, сеть или загрузку весов.
3. Fail при устаревших fixture, missing dependencies или недоступном SDK фиксировать как границу верификации, не превращать этот функциональный проход в bugfix.
4. В финальном проекте проверять семантику, состояния и инварианты, а не копировать Python API/class structure; исходные тесты — исходные свидетельства, а не автоматическая целевая Rust test architecture.

**Далее:** связать test-файлы не только с эвристической группой, но с source-specific `CAP-*` / `REQ-*`, выявить отсутствие контрактных fixtures для внешних интеграций и всех действий GUI, отдельно провести Windows/device/network E2E.
