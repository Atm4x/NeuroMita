from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from handlers.llm_providers.base import LLMRequest
from handlers.llm_providers.errors import LLMProviderError
from handlers.llm_providers.gemini_provider import GeminiProvider


class _Response:
    status_code = 200
    headers = {}
    text = "{}"

    def __init__(self, payload):
        self._payload = payload
        self.closed = False

    def json(self):
        return self._payload

    def read(self):
        return b""

    def close(self):
        self.closed = True


class _Transport:
    def __init__(self, payload):
        self.payload = payload
        self.response = None

    def post_json(self, req, url, headers=None, payload=None, stream=False):
        self.response = _Response(self.payload)
        return self.response


class GeminiEmptyCompletionTests(unittest.TestCase):
    """Пустой ответ Gemini раньше превращался в "..." и падал на разборе JSON."""

    def _run(self, payload):
        transport = _Transport(payload)
        provider = GeminiProvider(http_transport=transport)
        req = LLMRequest(
            model="gemini-3.5-flash-lite",
            messages=[{"role": "user", "content": "привет"}],
            api_url=(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-3.5-flash-lite:generateContent"
            ),
            provider_name="gemini",
            capabilities={"streaming": True, "structured_output": True},
        )
        return provider, req, transport

    def test_empty_candidate_is_a_retryable_provider_error(self):
        provider, req, transport = self._run({
            "candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}],
            "promptFeedback": {"blockReason": "SAFETY"},
        })

        with self.assertRaises(LLMProviderError) as caught:
            provider.generate_request_gemini(req)

        error = caught.exception
        self.assertEqual("empty_completion", error.code)
        self.assertTrue(error.retryable)
        self.assertIn("SAFETY", error.provider_message)
        self.assertTrue(transport.response.closed)

    def test_function_call_only_response_is_not_treated_as_empty(self):
        provider, req, _ = self._run({
            "candidates": [{"content": {"parts": [{"functionCall": {"name": "look"}}]}}],
        })

        result = provider.generate_request_gemini(req)

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
