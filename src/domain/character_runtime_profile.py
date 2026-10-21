"""Character-specific capabilities consumed by the shared generation pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterRuntimeProfile:
    rag_enabled: bool = True
    core_memory_enabled: bool = True
    tools_enabled: bool = True
    background_memory_enabled: bool = True
    requires_structured_output: bool = False
    scene_context_key: str | None = None
    scene_context_fields: tuple[str, ...] = ()
    history_message_limit: int | None = None


DEFAULT_RUNTIME_PROFILE = CharacterRuntimeProfile()


def runtime_profile_for(character) -> CharacterRuntimeProfile:
    profile = getattr(character, "runtime_profile", None)
    return profile if isinstance(profile, CharacterRuntimeProfile) else DEFAULT_RUNTIME_PROFILE
