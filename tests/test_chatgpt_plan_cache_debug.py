import json
from types import SimpleNamespace

from handlers.llm_providers.chatgpt_plan_cache_debug import CacheDiagnostics


def test_cache_diagnostics_compare_actual_prefix_without_logging_content(monkeypatch):
    logs = []
    monkeypatch.setattr('handlers.llm_providers.chatgpt_plan_cache_debug.logger.info', logs.append)
    diagnostics = CacheDiagnostics()
    payload = {'model': 'luna', 'input': [{'role': 'developer', 'content': 'secret prompt'},
                                        {'role': 'user', 'content': 'hello'}], 'store': False}
    diagnostics.request(payload, 'private account', {'prompt_cache_key': 'secret key'})
    payload['input'][1]['content'] = 'help'
    token = diagnostics.request(payload, 'private account', {})
    diagnostics.response(token, SimpleNamespace(headers={'x-request-id': 'request123'}, status_code=200),
                         {'model': 'luna', 'usage': {'input_tokens': 2000,
                                                   'input_tokens_details': {'cached_tokens': 0}}})
    report = json.loads(logs[1].split('request ', 1)[1])
    assert report['common_items'] == 1
    assert report['first_changed_item'] == 1
    assert report['next_item_common_chars'] > 0
    assert report['same_settings'] is True and report['same_account'] is True
    assert json.loads(logs[0].split('request ', 1)[1])['cache_options_requested'] == ['prompt_cache_key']
    assert report['cache_options_sent'] == []
    result = json.loads(logs[2].split('response ', 1)[1])
    assert result['diagnostic_id'] == token[0]
    assert result['input_tokens_details']['cached_tokens'] == 0
    assert result['request_id'] == 'request123'
    assert not any(secret in '\n'.join(logs) for secret in ('secret prompt', 'private account', 'secret key'))


def test_changes_to_model_schema_and_account_are_visible(monkeypatch):
    logs = []
    monkeypatch.setattr('handlers.llm_providers.chatgpt_plan_cache_debug.logger.info', logs.append)
    diagnostics = CacheDiagnostics()
    diagnostics.request({'model': 'first', 'input': []}, 'one', {})
    diagnostics.request({'model': 'second', 'input': [], 'text': {'format': {'type': 'json_schema'}}}, 'two', {})
    report = json.loads(logs[-1].split('request ', 1)[1])
    assert report['same_account'] is False
    assert report['same_settings'] is False


def test_server_comparison_uses_completed_id_only_for_same_account_and_model(monkeypatch):
    logs = []
    monkeypatch.setattr('handlers.llm_providers.chatgpt_plan_cache_debug.logger.info', logs.append)
    diagnostics = CacheDiagnostics()
    first = diagnostics.request({'model': 'luna', 'input': []}, 'one', {})
    diagnostics.response(first, SimpleNamespace(headers={}, status_code=200), {'id': 'resp_baseline'})
    second_payload = {'model': 'luna', 'input': []}
    second = diagnostics.request(second_payload, 'one', {})
    assert second_payload['prompt_cache_options'] == {'comparison_response_id': 'resp_baseline'}
    report = json.loads(logs[-1].split('request ', 1)[1])
    assert report['same_settings'] is True
    diagnostics.response(second, SimpleNamespace(headers={}, status_code=200),
                         {'prompt_cache_diagnostics': {'type': 'unavailable'}})
    assert json.loads(logs[-1].split('response ', 1)[1])['prompt_cache_diagnostics'] == {'type': 'unavailable'}
    for account, model in [('two', 'luna'), ('one', 'other')]:
        payload = {'model': model, 'input': []}
        diagnostics.request(payload, account, {})
        assert 'prompt_cache_options' not in payload
