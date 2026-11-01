from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_TYPES = {"player.speed", "mita.calm", "animation.unlock"}


@dataclass(frozen=True)
class CartridgeDefinition:
    id: str
    character_id: str
    title: str
    prompt: str
    history_messages: int
    context_characters: int


def _number(value: Any, minimum: float, maximum: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and minimum <= value <= maximum


def parse_catalog(payload: Any) -> tuple[CartridgeDefinition, ...]:
    if not isinstance(payload, dict) or payload.get("version") != PROTOCOL_VERSION:
        raise ValueError("Unsupported cartridge catalog version")
    rows = payload.get("cartridges")
    if not isinstance(rows, list) or len(rows) > 128:
        raise ValueError("Invalid cartridge catalog size")
    ids, characters, effects, items = set(), set(), set(), set()
    definitions = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid cartridge definition")
        cid = row.get("id")
        if not isinstance(cid, str) or not _ID.fullmatch(cid) or cid in ids:
            raise ValueError("Invalid or duplicate cartridge id")
        ids.add(cid)
        legacy = row.get("legacyCharacter")
        if legacy not in (None, "", "Cart_portal", "Cart_divan"):
            raise ValueError("Unsupported legacy cartridge id")
        character_id = legacy or "Cartridge_" + cid
        if character_id in characters:
            raise ValueError("Duplicate cartridge character")
        characters.add(character_id)
        for key in ("title", "record", "prompt"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError("Missing cartridge " + key)
        if len(row["prompt"]) > 16000:
            raise ValueError("Cartridge prompt is too long")
        history, context = row.get("historyMessages", 12), row.get("contextCharacters", 12000)
        if type(history) is not int or not 2 <= history <= 40 or type(context) is not int or not 1000 <= context <= 32000 or len(row["prompt"]) + 1000 > context:
            raise ValueError("Invalid cartridge context limits")
        names = row.get("itemNames", [])
        if not isinstance(names, list):
            raise ValueError("Invalid item mapping")
        for name in names:
            if not isinstance(name, str) or not name.strip() or name in items:
                raise ValueError("Ambiguous item mapping")
            items.add(name)
        rows_effects = row.get("effects", [])
        if not isinstance(rows_effects, list):
            raise ValueError("Invalid effects")
        for effect in rows_effects:
            if not isinstance(effect, dict):
                raise ValueError("Invalid effect")
            eid, kind = effect.get("id"), effect.get("type")
            if not isinstance(eid, str) or not _ID.fullmatch(eid) or eid in effects or kind not in _TYPES:
                raise ValueError("Invalid or unsupported effect")
            effects.add(eid)
            if not isinstance(effect.get("title"), str) or not effect["title"].strip():
                raise ValueError("Missing effect title")
            if type(effect.get("slotCost", 1)) is not int or not 1 <= effect.get("slotCost", 1) <= 3:
                raise ValueError("Invalid effect slot cost")
            magnitude, target = effect.get("magnitude", 1), effect.get("target", "player")
            if not _number(effect.get("radius", 8), 1, 30) or not _number(effect.get("durationSeconds", 0), 0, 86400):
                raise ValueError("Invalid effect timing or radius")
            permanent = effect.get("permanent", False)
            if type(permanent) is not bool:
                raise ValueError("Invalid effect lifetime")
            if kind == "player.speed" and (permanent or target != "player" or not _number(magnitude, 0.5, 2)):
                raise ValueError("Invalid movement effect")
            if kind == "mita.calm" and (permanent or target not in ("nearby", "selected") or not _number(magnitude, 0.1, 5)):
                raise ValueError("Invalid calm effect")
            if kind == "animation.unlock" and (not permanent or target != "player" or not isinstance(effect.get("animation"), str) or not effect["animation"].strip()):
                raise ValueError("Invalid animation effect")
        definitions.append(CartridgeDefinition(cid, character_id, row["title"], row["prompt"], history, context))
    return tuple(definitions)


def validate_session(payload: Any, character_id: str) -> tuple[CartridgeDefinition, ...]:
    if not isinstance(payload, dict) or payload.get("version") != PROTOCOL_VERSION:
        raise ValueError("Unsupported cartridge protocol")
    definitions = parse_catalog(payload.get("catalog"))
    selected = next((item for item in definitions if item.id == payload.get("id")), None)
    if selected is None or selected.character_id != character_id:
        raise ValueError("Cartridge identity does not match the inserted item")
    if payload.get("ai_enabled") is not True or not isinstance(payload.get("session"), str) or not 1 <= len(payload["session"]) <= 128:
        raise ValueError("Cartridge AI is disabled or session is missing")
    return definitions
