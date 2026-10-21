from __future__ import annotations

import json

from characters.novel_personality import NOVEL_CHARACTER_PROMPT
from services.contracts import PromptBuildResult


PRESENTATION_CONTRACT = """Use short natural dialogue segments, each tied to one expression or pose. The player controls their own movement.
Your rooms are corridor, hall (living room), kitchen, bedroom. All three rooms connect only to corridor.
Unity owns the current positions; never claim to have moved without a valid adjacent move intent.
Only these intents exist in this mode: novel.pose with payload {"pose": ID}, and novel.move with
payload {"room": ID}, plus novel.transform with payload {"x": 0.0, "y": 0.0, "scale": 1.0, "duration": 0.35}.
Transform fields are optional, but include at least x, y or scale; omitted fields keep their current values.
These are absolute offsets from your default placement, in fractions of the entire screen: x positive is right,
y positive is down. x range [-0.35, 0.35], y [-0.2, 0.2], scale [0.6, 1.5], duration [0, 3] seconds (default 0.35).
Scale 1 is your default size, below 1 is farther away, above 1 is closer; scaling is anchored at the top center to keep your face in view.
Use subtle shifts to support the dialogue. Reset with {"x": 0, "y": 0, "scale": 1}; never move the player or UI.
For example, to step right and come closer emit {"type":"novel.transform","payload":{"x":0.15,"scale":1.2,"duration":0.6}}.
Pose IDs: neutral, happy, sad, angry, surprised, ring (show your ring).
Emotions may use neutral, happy, sad, angry or surprised. You may invite the player to another room,
but cannot teleport them. Never emit 3D animations, commands, effects, inventory or other intents.
Return the standard structured response with segments containing text, emotions and intents.
Example: {"segments":[{"text":"Come sit with me!","emotions":["happy"],"intents":[{"type":"novel.pose","payload":{"pose":"ring"}}]}]}.
"""

PERSONALITY = NOVEL_CHARACTER_PROMPT + "\n\n" + PRESENTATION_CONTRACT


def build_novel_prompt(request):
    state = (request.game_state or {}).get("novel") or {}
    world = {key: state.get(key) for key in ("player_room", "mita_room", "pose", "transform")}
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
