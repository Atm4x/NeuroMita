"""Validated, prompt-facing catalog of on-demand character skills.

A skill is authored text kept in the character's prompt set.  The catalog
only describes it; loading the body is an explicit, bounded action so the
main prompt does not have to carry every skill all the time.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

CATALOG_DIRNAME = "Skills"
CATALOG_FILENAME = "catalog.json"

DEFAULT_MAX_SKILL_CHARS = 4000
DEFAULT_CATALOG_BLOCK_CHARS = 1200
MAX_SKILL_ID_CHARS = 40

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_ALLOWED_SUFFIXES = {".md", ".txt"}


class SkillCatalogError(ValueError):
    """The catalog on disk cannot be trusted as written."""


@dataclass(frozen=True)
class SkillEntry:
    id: str
    title: str
    description: str
    content: str
    content_hash: str
    token_estimate: int
    capabilities: tuple[str, ...] = ()

    def render_body(self, *, max_chars: int = DEFAULT_MAX_SKILL_CHARS) -> str:
        if len(self.content) <= max_chars:
            return self.content
        return self.content[: max(1, max_chars - 1)].rstrip() + "\u2026"


@dataclass
class SkillCatalog:
    root: Path
    entries: dict[str, SkillEntry] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, prompt_set_path: str | Path) -> "SkillCatalog":
        root = Path(prompt_set_path or "") / CATALOG_DIRNAME
        catalog = cls(root=root)
        manifest_path = root / CATALOG_FILENAME
        if not manifest_path.is_file():
            return catalog
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            catalog.issues.append(f"unreadable catalog: {exc}")
            return catalog
        raw_skills = payload.get("skills") if isinstance(payload, dict) else None
        if not isinstance(raw_skills, list):
            catalog.issues.append("catalog has no skills list")
            return catalog
        for index, raw in enumerate(raw_skills):
            try:
                entry = catalog._read_entry(raw, index)
            except SkillCatalogError as exc:
                catalog.issues.append(str(exc))
                continue
            if entry.id in catalog.entries:
                catalog.issues.append(f"duplicate skill id: {entry.id}")
                continue
            catalog.entries[entry.id] = entry
        return catalog

    def _read_entry(self, raw: object, index: int) -> SkillEntry:
        if not isinstance(raw, dict):
            raise SkillCatalogError(f"skill #{index} is not an object")
        skill_id = str(raw.get("id") or "").strip()
        if not _ID_RE.match(skill_id) or len(skill_id) > MAX_SKILL_ID_CHARS:
            raise SkillCatalogError(f"skill #{index} has an invalid id: {skill_id!r}")
        relative = str(raw.get("file") or "").strip()
        if not relative:
            raise SkillCatalogError(f"skill {skill_id} has no file")
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise SkillCatalogError(f"skill {skill_id} escapes the catalog directory") from exc
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise SkillCatalogError(f"skill {skill_id} must be .md or .txt")
        if not path.is_file():
            raise SkillCatalogError(f"skill {skill_id} file is missing: {relative}")
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SkillCatalogError(f"skill {skill_id} cannot be read: {exc}") from exc
        if not content:
            raise SkillCatalogError(f"skill {skill_id} is empty")
        capabilities = raw.get("capabilities") or []
        if not isinstance(capabilities, list):
            capabilities = []
        return SkillEntry(
            id=skill_id,
            title=str(raw.get("title") or skill_id).strip(),
            description=" ".join(str(raw.get("description") or "").split()),
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            token_estimate=(len(content) + 3) // 4,
            capabilities=tuple(str(item) for item in capabilities if str(item).strip()),
        )

    def get(self, skill_id: str) -> SkillEntry | None:
        return self.entries.get(str(skill_id or "").strip())

    @classmethod
    def from_payload(cls, payload: object) -> "SkillCatalog":
        """Build a catalog from the connected game runtime payload.

        The runtime owns the skill text there, so there are no files to read:
        the same manifest shape is used, with ``body`` instead of ``file``.
        """
        catalog = cls(root=Path(""))
        data = payload
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError as exc:
                catalog.issues.append(f"unreadable runtime catalog: {exc}")
                return catalog
        if isinstance(data, dict):
            data = data.get("skills")
        if not isinstance(data, list):
            catalog.issues.append("runtime catalog has no skills list")
            return catalog
        for index, raw in enumerate(data):
            try:
                entry = catalog._payload_entry(raw, index)
            except SkillCatalogError as exc:
                catalog.issues.append(str(exc))
                continue
            if entry.id in catalog.entries:
                catalog.issues.append(f"duplicate skill id: {entry.id}")
                continue
            catalog.entries[entry.id] = entry
        return catalog

    def _payload_entry(self, raw: object, index: int) -> SkillEntry:
        if not isinstance(raw, dict):
            raise SkillCatalogError(f"skill #{index} is not an object")
        skill_id = str(raw.get("id") or "").strip()
        if not _ID_RE.match(skill_id) or len(skill_id) > MAX_SKILL_ID_CHARS:
            raise SkillCatalogError(f"skill #{index} has an invalid id: {skill_id!r}")
        content = str(raw.get("body") or raw.get("content") or "").strip()
        if not content:
            raise SkillCatalogError(f"skill {skill_id} has no body")
        capabilities = raw.get("capabilities") or []
        if not isinstance(capabilities, list):
            capabilities = []
        return SkillEntry(
            id=skill_id,
            title=str(raw.get("title") or skill_id).strip(),
            description=" ".join(str(raw.get("description") or "").split()),
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            token_estimate=(len(content) + 3) // 4,
            capabilities=tuple(str(item) for item in capabilities if str(item).strip()),
        )

    def available(self, capabilities: Iterable[str] = ()) -> list[SkillEntry]:
        required = {str(item).strip() for item in capabilities if str(item).strip()}
        if not required:
            return list(self.entries.values())
        return [
            entry for entry in self.entries.values()
            if set(entry.capabilities) & required
        ]

    def render_catalog_block(
        self,
        *,
        capabilities: Iterable[str] = (),
        max_chars: int = DEFAULT_CATALOG_BLOCK_CHARS,
    ) -> str:
        entries = self.available(capabilities)
        if not entries:
            return ""
        lines = [
            "[SKILLS]",
            "Skills you can load on demand. To read one, call the load_skill tool "
            "through the top-level tool_call field next to segments, passing its "
            "id or ids (two at once when the scene needs both); [Available Tools] "
            "shows the exact shape. "
            "Load one only when the current scene needs it; the result is placed "
            "in the conversation history, and eventually leaves the context "
            "window like older dialogue. Call load_skill again if needed.",
        ]
        budget = max(200, int(max_chars or DEFAULT_CATALOG_BLOCK_CHARS))
        for entry in entries:
            line = f"- {entry.id}: {entry.title}"
            if entry.description:
                line += f" \u2014 {entry.description}"
            if sum(len(item) + 1 for item in lines) + len(line) > budget:
                lines.append("- ...")
                break
            lines.append(line)
        lines.append("[/SKILLS]")
        return "\n".join(lines)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def render_loaded_block(
        self,
        skill_ids: Iterable[str],
        *,
        max_chars: int = DEFAULT_MAX_SKILL_CHARS * 3,
    ) -> str:
        """Render the bodies of currently retained skills for this turn."""
        selected = []
        for skill_id in skill_ids or ():
            entry = self.get(str(skill_id))
            if entry is None:
                continue
            selected.append(entry)
        if not selected:
            return ""
        budget = max(400, int(max_chars or DEFAULT_MAX_SKILL_CHARS * 3))
        lines = [
            "[LOADED SKILLS]",
            "Instructions for the current scene. They describe how to act and do not "
            "override character rules, current observations or the player's words.",
        ]
        remaining = budget - sum(len(line) + 1 for line in lines)
        for entry in selected:
            header = f"## {entry.title} ({entry.id})"
            body_budget = remaining - len(header) - 2
            if body_budget < 200:
                break
            body = entry.render_body(max_chars=body_budget)
            if not body:
                continue
            block = f"{header}\n{body}"
            lines.append(block)
            remaining -= len(block) + 1
        if len(lines) == 2:
            return ""
        lines.append("[/LOADED SKILLS]")
        return "\n".join(lines)
