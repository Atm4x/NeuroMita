"""Normalize legacy Unity dialogue rosters before they reach an LLM.

The old Unity roster marked its *own recipient* with "(you)". When that
snapshot is later replayed to a different Mita, it asserts a false identity.
Do not edit persisted history: normalize the prompt copy only.
"""
from __future__ import annotations

import re
from typing import Any

_ROSTER_START = re.compile(
    r"\[DIALOGUE\]\s*You are in dialogue with several", re.IGNORECASE
)
_ROSTER_ENTRY = re.compile(
    r"^(?P<indent>[ \t]*)(?P<id>[A-Za-z][A-Za-z0-9_-]*) "
    r"\((?P<kind>Mita|cartridge|system)\)", re.IGNORECASE
)


# Unity Runtime Events can compact a whole roster into a *single* bullet
# containing the event payload after [DIALOGUE_UPDATE]. Only rewrite the
# roster portion, never the quoted speaker text following that delimiter.
_INLINE_ROSTER_ENTRY = re.compile(
    r"(?P<label>\b[A-Za-z][A-Za-z0-9_-]*\s+\((?:Mita|cartridge|system)\))"
    r"(?:,\s*its game object\s+[^)\r\n]*\))?(?:\(you\))?",
    re.IGNORECASE,
)


def neutralize_legacy_dialogue_roster(text: str) -> str:
    """Strip relative identity and Unity object names from legacy roster lines.

    Only lines in a known [DIALOGUE] roster are changed. Speech, quotations,
    other uses of "(you)", and event payloads remain intact.
    """
    if not isinstance(text, str) or "[DIALOGUE]" not in text or "(you)" not in text:
        return text

    inside_roster = False
    result: list[str] = []
    for line in text.splitlines(keepends=True):
        # Some older [Current UnityEvent] entries embed JSON descriptions with
        # literal "\\n" separators instead of actual newlines. Decode only for
        # parsing the roster, then re-escape so the original JSON stays valid.
        if _ROSTER_START.search(line) and "\\n" in line:
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            body = line[:-len(newline)] if newline else line
            decoded = body.replace("\\n", "\n")
            cleaned = neutralize_legacy_dialogue_roster(decoded)
            result.append(cleaned.replace("\n", "\\n") + newline)
            inside_roster = False
            continue

        if _ROSTER_START.search(line):
            inside_roster = True
            # Some Unity events flatten "[DIALOGUE] ... Player Kind
            # (Mita)(you) ..." into a single line, followed by speech.
            if "speakers:" in line and "Player " in line:
                roster, delimiter, speech = line.partition("[DIALOGUE_UPDATE]")
                roster = _INLINE_ROSTER_ENTRY.sub(
                    lambda match: match.group("label"), roster
                )
                line = roster + delimiter + speech
            result.append(line)
            continue

        if inside_roster:
            match = _ROSTER_ENTRY.match(line)
            if match:
                newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                result.append(
                    f"{match.group('indent')}{match.group('id')} "
                    f"({match.group('kind')}){newline}"
                )
                continue
            if line.strip() == "Player":
                result.append(line)
                continue
            inside_roster = False

        result.append(line)
    return "".join(result)


def neutralize_dialogue_roster_content(content: Any) -> Any:
    """Copy only changed multimodal text chunks; leave images and DB values alone."""
    if isinstance(content, str):
        return neutralize_legacy_dialogue_roster(content)
    if not isinstance(content, list):
        return content

    result = None
    for index, chunk in enumerate(content):
        if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
            continue
        new_text = neutralize_legacy_dialogue_roster(chunk["text"])
        if new_text != chunk["text"]:
            if result is None:
                result = list(content)
            result[index] = {**chunk, "text": new_text}
    return content if result is None else result


def neutralize_dialogue_roster_message(message: dict) -> dict:
    """Return a prompt-only copy when a legacy roster is found."""
    if not isinstance(message, dict):
        return message
    content = message.get("content")
    cleaned = neutralize_dialogue_roster_content(content)
    return message if cleaned is content or cleaned == content else {**message, "content": cleaned}
