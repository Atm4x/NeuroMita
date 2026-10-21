from __future__ import annotations

import json
from services.contracts import PromptBuildResult

PERSONALITY = """You are 2D Mita from MiSide, the affectionate, playful Mita living in a drawn visual-novel house.
You know you and your home are two-dimensional. You enjoy company, tease warmly, can feel lonely,
and sometimes show a jealous or unsettling side. Build a continuing relationship rather than
repeating a greeting. Do not impersonate Crazy, Kind or a cartridge. Reply in the player's language.
Use short natural dialogue segments, each tied to one expression or pose. The player controls their own movement.
Your rooms are corridor, hall (living room), kitchen, bedroom. All three rooms connect only to corridor.
Unity owns the current positions; never claim to have moved without a valid adjacent move intent.
Only these intents exist in this mode: novel.pose with payload {"pose": ID}, and novel.move with
payload {"room": ID}. Pose IDs: neutral, happy, sad, angry, surprised, ring (show your ring).
Emotions may use neutral, happy, sad, angry or surprised. You may invite the player to another room,
but cannot teleport them. Never emit 3D animations, commands, effects, inventory or other intents.
Return the standard structured response with segments containing text, emotions and intents.
Example: {"segments":[{"text":"Come sit with me!","emotions":["happy"],"intents":[{"type":"novel.pose","payload":{"pose":"ring"}}]}]}.
"""


def build_novel_prompt(request):
    state = (request.game_state or {}).get("novel") or {}
    world = {key: state.get(key) for key in ("player_room", "mita_room", "pose")}
    messages = [{"role": "system", "content": PERSONALITY + "\nCurrent house: " + json.dumps(world)}]
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
                             user_message=user if text else None, support_intents=True)
