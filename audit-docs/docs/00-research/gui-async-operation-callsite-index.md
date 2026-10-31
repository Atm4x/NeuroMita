# Static GUI work-operation callsite index

**Scope:** all concrete calls to the `IntentViewModel` async work primitives within `src/controllers/gui/*_view_model.py` in the `CodeNow.zip` source snapshot. The 20 modules and 52 static callsites are **not** 52 proven user-facing actions: caller reachability and UI registration require independent evidence. No runtime GUI app launched.

**Totals:** 52 callsites / 20 files; `run_latest` 14, `run_exclusive` 20, `run_coalesced` 18.

| Source:line | Method | Operation | Name / scope |
|---|---|---|---|
| `src/controllers/gui/ai_engine_settings_view_model.py:91` | `refresh_hardware` | `run_latest` | `'ai-engine-hardware-refresh'` |
| `src/controllers/gui/ai_engine_settings_view_model.py:108` | `refresh_topology` | `run_latest` | `'ai-engine-topology-refresh'` |
| `src/controllers/gui/ai_engine_settings_view_model.py:125` | `refresh_maintenance` | `run_latest` | `'ai-engine-maintenance-refresh'` |
| `src/controllers/gui/ai_engine_settings_view_model.py:149` | `refresh_backends` | `run_latest` | `'ai-engine-backends-refresh'` |
| `src/controllers/gui/ai_engine_settings_view_model.py:180` | `switch_mode` | `run_latest` | `'ai-engine-topology-switch'` |
| `src/controllers/gui/ai_engine_settings_view_model.py:233` | `reset_environments` | `run_latest` | `'ai-environment-reset'` |
| `src/controllers/gui/ai_hub_settings_view_model.py:224` | `select_component` | `run_latest` | `'ai-hub-settings-load'` |
| `src/controllers/gui/ai_hub_settings_view_model.py:309` | `_start_compile` | `run_exclusive` | `f'ai-hub-compile-prepare:{component_id}'` |
| `src/controllers/gui/ai_hub_settings_view_model.py:364` | `_refresh_compile_status` | `run_latest` | `'ai-hub-compile-status'` |
| `src/controllers/gui/ai_hub_settings_view_model.py:409` | `save` | `run_exclusive` | `'ai-hub-settings-save'` |
| `src/controllers/gui/ai_hub_view_model.py:140` | `refresh` | `run_coalesced` | `'ai-hub-refresh'` |
| `src/controllers/gui/ai_hub_view_model.py:162` | `clear_cache` | `run_exclusive` | `'ai-hub-cache-clear'` |
| `src/controllers/gui/ai_hub_view_model.py:242` | `request_component_action` | `run_exclusive` | `operation_name` |
| `src/controllers/gui/asr_glossary_view_model.py:69` | `refresh` | `run_coalesced` | `'asr-glossary-refresh'` |
| `src/controllers/gui/asr_glossary_view_model.py:85` | `load_settings` | `run_latest` | `'asr-glossary-settings'` |
| `src/controllers/gui/beat_settings_view_model.py:82` | `refresh` | `run_coalesced` | `'beat-settings-refresh'` |
| `src/controllers/gui/beat_settings_view_model.py:130` | `rebuild_cache` | `run_exclusive` | `'beat-settings-cache-build'` |
| `src/controllers/gui/character_state_view_model.py:40` | `refresh` | `run_coalesced` | `'character-state-refresh'` |
| `src/controllers/gui/chat_message_actions_view_model.py:95` | `dispatch` | `run_latest` | `'chat-sample-context'` |
| `src/controllers/gui/chat_panel_view_model.py:148` | `refresh` | `run_coalesced` | `'chat-composer-state'` |
| `src/controllers/gui/chat_panel_view_model.py:287` | `_stage_files` | `run_exclusive` | `'chat-stage-files'` |
| `src/controllers/gui/chat_panel_view_model.py:328` | `_capture_screen` | `run_exclusive` | `'chat-screen-capture'` |
| `src/controllers/gui/embed_provider_view_model.py:60` | `_refresh_index_status` | `run_latest` | `'embed-provider-index-status'` |
| `src/controllers/gui/embed_provider_view_model.py:152` | `refresh_presets` | `run_coalesced` | `'embed-provider-presets'` |
| `src/controllers/gui/embed_provider_view_model.py:208` | `select_preset` | `run_latest` | `'embed-provider-config'` |
| `src/controllers/gui/embed_provider_view_model.py:245` | `save_preset` | `run_exclusive` | `'embed-provider-save'` |
| `src/controllers/gui/embed_provider_view_model.py:269` | `add_preset` | `run_exclusive` | `'embed-provider-add'` |
| `src/controllers/gui/embed_provider_view_model.py:282` | `delete_preset` | `run_exclusive` | `'embed-provider-delete'` |
| `src/controllers/gui/embed_provider_view_model.py:294` | `reorder_presets` | `run_exclusive` | `'embed-provider-reorder'` |
| `src/controllers/gui/embed_provider_view_model.py:344` | `download_model` | `run_exclusive` | `'embed-provider-download'` |
| `src/controllers/gui/finetune_data_view_model.py:53` | `dispatch` | `run_exclusive` | `'finetune-enforce-limit'` |
| `src/controllers/gui/finetune_data_view_model.py:78` | `refresh` | `run_coalesced` | `'finetune-data-refresh'` |
| `src/controllers/gui/finetune_data_view_model.py:97` | `clear_all` | `run_exclusive` | `'finetune-data-clear'` |
| `src/controllers/gui/gallery_page_view_model.py:60` | `dispatch` | `run_coalesced` | `'gallery-scan'` |
| `src/controllers/gui/gallery_page_view_model.py:77` | `dispatch` | `run_exclusive` | `'gallery-folder'` |
| `src/controllers/gui/gallery_page_view_model.py:84` | `dispatch` | `run_latest` | `'gallery-photo'` |
| `src/controllers/gui/gallery_page_view_model.py:128` | `_load_thumbnails` | `run_exclusive` | `'gallery-thumbnails'` |
| `src/controllers/gui/home_page_view_model.py:252` | `refresh_updates` | `run_coalesced` | `'home-update-check'` |
| `src/controllers/gui/home_page_view_model.py:664` | `_start_selective_update` | `run_exclusive` | `'home-apply-updates'` |
| `src/controllers/gui/logs_page_view_model.py:36` | `_refresh` | `run_coalesced` | `'logs-tail'` |
| `src/controllers/gui/news_page_view_model.py:62` | `refresh` | `run_coalesced` | `'news-page-refresh'` |
| `src/controllers/gui/rag_preset_view_model.py:197` | `_apply` | `run_latest` | `'rag-preset-model-status'` |
| `src/controllers/gui/remote_voice_settings_view_model.py:136` | `dispatch` | `run_exclusive` | `'remote_voice_settings'` |
| `src/controllers/gui/sandbox_page_view_model.py:195` | `refresh_selectors` | `run_coalesced` | `'sandbox-selectors'` |
| `src/controllers/gui/sandbox_page_view_model.py:210` | `refresh_status` | `run_coalesced` | `'sandbox-status'` |
| `src/controllers/gui/sandbox_page_view_model.py:248` | `refresh_memory` | `run_coalesced` | `'sandbox-memory'` |
| `src/controllers/gui/sandbox_page_view_model.py:265` | `refresh_budget` | `run_coalesced` | `'sandbox-budget'` |
| `src/controllers/gui/settings_page_view_model.py:135` | `_prepare` | `run_exclusive` | `f'settings-section:{category}'` |
| `src/controllers/gui/settings_page_view_model.py:191` | `_prepare_features` | `run_exclusive` | `f'settings-features:{category}'` |
| `src/controllers/gui/settings_runtime_options_view_model.py:40` | `load_providers` | `run_coalesced` | `'settings-provider-options'` |
| `src/controllers/gui/settings_runtime_options_view_model.py:57` | `load_cameras` | `run_coalesced` | `'settings-camera-options'` |
| `src/controllers/gui/voice_models_view_model.py:107` | `refresh` | `run_coalesced` | `'voice-models-refresh'` |

## Interpretation and validation boundary

- `run_latest` increments a generation and discards older worker replies; it is not proof physical worker cancellation.
- `run_exclusive` rejects a second concurrent call **with the same operation name**. Different IDs/actions can overlap; actual business resource serialization requires separate verification.
- `run_coalesced` tracks one pending rerun for the same operation key, delivering the freshest result after rerun.
- App/window closing, event subscription disposal and presentation update only if still alive are studied in [functional semantics](../02-ui/intent-workloads-and-visible-state-consistency.md).
- These are only direct syntactic calls; dynamic wrappers and operations not inheriting `IntentViewModel` are not counted. To prove action reachability, follow the registered page/view/controller `dispatch()` for each row.

## Suggested continuation

For GUI gate 14 PARTIAL: trace registered UI action → intent → `dispatch` → operation/result → domain side effect; distinguish GUI action presence, action availability, and actual E2E behavior. Do not treat every AST callsite as a distinct function or increase overall completion percent on this count alone.
