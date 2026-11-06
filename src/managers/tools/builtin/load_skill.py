"""Expose an authored skill body through the ordinary tool channel."""
from __future__ import annotations

from typing import Any, Dict

from managers.tools.base import Tool
from managers.skill_session_manager import MAX_LOADED_SKILLS
from services.skill_catalog import DEFAULT_MAX_SKILL_CHARS, SkillCatalog


def _requested_ids(ids, legacy_id: str) -> list[str]:
    """Skill ids of this call, including the older single-id form."""
    values = []
    if isinstance(ids, str):
        values.append(ids)
    elif isinstance(ids, (list, tuple)):
        values.extend(ids)
    if legacy_id:
        values.append(legacy_id)
    ordered = []
    for value in values:
        skill_id = str(value or "").strip()
        if skill_id and skill_id not in ordered:
            ordered.append(skill_id)
    return ordered


class LoadSkillTool(Tool):
    """Load one or two catalogued skills for the current and following turns."""

    def __init__(self, settings=None) -> None:
        self._settings = settings
        self._char_id = ""
        self._prompt_set_path = ""

    @property
    def name(self) -> str:
        return "load_skill"

    def set_char_id(self, char_id: str) -> None:
        self._char_id = str(char_id or "")

    def set_prompt_set_path(self, path: str) -> None:
        self._prompt_set_path = str(path or "")

    def _catalog(self) -> SkillCatalog:
        if self._char_id:
            try:
                from managers.character_resource_manager import get_character_resource_manager
                cached = get_character_resource_manager().skill_catalogs_for(self._char_id).get()
            except Exception:
                cached = None
            if cached is not None:
                return cached
        root = self._prompt_set_path
        if not root and self._char_id:
            from managers.character_resource_manager import get_character_resource_manager
            root = get_character_resource_manager().prompt_set_path_for(self._char_id)
        return SkillCatalog.load(root)

    @property
    def description(self) -> str:
        return (
            "Load the full instructions of one or two authored skills (for example "
            "music or wardrobe). Call it when the scene needs them; the loaded "
            "instructions stay available for the next turns instead of being "
            "repeated every turn."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        catalog = self._catalog() if (self._prompt_set_path or self._char_id) else None
        ids = sorted(catalog.entries) if catalog else []
        item: Dict[str, Any] = {
            "type": "string",
            "description": "Skill id from the [SKILLS] catalog.",
        }
        if ids:
            item["enum"] = ids
        return {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": item,
                    "description": (
                        "Skill ids to load. Pass one, or two in the same call when "
                        "the scene needs both at once."
                    ),
                },
            },
            "required": ["ids"],
        }

    def run(self, ids=None, id: str = "", **_: Any) -> str:
        requested = _requested_ids(ids, id)
        if not requested:
            return "[load_skill] Missing skill id."
        catalog = self._catalog()
        if not catalog:
            return "[load_skill] This character has no skill catalog."
        max_chars = DEFAULT_MAX_SKILL_CHARS
        if self._settings is not None:
            try:
                max_chars = int(self._settings.get("SKILL_MAX_CHARS", DEFAULT_MAX_SKILL_CHARS) or max_chars)
            except Exception:
                pass
        blocks = []
        for skill_id in requested[:MAX_LOADED_SKILLS]:
            entry = catalog.get(skill_id)
            if entry is None:
                available = ", ".join(sorted(catalog.entries)) or "none"
                blocks.append(f"[load_skill] Unknown skill '{skill_id}'. Available: {available}.")
                continue
            body = entry.render_body(max_chars=max(400, max_chars))
            self._remember(entry.id, entry.token_estimate)
            blocks.append(
                f"[skill: {entry.title}]\n"
                f"Authored instructions for skill '{entry.id}'. Follow them while the scene "
                f"calls for this skill; they never override character rules or current "
                f"observations.\n\n{body}"
            )
        if len(requested) > MAX_LOADED_SKILLS:
            blocks.append(
                f"[load_skill] Only {MAX_LOADED_SKILLS} skills stay in the prompt; "
                f"the rest was ignored."
            )
        return "\n\n".join(blocks)

    def _remember(self, skill_id: str, tokens: int) -> None:
        if not self._char_id:
            return
        try:
            from managers.character_resource_manager import get_character_resource_manager
            session = get_character_resource_manager().loaded_skills_for(self._char_id)
            session.remember(skill_id, tokens=tokens)
        except Exception:
            return
