from __future__ import annotations

import json
from services.contracts import PromptBuildResult


def build_cartridge_prompt(request) -> PromptBuildResult:
    character = request.character
    definition = character.cartridge_definition
    history = []
    if request.policy.use_history_in_prompt:
        history = character.history_manager.get_recent_messages(limit=definition.history_messages)
    contract = (
        "You are a virtual cartridge personality. Reply briefly in the player's language. "
        "You have no body, no game-control permissions, and cannot learn or activate abilities. "
        "Return a structured response with text segments only; omit intents, commands and game effects."
    )
    messages = [{"role": "system", "content": definition.prompt + "\n" + contract}]
    budget = max(0, definition.context_characters - len(messages[0]["content"]))
    user_text = str(request.user_input or "")[:min(2000, max(0, budget - 128))]
    budget -= len(user_text)
    participants = [str(p) for p in (request.participants or [])][:16]
    if participants:
        content = ("Present speakers: " + ", ".join(participants))[:budget // 2]
        messages.append({"role": "system", "content": content})
        budget -= len(content)
    if request.system_input:
        content = str(request.system_input)[:min(1500, budget // 2)]
        messages.append({"role": "system", "content": content})
        budget -= len(content)
    recent = []
    for message in reversed(history):
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if len(content) > budget:
            break
        if message.get("role") in ("user", "assistant"):
            budget -= len(content)
            recent.append({"role": message["role"], "content": content})
    recent.reverse()
    messages.extend(recent)
    user_message = {"role": "user", "content": user_text, "sender": str(request.sender or "Player")}
    if user_message["content"]:
        messages.append(user_message)
    history_messages = recent + ([user_message] if user_message["content"] else [])
    return PromptBuildResult(messages=messages, history_messages=history_messages, user_message=user_message, support_intents=False)
