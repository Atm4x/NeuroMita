from __future__ import annotations

import socket
import ssl
import sys
import unittest
from pathlib import Path

import httpx

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from core.networking.errors import classify_network_error


class NetworkErrorClassificationTests(unittest.TestCase):
    def _connect_error(self, cause: BaseException) -> httpx.ConnectError:
        error = httpx.ConnectError("connection failed", request=httpx.Request("GET", "https://example.test"))
        error.__cause__ = cause
        return error

    def test_certificate_verification_is_non_retryable_tls_error(self) -> None:
        error = self._connect_error(ssl.SSLCertVerificationError("certificate verify failed"))

        result = classify_network_error("test", error)

        self.assertEqual(result.code, "network.tls.certificate")
        self.assertEqual(result.phase, "connect")
        self.assertFalse(result.retryable)

    def test_generic_ssl_error_is_non_retryable_handshake_error(self) -> None:
        result = classify_network_error("test", self._connect_error(ssl.SSLError("handshake failed")))

        self.assertEqual(result.code, "network.tls.handshake")
        self.assertFalse(result.retryable)

    def test_dns_connect_error_remains_retryable(self) -> None:
        result = classify_network_error("test", self._connect_error(socket.gaierror("getaddrinfo failed")))

        self.assertEqual(result.code, "network.dns")
        self.assertTrue(result.retryable)

    def test_plain_connect_error_remains_retryable(self) -> None:
        result = classify_network_error("test", self._connect_error(OSError("connection refused")))

        self.assertEqual(result.code, "network.connect")
        self.assertTrue(result.retryable)

    def test_secret_query_parameter_is_redacted(self) -> None:
        error = httpx.ConnectError("failed", request=httpx.Request("GET", "https://example.test/?key=secret-value"))

        result = classify_network_error("test", error)

        self.assertNotIn("secret-value", result.url or "")
        self.assertIn("redacted", result.url or "")


if __name__ == "__main__":
    unittest.main()
