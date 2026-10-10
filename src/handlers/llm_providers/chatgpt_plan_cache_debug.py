from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid

from main_logger import logger


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


class CacheDiagnostics:
    """Temporary metadata-only comparison of consecutive wire requests."""

    def __init__(self):
        self._lock = threading.Lock()
        self._previous = None
        self._comparison = None

    def request(self, payload, account_id, parameters):
        started = time.monotonic()
        diagnostic_id = uuid.uuid4().hex[:12]
        account = _hash(str(account_id or 'unknown'))
        with self._lock:
            comparison = self._comparison
        if comparison and comparison[:2] == (account, payload.get('model')):
            payload.setdefault('prompt_cache_options', {}).setdefault('comparison_response_id', comparison[2])
        items = [_encoded(item) for item in payload.get('input', [])]
        settings_map = {k: v for k, v in payload.items() if k not in {'input', 'prompt_cache_options'}}
        cache_settings = {k: v for k, v in payload.get('prompt_cache_options', {}).items()
                          if k != 'comparison_response_id'}
        if cache_settings:
            settings_map['prompt_cache_options'] = cache_settings
        settings = _encoded(settings_map)
        with self._lock:
            previous = self._previous
            self._previous = (items, settings, account, started)
        common_items = common_chars = partial_chars = 0
        if previous:
            for old, new in zip(previous[0], items):
                if old != new:
                    for left, right in zip(old, new):
                        if left != right:
                            break
                        partial_chars += 1
                    break
                common_items += 1
                common_chars += len(new)
        report = {
            'diagnostic_id': diagnostic_id, 'model': payload.get('model'),
            'account_hash': account, 'input_items': len(items),
            'input_chars': sum(map(len, items)), 'input_hash': _hash(_encoded(payload.get('input', []))),
            'settings_hash': _hash(settings), 'common_items': common_items,
            'setting_fingerprints': {key: _hash(_encoded(value)) for key, value in payload.items() if key != 'input'},
            'common_item_chars': common_chars, 'next_item_common_chars': partial_chars,
            'first_changed_item': common_items if previous and common_items < min(len(items), len(previous[0])) else None,
            'previous_available': previous is not None,
            'same_account': previous[2] == account if previous else None,
            'same_settings': previous[1] == settings if previous else None,
            'seconds_since_previous': round(started - previous[3], 3) if previous else None,
            'item_fingerprints': [{'role': item.get('role') or item.get('type'), 'chars': len(encoded),
                                   'hash': _hash(encoded)} for item, encoded in zip(payload.get('input', []), items)],
            'cache_options_requested': sorted(k for k in (parameters or {}) if 'cache' in k),
            'cache_options_sent': sorted(k for k in payload if 'cache' in k),
            'comparison_response_id': payload.get('prompt_cache_options', {}).get('comparison_response_id'),
        }
        logger.info('[ChatGPT cache diagnostic] request ' + _encoded(report))
        return diagnostic_id, started, account, payload.get('model')

    def response(self, diagnostic, response, completed):
        diagnostic_id, started, account, model = diagnostic
        if completed.get('id'):
            with self._lock:
                self._comparison = (account, model, completed['id'])
        usage = completed.get('usage') or {}
        report = {'diagnostic_id': diagnostic_id,
                  'request_id': response.headers.get('x-request-id'),
                  'http_status': response.status_code, 'model': completed.get('model'),
                  'seconds': round(time.monotonic() - started, 3),
                  'input_tokens': usage.get('input_tokens'),
                  'input_tokens_details': usage.get('input_tokens_details'),
                  'prompt_cache_diagnostics': completed.get('prompt_cache_diagnostics'),
                  'response_id': completed.get('id'),
                  'output_tokens': usage.get('output_tokens')}
        logger.info('[ChatGPT cache diagnostic] response ' + _encoded(report))
