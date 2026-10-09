from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from core.app_paths import settings_path
from main_logger import logger


AUTHORIZE_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
OIDC_CONFIG_URL = "https://auth.openai.com/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
AGENT_NAME = "NeuroMita"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(str(value) + "=" * (-len(str(value)) % 4))


def make_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def validate_id_token_claims(
    claims: Mapping[str, Any], *, client_id: str, nonce: str, now: int | None = None
) -> None:
    now = int(time.time()) if now is None else int(now)
    if str(claims.get("iss") or "") != "https://auth.openai.com":
        raise ValueError("Unexpected OpenAI ID token issuer")
    aud = claims.get("aud")
    audiences = [str(x) for x in aud] if isinstance(aud, list) else [str(aud or "")]
    if str(client_id) not in audiences:
        raise ValueError("OpenAI ID token audience mismatch")
    if str(claims.get("nonce") or "") != str(nonce):
        raise ValueError("OpenAI ID token nonce mismatch")
    if int(claims.get("exp") or 0) <= now:
        raise ValueError("OpenAI ID token expired")
    if not str(claims.get("sub") or ""):
        raise ValueError("OpenAI ID token subject is missing")


class ChatGPTPlanAuth:
    """OAuth session manager for the OSS Sign in with ChatGPT flow."""

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(follow_redirects=True, timeout=30.0, trust_env=True)
        self._owns_client = client is None
        self._lock = threading.RLock()
        self._path = settings_path("chatgpt_plan_auth.json", create_parent=True)
        self._data = self._load()
        if not self._data.get("ext_agent_host_id"):
            self._data["ext_agent_host_id"] = f"urn:uuid:{uuid.uuid4()}"
            self._save()

    @property
    def host_id(self) -> str:
        return str(self._data.get("ext_agent_host_id") or "")

    def status(self) -> dict[str, Any]:
        with self._lock:
            account = self._data.get("account") if isinstance(self._data.get("account"), dict) else {}
            return {
                "signed_in": bool(account.get("client_id") and account.get("refresh_token")),
                "email": str(account.get("email") or ""),
                "client_id": str(account.get("client_id") or ""),
                "scopes": list(account.get("scopes") or []),
            }

    def sign_in(self, timeout: float = 240.0) -> dict[str, Any]:
        with self._lock:
            account = self._data.get("account") if isinstance(self._data.get("account"), dict) else {}
            saved_client_id = str(account.get("client_id") or "")
            client_id = saved_client_id or DYNAMIC_CLIENT_ID
            verifier, challenge = make_pkce_pair()
            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            callback: dict[str, str] = {}
            event = threading.Event()

            auth_manager = self

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlparse(self.path)
                    if parsed.path != "/auth/callback":
                        self.send_response(404)
                        self.end_headers()
                        return
                    values = parse_qs(parsed.query)
                    for key in ("code", "state", "client_id", "scope", "error", "error_description"):
                        if values.get(key):
                            callback[key] = str(values[key][0])
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        "<html><body><h2>NeuroMita</h2><p>Authorization received. You can close this tab.</p></body></html>".encode("utf-8")
                    )
                    event.set()

                def log_message(self, *_args):
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = int(server.server_address[1])
            redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
            thread = threading.Thread(target=server.serve_forever, name="chatgpt-plan-oauth", daemon=True)
            thread.start()

            params = {
                "client_id": client_id,
                "ext_agent_host_id": self.host_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": SCOPES,
                "resource": RESOURCE,
                "state": state,
                "nonce": nonce,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
            if not saved_client_id:
                params["agent_name_hint"] = AGENT_NAME
            else:
                id_token_hint = str(account.get("id_token") or "")
                email = str(account.get("email") or "")
                if id_token_hint:
                    params["id_token_hint"] = id_token_hint
                if email:
                    params["login_hint"] = email

            auth_url = AUTHORIZE_URL + "?" + urlencode(params)
            try:
                if not webbrowser.open(auth_url, new=1, autoraise=True):
                    logger.warning("Could not open the system browser for Sign in with ChatGPT")
                if not event.wait(max(1.0, float(timeout))):
                    raise TimeoutError("Sign in with ChatGPT timed out")
            finally:
                server.shutdown()
                server.server_close()

            if callback.get("state") != state:
                raise ValueError("Sign in with ChatGPT returned an invalid state")
            if callback.get("error"):
                raise RuntimeError(callback.get("error_description") or callback["error"])
            code = str(callback.get("code") or "")
            if not code:
                raise RuntimeError("Sign in with ChatGPT did not return an authorization code")

            returned_client_id = str(callback.get("client_id") or "")
            if saved_client_id:
                if returned_client_id and returned_client_id != saved_client_id:
                    raise ValueError("Sign in with ChatGPT returned a different client registration")
                issued_client_id = saved_client_id
            else:
                issued_client_id = returned_client_id
                if not issued_client_id or issued_client_id == DYNAMIC_CLIENT_ID:
                    raise RuntimeError("ChatGPT client registration was not completed")

            token_response = self._client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": issued_client_id,
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": redirect_uri,
                    "resource": RESOURCE,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()
            record = self._validated_record(tokens, issued_client_id, nonce)
            self._data["account"] = record
            self._save()
            return self.status()

    def get_access_token(self) -> str:
        with self._lock:
            account = self._data.get("account") if isinstance(self._data.get("account"), dict) else {}
            access_token = str(account.get("access_token") or "")
            expires_at = int(account.get("expires_at") or 0)
            if access_token and expires_at > int(time.time()) + 90:
                return access_token
            if not account.get("refresh_token") or not account.get("client_id"):
                raise RuntimeError("Sign in with ChatGPT is required")
            self._refresh(account)
            return str(self._data["account"].get("access_token") or "")

    def list_models(self) -> list[dict[str, str]]:
        token = self.get_access_token()
        response = self._client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
        models = data.get("models") if isinstance(data, dict) else []
        result: list[dict[str, str]] = []
        for item in models or []:
            if not isinstance(item, dict) or item.get("visibility") != "list":
                continue
            slug = str(item.get("slug") or "").strip()
            if slug:
                result.append({"id": slug, "name": str(item.get("display_name") or slug)})
        return result

    def _refresh(self, account: dict[str, Any]) -> None:
        response = self._client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": str(account.get("client_id") or ""),
                "refresh_token": str(account.get("refresh_token") or ""),
                "resource": RESOURCE,
            },
        )
        response.raise_for_status()
        payload = response.json()
        account["access_token"] = str(payload.get("access_token") or "")
        if payload.get("refresh_token"):
            account["refresh_token"] = str(payload["refresh_token"])
        if payload.get("id_token"):
            account["id_token"] = str(payload["id_token"])
        account["expires_at"] = int(time.time()) + int(payload.get("expires_in") or 3600)
        scopes = str(payload.get("scope") or "").split()
        if scopes:
            account["scopes"] = scopes
        self._data["account"] = account
        self._save()

    def _validated_record(self, tokens: Mapping[str, Any], client_id: str, nonce: str) -> dict[str, Any]:
        id_token = str(tokens.get("id_token") or "")
        if not id_token:
            raise ValueError("OpenAI token response did not include an ID token")
        claims = self._validate_jwt(id_token, client_id=client_id, nonce=nonce)
        scopes = str(tokens.get("scope") or "").split()
        if "chatgpt.tokens.use.direct" not in scopes:
            raise PermissionError("ChatGPT plan usage permission was not granted")
        return {
            "email": str(claims.get("email") or ""),
            "issuer": str(claims.get("iss") or ""),
            "subject": str(claims.get("sub") or ""),
            "client_id": client_id,
            "ext_agent_host_id": self.host_id,
            "id_token": id_token,
            "access_token": str(tokens.get("access_token") or ""),
            "refresh_token": str(tokens.get("refresh_token") or ""),
            "token_type": str(tokens.get("token_type") or "Bearer"),
            "expires_at": int(time.time()) + int(tokens.get("expires_in") or 3600),
            "scopes": scopes,
        }

    def _validate_jwt(self, token: str, *, client_id: str, nonce: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid OpenAI ID token")
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        if str(header.get("alg") or "") != "RS256":
            raise ValueError("Unsupported OpenAI ID token algorithm")

        discovery = self._client.get(OIDC_CONFIG_URL)
        discovery.raise_for_status()
        jwks_uri = str(discovery.json().get("jwks_uri") or "")
        if not jwks_uri:
            raise ValueError("OpenAI OIDC configuration has no JWKS URI")
        jwks_response = self._client.get(jwks_uri)
        jwks_response.raise_for_status()
        keys = jwks_response.json().get("keys") or []
        key = next((item for item in keys if isinstance(item, dict) and item.get("kid") == header.get("kid")), None)
        if not key:
            raise ValueError("OpenAI ID token signing key was not found")

        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15

        n = int.from_bytes(_b64url_decode(str(key.get("n") or "")), "big")
        e = int.from_bytes(_b64url_decode(str(key.get("e") or "")), "big")
        public_key = RSA.construct((n, e))
        digest = SHA256.new(f"{parts[0]}.{parts[1]}".encode("ascii"))
        try:
            pkcs1_15.new(public_key).verify(digest, _b64url_decode(parts[2]))
        except (ValueError, TypeError) as exc:
            raise ValueError("OpenAI ID token signature verification failed") from exc

        validate_id_token_claims(claims, client_id=client_id, nonce=nonce)
        return claims

    def _load(self) -> dict[str, Any]:
        try:
            path = Path(self._path)
            if not path.exists():
                return {}
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            if payload.get("protected_account"):
                payload["account"] = self._unprotect_json(str(payload.pop("protected_account")))
            return payload
        except Exception as exc:
            logger.warning("Failed to load ChatGPT plan credentials: %s", exc)
            return {}

    def _save(self) -> None:
        path = Path(self._path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ext_agent_host_id": self._data.get("ext_agent_host_id", "")}
        account = self._data.get("account")
        if isinstance(account, dict) and account:
            payload["protected_account"] = self._protect_json(account)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    @staticmethod
    def _protect_json(value: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(value), ensure_ascii=False).encode("utf-8")
        if os.name == "nt":
            import win32crypt
            encrypted = win32crypt.CryptProtectData(raw, "NeuroMita ChatGPT Plan", None, None, None, 0)[1]
            return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
        return "file:" + base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _unprotect_json(value: str) -> dict[str, Any]:
        mode, _, encoded = str(value).partition(":")
        raw = base64.b64decode(encoded.encode("ascii"))
        if mode == "dpapi":
            if os.name != "nt":
                raise RuntimeError("Windows DPAPI credentials cannot be opened on this platform")
            import win32crypt
            raw = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


_default_auth: ChatGPTPlanAuth | None = None
_default_lock = threading.Lock()


def get_chatgpt_plan_auth() -> ChatGPTPlanAuth:
    global _default_auth
    with _default_lock:
        if _default_auth is None:
            _default_auth = ChatGPTPlanAuth()
        return _default_auth


__all__ = [
    "ChatGPTPlanAuth", "get_chatgpt_plan_auth", "make_pkce_pair", "validate_id_token_claims",
]
