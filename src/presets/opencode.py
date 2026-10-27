"""OpenCode Console/Go endpoints and documented model API families."""
from __future__ import annotations

DOCS_URL = "https://opencode.ai/v2/docs/console/models/"
GO_DOCS_URL = "https://opencode.ai/v2/docs/console/go"
CONSOLE_URL = "https://opencode.ai/console"

CONSOLE_NOTICE = (
    "Zen: платные модели по API-ключу; бесплатные можно попробовать, но сервер может ограничить доступ или квоту (403/429). Загрузка моделей не проверяет ключ и баланс. Формат API выбирается автоматически. Anthropic Messages и System One пока не поддерживаются.",
    "Zen: paid models use an API key; free models can be tried, but the server may restrict access or quota (403/429). Loading models does not validate the key or balance. API format is selected automatically. Anthropic Messages and System One are not yet supported.",
)
GO_NOTICE = (
    "Go / Go Plus: подписка с API-ключом и квотами для coding agents; применимость к игровым диалогам не подтверждена. Доступ зависит от региона и настроек workspace. Загрузка моделей не проверяет подписку. Формат API выбирается автоматически; Anthropic Messages пока не поддерживается.",
    "Go / Go Plus: API-key subscription with quotas for coding agents; applicability to game dialogue is unconfirmed. Access depends on region and workspace settings. Loading models does not validate the subscription. API format is selected automatically; Anthropic Messages is not yet supported.",
)


def is_free_model(model: str) -> bool:
    return model == "big-pickle" or model.endswith("-free")


def model_family(model: str, *, go: bool) -> str:
    if model.startswith(("gpt-", "grok-", "muse-")):
        return "responses"
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith(("claude-", "jev-")) or model == "test":
        return "unsupported"
    if model.startswith("qwen"):
        return "chat" if not go and model == "qwen3.8-max" else "unsupported"
    if go and model in {"minimax-m3", "minimax-m2.7", "minimax-m2.5"}:
        return "unsupported"
    if is_free_model(model) or model.startswith((
        "glm-", "deepseek-", "kimi-", "minimax-", "mistral-", "longcat-",
        "mimo-", "hy3", "hy4", "step-", "space-",
    )):
        return "chat"
    return "unsupported"


def filter_models(data: dict, *, family: str = "all", go: bool) -> dict:
    models = []
    for raw in data.get("data", data.get("models", [])) or []:
        if not isinstance(raw, dict):
            continue
        model = str(raw.get("id") or "").strip()
        actual = model_family(model, go=go)
        if not model or actual == "unsupported" or (family != "all" and actual != family):
            continue
        free = is_free_model(model)
        entry = {**raw, "id": model, "is_free": free}
        if free and not go:
            entry["name"] = f"{model} (experimental / экспериментально)"
        models.append(entry)
    return {"models": models}


def route_model(protocol_id: str, model: str) -> dict:
    go = protocol_id.startswith("opencode_go_")
    family = model_family(model, go=go)
    if family == "unsupported":
        family = "chat"
    schema = {"chat": "openai-compatible", "responses": "openai-responses", "gemini": "google-level"}[family]
    path = {
        "chat": "/openai/v1/chat/completions", "responses": "/openai/v1/responses",
        "gemini": "/google/v1beta/models/{model}:generateContent",
    }[family]
    base = "https://opencode.ai/inference" + ("/go" if go else "")
    return {"protocol_id": f"opencode_{'go' if go else 'zen'}_{family}",
            "settings_schema_id": schema, "url": base + path.format(model=model), "url_tpl": ""}


def resolve_preset(preset: dict, model: str | None = None) -> dict:
    protocol = str(preset.get("protocol_id") or "")
    if not protocol.startswith(("opencode_go_", "opencode_zen_")):
        return preset
    model = str(model if model is not None else preset.get("default_model") or "").strip()
    return {**preset, **route_model(protocol, model), "default_model": model}


def canonical_template_id(identifier: int | None) -> int | None:
    return {15: 14, 16: 14, 18: 17, 19: 17}.get(identifier, identifier)


def protocol_data() -> list[dict]:
    protocols = []
    for go in (False, True):
        for family, dialect, schema, provider in (
            ("chat", "openai_chat_completions", "openai-compatible", "common"),
            ("responses", "openai_responses", "openai-responses", "common"),
            ("gemini", "gemini_generate_content", "google-level", "gemini"),
        ):
            name = "OpenCode Go" if go else "OpenCode Zen"
            caps = {"tools_native": True, "streaming": True,
                    "streaming_with_tools": family == "responses",
                    "structured_output": True, "structured_output_fallback": family != "responses"}
            if family == "chat":
                caps.update(structured_output_mode="json_object", supports_stream_usage=True)
            elif family == "responses":
                caps.update(native_structured_output=True, supports_stream_usage=True,
                            images=True, files=True, force_wire_stream=False, tools_namespace="")
            protocols.append({
                "id": f"opencode_{'go' if go else 'zen'}_{family}",
                "name": f"{name} ({family})", "display_name": name,
                "settings_schema_id": schema, "dialect": dialect, "provider": provider,
                "auth": {"mode": "bearer"}, "headers": {"User-Agent": "NeuroMita/1.0"},
                "capabilities": caps, "transforms": [],
            })
    return protocols


def template_data() -> list[dict]:
    templates = []
    for go in (False, True):
        base = "https://opencode.ai/inference" + ("/go" if go else "")
        name = "OpenCode Go" if go else "OpenCode Zen"
        templates.append({
            "id": 17 if go else 14, "name": name,
            "settings_schema_id": "openai-compatible", "pricing": "paid",
            "badge_kind": "subscription_only" if go else "",
            "url": base + "/openai/v1/chat/completions",
            "default_model": "glm-5.3-flash", "known_models": ["glm-5.3-flash"],
            "protocol_id": f"opencode_{'go' if go else 'zen'}_chat",
            "test_url": base + "/v1/models", "test_url_editable": False,
            "filter_fn": f"opencode_{'go' if go else 'zen'}_all",
            "documentation_url": GO_DOCS_URL if go else DOCS_URL,
            "models_url": GO_DOCS_URL if go else DOCS_URL, "key_url": CONSOLE_URL,
        })
    return templates
