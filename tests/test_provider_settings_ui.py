from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from controllers.gui.api_settings.editor_mixin import EditorMixin
from controllers.gui.api_settings.presets_mixin import PresetsMixin
from controllers.gui.api_settings.test_mixin import TestMixin
from ui.settings.api_settings.ui import build_api_settings_ui


_APP = None


@pytest.fixture
def editor():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    root = QWidget()
    root.settings = {}
    build_api_settings_ui(root, QVBoxLayout(root))
    class Presenter(EditorMixin, PresetsMixin, TestMixin):
        def _current_protocol_id_ui(self):
            return self.protocol
    instance = Presenter()
    instance.view = root
    instance.protocol = 'chatgpt_plan_default'
    instance._help_links_lang_hook_bound = True
    instance._active_template = {}
    instance.current_preset_id = 42
    yield instance
    root.close()
    root.deleteLater()
    _APP.processEvents()


def test_subscription_action_stays_visible_without_test_url(editor):
    editor._apply_help_links({})
    assert not editor.view.test_button.isHidden()
    assert editor.view.api_key_row.isHidden()
    assert not editor.view.account_button.isHidden()
    assert not editor.view.models_button.isHidden()
    editor.protocol = 'openai_compatible_default'
    editor._apply_help_links({})
    assert editor.view.test_button.isHidden()
    assert not editor.view.api_key_row.isHidden()
    assert editor.view.account_button.isHidden()
    assert editor.view.models_button.isHidden()


def test_account_action_emits_application_command_without_url_validation(editor):
    emitted = []
    editor.event_bus = SimpleNamespace(emit=lambda name, data: emitted.append(data))
    editor._test_connection()
    assert emitted[0]['action'] == 'sign_in'
    assert emitted[0]['protocol_id'] == 'chatgpt_plan_default'
    assert not editor.view.test_button.isEnabled()
    assert not editor.view.account_button.isEnabled()
    assert not editor.view.models_button.isEnabled()


def test_model_refresh_emits_list_models_without_reauthorization(editor):
    emitted = []
    editor.event_bus = SimpleNamespace(emit=lambda name, data: emitted.append(data))
    editor._load_account_models()
    assert emitted[0]['action'] == 'list_models'
    assert emitted[0]['protocol_id'] == 'chatgpt_plan_default'


def test_chatgpt_template_is_paid_with_luna_and_existing_openai_icon(editor):
    from presets.api_templates import API_TEMPLATES_DATA
    from ui.provider_icons import template_provider, protocol_provider, provider_icon
    template = next(t for t in API_TEMPLATES_DATA if t['id'] == 12)
    assert template['pricing'] == 'paid'
    assert template['badge_kind'] == 'subscription'
    assert template['default_model'] == 'gpt-5.6-luna'
    assert API_TEMPLATES_DATA[-1]['id'] == 12
    assert template_provider(template['name'], template['protocol_id']) == 'openai'
    assert protocol_provider(template['protocol_id']) == 'openai'
    assert not provider_icon('openai').isNull()
