from __future__ import annotations

import json

from services.contracts import PromptBuildResult


def build_novel_prompt(request):
    character = request.character
    blocks, _ = character.dsl_interpreter.process_main_template(character.main_template_path_relative)
    prompt = "\n\n".join(block for block in blocks if block.strip())
    if not prompt:
        raise ValueError("2D Mita prompt set is empty: " + character.base_data_path)
    state = (request.game_state or {}).get("novel") or {}
    world = {key: state.get(key) for key in ("player_room", "mita_room", "pose", "transform", "appearance")}
    messages = [{"role": "system", "content": prompt + "\nCurrent house: " + json.dumps(world)}]
    budget = 16000
    text = str(request.user_input or "")[:2000]
    budget -= len(text)
    history = request.character.history_manager.get_recent_messages(limit=40) if request.policy.use_history_in_prompt else []
    recent = []
    for item in reversed(history):
        if item.get("role") not in ("user", "assistant"):
            continue
        content = item.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if len(content) > budget:
            break
        budget -= len(content)
        recent.append({"role": item["role"], "content": content})
    recent.reverse()
    messages.extend(recent)
    user = {"role": "user", "content": text, "sender": str(request.sender or "Player")}
    if text:
        messages.append(user)
    return PromptBuildResult(messages=messages, history_messages=recent + ([user] if text else []),
                             user_message=user if text else None, support_intents=bool(character.dsl_interpreter.get_prompt_feature("support_intents", True)))
