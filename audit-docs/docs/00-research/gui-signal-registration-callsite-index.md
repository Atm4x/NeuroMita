# Индекс соединений GUI-сигналов с обработчиками (Pass 12)

**Метод:** AST-наблюдение `.connect(...)` для 16 UI-сигналов (`clicked`, `toggled`, `currentIndexChanged`, `textChanged`, `triggered`, `timeout` и др.) в `src/ui/{pages,settings,dialogs,windows,widgets}` и `src/controllers/gui`. Исключены `ui/not_used`, `utils/Testing`, `src/Lib`. Снимок `CodeNow.zip`; не выполнялся запуск Qt. Сканирование зафиксировало **517 синтаксических соединений в 75 файлах**. Число не равно количеству пользовательских действий: `timeout` — таймер, часть UI создаётся условно, часть обработчиков не связана напрямую с бизнес-операцией, а часть сигналов строится динамически.

## Метод интерпретации

Часть связей относится к visual state (`toggle/collapse/selection`), часть — к intent/command (установка, импорт, генерация, очистка). **Только после анализа downstream receiver** можно считать одно соединение отдельной capability. `QTimer.timeout` является фоновым UI refresh и не является событием пользователя. Не найденные AST `.connect` сигналы могут регистрироваться через `setOn...`, eventFilter, decorated Qt slots, контекстные меню, custom signals или runtime reflection.

## CAP-UI-SIGNAL-001 — срез по сигналам

| Сигнал | Число AST соединений | Интерпретация |
|---|---:|---|
| `clicked` | 273 | кнопки, не всегда Core intent |
| `toggled` | 53 | enabled/visible/preferences |
| `textChanged` | 40 | поиск, validation, live edit |
| `triggered` | 29 | menu/action, иногда clipboard/export |
| `currentIndexChanged` | 26 | выбор контекста/профиля |
| `timeout` | 24 | таймеры, не явное действие пользователя |
| `stateChanged` | 18 | checkbox/combo state |
| `currentTextChanged` | 13 | выбор строки/компонента |
| `valueChanged` | 10 | slider/number control |
| `activated` | 9 | keyboard/mouse activation |
| `rejected` | 8 | редкий UI переход |
| `accepted` | 5 | редкий UI переход |
| `editingFinished` | 4 | редкий UI переход |
| `returnPressed` | 4 | редкий UI переход |
| `itemDoubleClicked` | 1 | редкий UI переход |

## CAP-UI-SIGNAL-002 — source-callsite индекс по файлам

Каждая строка содержит синтаксический регистрируемый handler с точной **строкой исходника**, а не гарантию runtime-достижимости. Пример показывает первые три по порядку исходного файла; полный список доступен воспроизводимым AST-сканированием `src`. Счётчик всех 75 файлов суммируется в 517.

| Source file | Всего | Примеры `line:signal→receiver` |
|---|---:|---|
| `src/controllers/gui/api_settings/controller.py` | 24 | `55:timeout→self._emit_save_state`; `146:textChanged→self._safe(self._on_field_changed, 'preset_name_chan…`; `150:clicked→self._safe(self._add_custom_preset_async, 'add_preset')` |
| `src/controllers/gui/api_settings/test_mixin.py` | 1 | `55:triggered→lambda _checked=False, aid=account['id']: self._test…` |
| `src/controllers/gui/character_settings_logic.py` | 28 | `535:textChanged→lambda text: _filter_character_library(self, text)`; `543:currentTextChanged→lambda _text: on_prompt_set_changed(self)`; `570:currentIndexChanged→lambda _i: save_character_provider(self, self.char_p…` |
| `src/controllers/gui/chat_panel_view_model.py` | 1 | `51:timeout→self._refresh_capture` |
| `src/controllers/gui/embed_provider_view_model.py` | 1 | `34:timeout→self._test_timed_out` |
| `src/controllers/gui/gallery_page_view_model.py` | 1 | `41:timeout→self._load_thumbnails` |
| `src/controllers/gui/home_page_controller.py` | 1 | `41:timeout→self._poll_external_process` |
| `src/controllers/gui/microphone_monitor_controller.py` | 3 | `18:timeout→self._render`; `19:toggled→self._toggle`; `20:currentIndexChanged→lambda _index: self.stop()` |
| `src/controllers/gui/microphone_settings_controller.py` | 17 | `194:currentIndexChanged→self._on_input_mode_changed`; `199:clicked→self.refresh_microphones`; `202:clicked→self.refresh_engines` |
| `src/controllers/gui/protocol_pipeline_gui_controller.py` | 1 | `31:accepted→lambda: self._apply(dialog)` |
| `src/controllers/gui/updates_settings_controller.py` | 11 | `551:activated→lambda _index: QTimer.singleShot(0, _save_mode)`; `569:stateChanged→_save_keep_prompts`; `585:stateChanged→_save_check_startup` |
| `src/controllers/gui/voiceover_controller.py` | 1 | `1656:rejected→lambda: self._user_hide_loading()` |
| `src/controllers/gui/voiceover_settings_logic.py` | 4 | `121:activated→self._on_local_model_changed`; `161:clicked→self._on_local_model_action`; `178:currentTextChanged→self._on_voiceover_method_changed` |
| `src/ui/dialogs/background_task_dialog.py` | 2 | `200:clicked→self.hide`; `205:clicked→self._on_stop` |
| `src/ui/dialogs/context_viewer_dialog.py` | 17 | `263:activated→self._focus_search`; `292:clicked→self._toggle_maximized`; `300:clicked→self._copy_json` |
| `src/ui/dialogs/db_export_dialog.py` | 7 | `151:toggled→_update_dt_enabled`; `152:toggled→_update_dt_enabled`; `153:toggled→_update_dt_enabled` |
| `src/ui/dialogs/db_viewer.py` | 42 | `272:clicked→self._restore_scroll_pos_later`; `286:timeout→self._resize_rows_to_contents_if_needed`; `299:triggered→self._delete_selected_rows` |
| `src/ui/dialogs/export_dialog.py` | 3 | `99:currentIndexChanged→self._update_count`; `143:clicked→self.reject`; `149:clicked→self._do_export` |
| `src/ui/dialogs/ffmpeg_dialogs.py` | 1 | `150:clicked→error_dialog.accept` |
| `src/ui/dialogs/gallery_viewer.py` | 6 | `98:clicked→lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(…`; `125:clicked→lambda: self.navigate(-1)`; `126:clicked→lambda: self.navigate(1)` |
| `src/ui/dialogs/graph_view_widget.py` | 12 | `140:timeout→self._layout_step`; `647:currentIndexChanged→self._reload`; `657:clicked→self._show_all` |
| `src/ui/dialogs/message_processing_dialog.py` | 6 | `96:clicked→self._on_add`; `111:currentIndexChanged→self._show_candidate_help`; `156:clicked→self._on_reset` |
| `src/ui/dialogs/model_loading_dialog.py` | 2 | `141:clicked→hide_callback`; `146:clicked→cancel_callback` |
| `src/ui/dialogs/styled_message.py` | 1 | `83:clicked→self.accept` |
| `src/ui/dialogs/telegram_auth_dialogs.py` | 7 | `148:clicked→dialog.reject`; `191:clicked→submit_code`; `192:returnPressed→submit_code` |
| `src/ui/pages/gallery_page.py` | 6 | `47:timeout→self.refresh`; `78:clicked→self.refresh`; `81:clicked→lambda: self._view_model.dispatch(OpenGalleryFolder())` |
| `src/ui/pages/home_page.py` | 5 | `100:timeout→self._advance_pulse`; `219:clicked→lambda: self.dispatch_intent(HomePrimaryRequested())`; `232:clicked→self._on_menu_button_clicked` |
| `src/ui/pages/logs_page.py` | 1 | `77:timeout→self.refresh_logs` |
| `src/ui/pages/sandbox_page.py` | 34 | `263:toggled→on_toggle`; `272:clicked→on_settings`; `483:toggled→lambda checked: on_toggle_active(bool(checked))` |
| `src/ui/pages/settings/settings_page_widget.py` | 5 | `474:clicked→lambda checked=False, cat=spec.key: self.show_catego…`; `535:clicked→self._page_actions.show_guide`; `540:clicked→lambda: self._page_actions.switch_page('wiki')` |
| `src/ui/pages/wiki_page.py` | 2 | `350:clicked→lambda _checked=False, f=_file: self._on_sidebar_cli…`; `480:clicked→callback` |
| `src/ui/settings/ai_engine_settings.py` | 5 | `208:clicked→lambda: view_model.refresh_hardware(force=True)`; `260:clicked→view_model.open_ai_hub`; `444:currentIndexChanged→on_mode_selected` |
| `src/ui/settings/api_settings/dialogs/model_parameters_dialog.py` | 5 | `97:clicked→self._add`; `98:clicked→self._remove`; `99:accepted→self._save` |
| `src/ui/settings/api_settings/dialogs/models_loaded_dialog.py` | 6 | `106:textChanged→self._rebuild_table`; `107:toggled→self._rebuild_table`; `108:clicked→self._accept_selected` |
| `src/ui/settings/api_settings/dialogs/new_preset_dialog.py` | 3 | `48:accepted→self._accept`; `49:rejected→self.reject`; `52:currentIndexChanged→self._on_template_changed` |
| `src/ui/settings/api_settings/dialogs/protocol_pipeline_dialog.py` | 7 | `63:clicked→self._on_add`; `64:clicked→self._on_remove`; `65:clicked→lambda: self._move(-1)` |
| `src/ui/settings/api_settings/model_settings_form.py` | 9 | `99:clicked→signal.emit`; `136:toggled→self._field_changed`; `165:currentIndexChanged→self._field_changed` |
| `src/ui/settings/api_settings/ui.py` | 1 | `174:textChanged→lambda text: _filter_presets(self.custom_presets_lis…` |
| `src/ui/settings/api_settings/widgets.py` | 15 | `297:triggered→lambda checked=False, k=key, pid=item.preset_id: sel…`; `495:toggled→lambda on: self.eye_btn.setIcon(qta.icon('fa5s.eye-s…`; `499:toggled→lambda on: self.key_edit.setEchoMode(QLineEdit.EchoM…` |
| `src/ui/settings/data_settings.py` | 8 | `108:stateChanged→_on_toggle`; `127:stateChanged→_on_rating_toggle`; `187:valueChanged→_on_limit_changed` |
| `src/ui/settings/debug_settings.py` | 10 | `57:currentIndexChanged→lambda _i: _set('SHOW_STRUCTURED_IN_GUI', struct_com…`; `70:toggled→lambda checked: _set('STRUCTURED_EXPANDED_DEFAULT', …`; `92:toggled→lambda checked: _set('REMOTE_ONLY_STRUCTURED_FIELDS_…` |
| `src/ui/settings/embed_provider_settings.py` | 28 | `82:currentIndexChanged→self._on_preset_combo_changed`; `88:clicked→self._on_add`; `93:clicked→self._on_delete` |
| `src/ui/settings/embedding_index_actions.py` | 4 | `31:clicked→self._start_or_show`; `34:clicked→self._refresh_status_callback`; `47:clicked→self._show_progress` |
| `src/ui/settings/game_settings.py` | 2 | `244:stateChanged→_sync`; `383:currentIndexChanged→_save_backend` |
| `src/ui/settings/microphone_settings/ui.py` | 2 | `156:toggled→lambda _checked: refresh_active_hint()`; `324:toggled→self.mic_instant_delay_row.setVisible` |
| `src/ui/settings/microphone_settings/widgets.py` | 2 | `42:timeout→self._pulse`; `270:timeout→self._animate` |
| `src/ui/settings/rag_install_widget.py` | 1 | `24:clicked→lambda: self._view_model.dispatch(OpenRagAiHub(self.…` |
| `src/ui/settings/rag_preset_widget.py` | 4 | `55:currentTextChanged→lambda value: self._view_model.dispatch(SelectRagPre…`; `58:clicked→lambda: self._view_model.dispatch(RequestApplyRagPre…`; `61:clicked→lambda: self._view_model.dispatch(RequestSaveRagPres…` |
| `src/ui/settings/screen_analysis_settings.py` | 2 | `223:stateChanged→_sync`; `225:stateChanged→_sync` |
| `src/ui/settings/voiceover_settings/remote_api.py` | 12 | `94:triggered→self._toggle_key`; `123:currentTextChanged→self._refresh_model_hint`; `139:clicked→self.speed.stepDown` |
| `src/ui/settings/voiceover_settings/ui.py` | 14 | `125:toggled→lambda enabled: self._save_setting('USE_VOICEOVER', …`; `128:toggled→lambda _enabled: refresh_voice_hint()`; `139:currentTextChanged→lambda value: self._save_setting('VOICEOVER_METHOD',…` |
| `src/ui/settings/voiceover_settings/widgets.py` | 1 | `105:clicked→lambda _checked, v=value: self.setCurrentText(v)` |
| `src/ui/widgets/character_state_panel.py` | 1 | `237:toggled→self._on_toggle_all` |
| `src/ui/widgets/character_voice_tabs.py` | 2 | `50:timeout→self._advance_hover`; `91:clicked→lambda: self._scroll_to(self._scroll_offset + step *…` |
| `src/ui/widgets/chat_panel.py` | 10 | `387:clicked→self._open_character_history`; `395:clicked→self._actions.reload_history`; `403:clicked→self._actions.clear_chat` |
| `src/ui/widgets/eula_widget.py` | 2 | `194:clicked→self._on_reject`; `201:clicked→self._on_accept` |
| `src/ui/widgets/guide_widget.py` | 14 | `496:clicked→self._on_close`; `542:currentIndexChanged→self._on_language_changed`; `546:clicked→self._open_help` |
| `src/ui/widgets/image_preview_widget.py` | 2 | `55:clicked→lambda: self.remove_clicked.emit(self.index)`; `203:clicked→self.thumbnail_clicked.emit` |
| `src/ui/widgets/image_viewer_widget.py` | 1 | `52:clicked→self.close_requested.emit` |
| `src/ui/widgets/launcher_dashboard_helpers.py` | 2 | `210:clicked→lambda _checked=False, m=mode: _apply_filter(m)`; `524:clicked→action.callback` |
| `src/ui/widgets/launcher_shell_sidebar.py` | 5 | `187:clicked→self.install_logs_requested.emit`; `264:clicked→lambda checked=False, key=section.key: self.request_…`; `316:clicked→lambda checked=False, value=key: self.social_request…` |
| `src/ui/widgets/microphone_button.py` | 1 | `27:timeout→self.update` |
| `src/ui/widgets/mita_status_widget.py` | 2 | `190:timeout→self._on_watchdog`; `209:timeout→self._tick_dots` |
| `src/ui/widgets/number_stepper.py` | 3 | `42:clicked→self.spin_box.stepDown`; `43:clicked→self.spin_box.stepUp`; `44:valueChanged→self.valueChanged` |
| `src/ui/widgets/settings_icon_button.py` | 1 | `43:valueChanged→self._on_loading_value_changed` |
| `src/ui/widgets/template_url_edit.py` | 4 | `72:valueChanged→self._set_address_width`; `95:textChanged→self._changed`; `96:textChanged→self._changed` |
| `src/ui/widgets/toggle_switch.py` | 3 | `43:toggled→self._animate_to`; `135:valueChanged→self._animate`; `136:toggled→self._move` |
| `src/ui/windows/ai_hub/dialog.py` | 15 | `84:clicked→self.accept`; `88:clicked→self.reject`; `223:clicked→self._toggle_queue_popup` |
| `src/ui/windows/ai_hub/schema_renderer.py` | 5 | `307:toggled→self._fire_change`; `325:currentIndexChanged→self._fire_change`; `340:valueChanged→self._fire_change` |
| `src/ui/windows/ai_hub/settings_panel.py` | 6 | `149:clicked→self._on_state_action`; `201:clicked→lambda: self._view_model.dispatch(OpenAIHubCompilati…`; `209:clicked→self._on_delete_compilation` |
| `src/ui/windows/ai_hub/widgets.py` | 5 | `419:clicked→self._handle_reinstall_click`; `427:clicked→self._show_menu`; `440:clicked→self._handle_install_click` |
| `src/ui/windows/app_window_base.py` | 4 | `183:timeout→self._on_voice_autosend_timeout`; `475:textChanged→self._on_user_entry_edited`; `1668:accepted→lambda: self._on_eula_accepted(eula_widget)` |
| `src/ui/windows/asr_glossary_view.py` | 6 | `143:textChanged→self._apply_filter`; `155:clicked→self.refresh`; `227:clicked→self._on_install_clicked` |
| `src/ui/windows/voice_action_windows.py` | 20 | `150:timeout→self._update_elapsed`; `219:timeout→self._update_disk_free`; `254:timeout→self._flush_raw_log` |
| `src/ui/windows/voice_model_view.py` | 9 | `111:clicked→self._on_uninstall`; `114:clicked→self._on_install`; `284:textChanged→lambda *_: notify_changed()` |

## Важные выводы и неразрешённое

- Большие файлы с множеством `.connect` (`ui/dialogs/db_viewer.py`, `ui/pages/sandbox_page.py`, `controllers/gui/character_settings_logic.py`, `ui/settings/embed_provider_settings.py`) — **узлы UI-плотности**, а не автоматически плохая архитектура или одинаковые по сложности функции.
- Для функционального паритета важен **результат каждого intent**: read-only navigation/clipboard, settings persistence, submission of background job, operation result, destructive action; это разные классы действия.
- Подробно прослежены user-facing file selection и confirmation actions: [native dialogs](../02-ui/native-dialogs-and-file-input-output-workflows.md), [confirmations](../02-ui/confirmation-and-destructive-intent-semantic-matrix.md), [modal reachability](../02-ui/dialog-class-reachability-and-action-outcomes.md).
- **Остаток GUI-depth:** типизированный receiver/intent downstream для каждого регистрируемого handler, динамически сформированные меню/overlays, keyboard shortcut events, реальные окна Qt, платформенные file-permissions, их async/cancel и редкие state transitions.

## Future parity requirements

- `REQ-UI-SIGNAL-001`: выделять из GUI регистраций **пользовательское действие → ответственность/побочный эффект → результат/ошибку**, а не считать счётчик `.connect` числом capabilities.
- `REQ-UI-SIGNAL-002`: учитывать `QTimer.timeout` и подписки на async state как **пассивные каналы наблюдения**, а не отдельно инициируемые операции.
- `REQ-UI-SIGNAL-003`: фиксировать source/handler path и статус ACTIVE/CONDITIONAL/UNRESOLVED при сверке; отсутствие прямой строки в AST не доказывает, что функция отсутствует.

**Вердикт:** 517/75 — инвентарь сквозной проверки UI, не показатель завершения всего GUI-аудита. Новая Rust-архитектура не выбиралась.
