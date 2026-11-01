import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from controllers.api_presets_controller import ApiPresetsController, ApiTemplate
from controllers.protocols_controller import ProtocolsController
from handlers.llm_providers.base import LLMRequest
from handlers.llm_providers.errors import LLMProviderError
from managers.provider_manager import ProviderManager
from model_settings.repository import SchemaRepository
from model_settings.service import ModelSettingsService
from presets.api_protocols import API_PROTOCOLS_DATA
from presets.api_templates import API_TEMPLATES_DATA
from presets.opencode import model_family, template_data, route_model, resolve_preset
from utils.opencode_session import session_id
from services.provider_settings import describe_protocol
from utils.api_filters import apply_filter


@pytest.mark.parametrize('template', template_data(), ids=lambda t: t['protocol_id'])
def test_templates_resolve_real_protocol_auth_and_schema(template, tmp_path):
    ApiTemplate(**template)
    proto = next(p for p in API_PROTOCOLS_DATA if p['id'] == template['protocol_id'])
    service = ModelSettingsService(SchemaRepository(tmp_path / 'schemas'))
    document = service.create(template['settings_schema_id'])
    service.compile(document, proto['dialect'])
    built = ProtocolsController.__new__(ProtocolsController).build_http_request(
        protocol_id=proto['id'], url=template.get('url') or template['url_tpl'].format(model=template['default_model']),
        api_key='test-key', headers={},
    )
    assert built['headers']['Authorization'] == 'Bearer test-key'
    assert built['headers']['User-Agent'] == 'NeuroMita/1.0'
    assert 'key=' not in built['url']
    assert model_family(template['default_model'], go='_go_' in proto['id']) == proto['id'].rsplit('_', 1)[1]
    descriptor = describe_protocol(proto['id'])
    assert descriptor.settings.api_key and not descriptor.account_actions
    assert descriptor.subscription_notice[0]
    assert descriptor.action_label[1] == 'Load models'


def test_catalog_separates_api_families_preserves_metadata_and_marks_free():
    raw = {'data': [{'id': m, 'context_length': 32000} for m in (
        'glm-5.3-flash', 'gpt-6-luna', 'grok-4.7', 'gemini-4-argon',
        'claude-haiku-5-5', 'qwen3.8-max', 'qwen3.8-flash', 'minimax-m3',
        'beam-free', 'big-pickle', 'jev-1.13-free', 'unknown-future-model', 'test',
    )]}
    console = apply_filter('opencode_zen_chat', raw)['models']
    go = apply_filter('opencode_go_chat', raw)['models']
    assert {m['id'] for m in console} == {'glm-5.3-flash', 'qwen3.8-max', 'minimax-m3', 'beam-free', 'big-pickle'}
    assert {m['id'] for m in go} == {'glm-5.3-flash', 'beam-free', 'big-pickle'}
    free = next(m for m in console if m['id'] == 'beam-free')
    assert free['is_free'] and 'experimental' in free['name']
    assert free['context_length'] == 32000
    assert all('name' not in m for m in raw['data'])
    assert {m['id'] for m in apply_filter('opencode_go_responses', raw)['models']} == {'gpt-6-luna', 'grok-4.7'}
    assert [m['id'] for m in apply_filter('opencode_zen_gemini', raw)['models']] == ['gemini-4-argon']


@pytest.mark.parametrize('model,protocol,code', [
    ('gpt-6-luna', 'opencode_go_chat', 'opencode.model_api_mismatch'),
    ('claude-haiku-5-5', 'opencode_zen_chat', 'opencode.model_api_mismatch'),
])
def test_invalid_model_fails_before_network(model, protocol, code):
    manager = ProviderManager.__new__(ProviderManager)
    with pytest.raises(LLMProviderError) as error:
        manager.generate(LLMRequest(model=model, messages=[], protocol_id=protocol, provider_name='common'))
    assert error.value.code == code
    assert not error.value.retryable


@pytest.mark.parametrize('family,provider', [('chat', 'common'), ('responses', 'responses'), ('gemini', 'gemini')])
def test_generation_routes_to_existing_transport(monkeypatch, family, provider):
    model = {'chat': 'glm-5.3-flash', 'responses': 'gpt-6-luna', 'gemini': 'gemini-4-argon'}[family]
    template = resolve_preset(template_data()[1], model)
    proto = next(p for p in API_PROTOCOLS_DATA if p['id'] == template['protocol_id'])
    manager = ProviderManager.__new__(ProviderManager)
    transport = SimpleNamespace(name=provider, generate=Mock(return_value='response'))
    manager._find_by_name = Mock(return_value=transport)
    monkeypatch.setattr('managers.provider_manager.preprocess_messages_for_provider', lambda *a: None)
    request = LLMRequest(model=template['default_model'], messages=[], protocol_id=proto['id'],
                         dialect_id=proto['dialect'], provider_name=proto['provider'])
    assert manager.generate(request) == 'response'
    manager._find_by_name.assert_called_once_with(provider)


def test_public_catalog_check_does_not_claim_key_validation(monkeypatch):
    controller = ApiPresetsController.__new__(ApiPresetsController)
    controller.event_bus = Mock()
    controller._update_preset_models = Mock()
    response = SimpleNamespace(status_code=200, text=json.dumps({'data': [
        {'id': 'glm-5.3-flash'}, {'id': 'gpt-6-luna'}, {'id': 'beam-free'},
    ]}), close=Mock())
    controller._http_transport = SimpleNamespace(get=Mock(return_value=response))
    builder = ProtocolsController.__new__(ProtocolsController)
    monkeypatch.setattr('controllers.api_presets_controller.use', lambda _: builder)
    template = ApiTemplate(**template_data()[0])
    controller._sync_test_connection(101, template, '')
    result = controller.event_bus.emit.call_args.args[1]
    assert result['success']
    assert result['models'] == ['glm-5.3-flash', 'gpt-6-luna', 'beam-free']
    assert 'not validated' in result['message'] or 'не проверены' in result['message']
    response.close.assert_called_once()
    controller._update_preset_models.assert_called_once_with(101, result['models'])


def test_session_is_stable_distinct_and_supports_cyrillic():
    assert session_id('mita') == session_id('mita')
    assert session_id('mita') != session_id('other')
    assert session_id('', 'Мита') != session_id('', 'Мила')
    assert session_id() == session_id()


def test_template_ids_are_unique():
    assert len({t['id'] for t in API_TEMPLATES_DATA}) == len(API_TEMPLATES_DATA)
    assert [t['name'] for t in template_data()] == ['OpenCode Zen', 'OpenCode Go']
    assert all(t['pricing'] == 'paid' for t in template_data())


def test_free_zen_request_reaches_transport(monkeypatch):
    manager = ProviderManager.__new__(ProviderManager)
    transport = SimpleNamespace(name='common', generate=Mock(return_value='free response'))
    manager._find_by_name = Mock(return_value=transport)
    monkeypatch.setattr('managers.provider_manager.preprocess_messages_for_provider', lambda *a: None)
    request = LLMRequest(model='big-pickle', messages=[], protocol_id='opencode_zen_chat', provider_name='common')
    assert manager.generate(request) == 'free response'
    transport.generate.assert_called_once_with(request)


@pytest.mark.parametrize('go', [False, True])
@pytest.mark.parametrize('model,family,suffix', [
    ('glm-5.3-flash', 'chat', '/openai/v1/chat/completions'),
    ('gpt-6-luna', 'responses', '/openai/v1/responses'),
    ('gemini-4-argon', 'gemini', '/google/v1beta/models/gemini-4-argon:generateContent'),
])
def test_resolver_automatically_routes_model_overrides(tmp_path, go, model, family, suffix):
    from managers.api_preset_resolver import ApiPresetResolver
    service = ModelSettingsService(SchemaRepository(tmp_path / 'schemas'))
    document = service.create('openai-compatible')
    document['values']['max_tokens'] = 2048
    document['enabled'] = ['max_tokens']
    preset = {**template_data()[int(go)], 'key': 'test-key', 'model_settings': document}
    resolver = ApiPresetResolver({}, None, model_settings_service=service)
    resolver._load_preset_full = Mock(return_value=preset)
    resolved = resolver.resolve(preset['id'], model_override=model)
    assert resolved.protocol_id == f"opencode_{'go' if go else 'zen'}_{family}"
    assert resolved.api_url == 'https://opencode.ai/inference' + ('/go' if go else '') + suffix
    assert resolved.headers['Authorization'] == 'Bearer test-key'
    assert resolved.api_model == model
    assert '2048' in str(resolved.native_parameters)
    assert document['schema_id'] == 'openai-compatible'


def test_go_catalog_includes_deepseek_alongside_responses_models():
    models = apply_filter('opencode_go_all', {'data': [
        {'id': 'deepseek-v4.1-flash'}, {'id': 'deepseek-v4-pro'},
        {'id': 'grok-4.7'}, {'id': 'gemini-4-argon'}, {'id': 'claude-haiku-5-5'},
    ]})['models']
    assert [m['id'] for m in models] == ['deepseek-v4.1-flash', 'deepseek-v4-pro', 'grok-4.7', 'gemini-4-argon']
