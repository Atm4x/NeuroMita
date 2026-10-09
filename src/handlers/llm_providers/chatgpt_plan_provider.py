from __future__ import annotations

from typing import Any

from utils import _

from .base import (
    BaseProvider, LLMRequest, LLMResponse, LLMUsage, StreamChannel,
    check_request_cancelled, record_response_body_started,
)
from .chatgpt_plan_auth import get_chatgpt_plan_auth
from .chatgpt_plan_protocol import build_responses_payload, normalize_responses_usage, parse_sse_data_line
from .errors import LLMProviderError


class ChatGPTPlanProvider(BaseProvider):
    """Direct Responses API transport authorized by Sign in with ChatGPT."""

    name = "chatgpt_plan"
    priority = 15
    supports_tools_native = False
    supports_streaming = True
    supports_streaming_with_tools = False
    supports_stream_usage = True

    def is_applicable(self, req: LLMRequest) -> bool:
        return str(req.provider_name or "") == self.name

    def generate(self, req: LLMRequest) -> LLMResponse:
        auth = get_chatgpt_plan_auth()
        try:
            access_token = auth.get_access_token()
        except Exception as exc:
            raise LLMProviderError(
                provider=self.name,
                friendly_message=_(
                    "Войдите через ChatGPT в настройках API перед использованием этого провайдера.",
                    "Sign in with ChatGPT in API settings before using this provider.",
                ),
                provider_message=str(exc),
                retryable=False,
                code="chatgpt_plan.sign_in_required",
                phase="auth",
            ) from exc

        url = str(req.api_url or "https://api.openai.com/v1/responses")
        payload = build_responses_payload(req.model, req.messages)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        headers.update(req.headers or {})

        response = self.http_transport.post_json(req, url, headers=headers, payload=payload, stream=True)
        try:
            if response.status_code != 200:
                body = response.read().decode("utf-8", errors="replace")
                raise LLMProviderError(
                    provider=self.name,
                    friendly_message=self._http_error_message(response.status_code),
                    status_code=int(response.status_code),
                    provider_message=body[:2000],
                    raw_payload=body,
                    retryable=response.status_code in {408, 429, 500, 502, 503, 504},
                    code=f"chatgpt_plan.http_{response.status_code}",
                    phase="http",
                    url=url,
                )

            record_response_body_started(req)
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            usage: LLMUsage | None = None
            completed_response: dict[str, Any] = {}
            completed = False

            for line in response.iter_lines():
                check_request_cancelled(req)
                event = parse_sse_data_line(line)
                if not event:
                    continue
                event_type = str(event.get("type") or "")

                if event_type == "response.output_text.delta":
                    delta = str(event.get("delta") or "")
                    if delta:
                        text_parts.append(delta)
                        if req.stream and req.stream_cb:
                            req.stream_cb(delta, StreamChannel.CONTENT)
                    continue

                if event_type in {"response.reasoning_summary_text.delta", "response.reasoning_text.delta"}:
                    delta = str(event.get("delta") or "")
                    if delta:
                        reasoning_parts.append(delta)
                        if req.stream and req.stream_cb:
                            req.stream_cb(delta, StreamChannel.REASONING)
                    continue

                if event_type == "response.completed":
                    completed_response = event.get("response") if isinstance(event.get("response"), dict) else {}
                    usage_map = normalize_responses_usage(completed_response.get("usage"))
                    if usage_map:
                        usage = LLMUsage(**usage_map)
                    completed = True
                    continue

                if event_type == "response.failed":
                    failed = event.get("response") if isinstance(event.get("response"), dict) else {}
                    error = failed.get("error") if isinstance(failed.get("error"), dict) else {}
                    code = str(error.get("code") or "chatgpt_plan.response_failed")
                    detail = str(error.get("message") or code)
                    quota = code in {
                        "subscription_sharing_usage_limit_exceeded",
                        "subscription_sharing_usage_unavailable",
                    }
                    raise LLMProviderError(
                        provider=self.name,
                        friendly_message=_(
                            "Квота ChatGPT/Codex для приложений исчерпана или временно недоступна. Проверьте Usage в ChatGPT или используйте резервный провайдер.",
                            "ChatGPT/Codex app quota is exhausted or temporarily unavailable. Check Usage in ChatGPT or use a fallback provider.",
                        ) if quota else _(
                            "ChatGPT не смог завершить ответ.",
                            "ChatGPT could not complete the response.",
                        ),
                        provider_message=detail,
                        raw_payload=failed,
                        retryable=not quota,
                        code=code,
                        phase="stream",
                        url=url,
                    )

                if event_type == "response.incomplete":
                    raise LLMProviderError(
                        provider=self.name,
                        friendly_message=_("ChatGPT вернул незавершённый ответ.", "ChatGPT returned an incomplete response."),
                        provider_message=str(event),
                        raw_payload=event,
                        retryable=True,
                        code="chatgpt_plan.response_incomplete",
                        phase="stream",
                        url=url,
                    )

            if not completed:
                raise LLMProviderError(
                    provider=self.name,
                    friendly_message=_(
                        "Поток ChatGPT завершился без подтверждения response.completed.",
                        "The ChatGPT stream ended without response.completed.",
                    ),
                    retryable=True,
                    code="chatgpt_plan.stream_interrupted",
                    phase="stream",
                    url=url,
                )

            return LLMResponse(
                text="".join(text_parts),
                reasoning="".join(reasoning_parts),
                usage=usage,
                model=str(completed_response.get("model") or req.model),
                provider_name=self.name,
                provider_display_name=req.provider_display_name or "ChatGPT Plan (Codex)",
                finish_reason="completed",
                raw=completed_response,
            )
        finally:
            response.close()

    @staticmethod
    def _http_error_message(status: int) -> str:
        if status in {401, 403}:
            return _(
                "Сессия ChatGPT недействительна или доступ к использованию плана не разрешён. Выполните вход заново.",
                "The ChatGPT session is invalid or plan usage is not authorized. Sign in again.",
            )
        if status == 429:
            return _(
                "Достигнут лимит ChatGPT/Codex. Проверьте Usage в ChatGPT или используйте резервный провайдер.",
                "The ChatGPT/Codex usage limit was reached. Check Usage in ChatGPT or use a fallback provider.",
            )
        return _("Ошибка Responses API ChatGPT.", "ChatGPT Responses API error.")


__all__ = ["ChatGPTPlanProvider"]
