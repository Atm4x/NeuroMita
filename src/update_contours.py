from __future__ import annotations

import os

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


RELEASE_CONTOUR = "release"
TEST_CONTOUR = "test"
VALID_UPDATE_CONTOURS = (RELEASE_CONTOUR, TEST_CONTOUR)

UPDATE_CONTOUR_KEY = "UPDATE_CONTOUR"
UPDATE_CONTOUR_SCHEMA_KEY = "UPDATE_CONTOUR_SCHEMA_VERSION"
UPDATE_CONTOUR_SCHEMA_VERSION = 1
INSTALLED_SOURCES_KEY = "UPDATE_INSTALLED_SOURCES"
TESTER_CODE_KEY = "TESTER_CODE"
TESTER_CODES_KEY = "TESTER_CODES"

# These repositories are part of the delivery architecture, not user settings.
# A release build must never be redirected to an arbitrary GitHub repository.
RELEASE_REPOSITORY = "VinerX/NeuroMita"
TEST_REPOSITORY = "Atm4x/NeuroMita"


@dataclass(frozen=True)
class UpdateSource:
    contour: str
    repo: str
    display_name_ru: str
    display_name_en: str
    requires_tester_code: bool = False

    @property
    def is_test(self) -> bool:
        return self.contour == TEST_CONTOUR


def _settings_get(settings: Any, key: str, default=None):
    if settings is None:
        return default
    getter = getattr(settings, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except TypeError:
            try:
                return getter(key)
            except Exception:
                return default
    if isinstance(settings, dict):
        return settings.get(key, default)
    return default


def normalize_update_contour(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in VALID_UPDATE_CONTOURS:
        return text
    return RELEASE_CONTOUR


def default_update_contour() -> str:
    # Test builds opt in explicitly through their launcher environment.
    raw = str(os.environ.get("NEUROMITA_TEST_CONTOUR") or "").strip().casefold()
    return TEST_CONTOUR if raw in {"1", "true", "yes", "on"} else RELEASE_CONTOUR


def migrate_update_contour_settings(settings: Any = None) -> tuple[dict[str, Any], bool]:
    """Persist a valid default without changing an existing contour choice."""
    payload = dict(settings) if isinstance(settings, dict) else {}
    try:
        schema_version = int(payload.get(UPDATE_CONTOUR_SCHEMA_KEY) or 0)
    except (TypeError, ValueError):
        schema_version = 0
    if schema_version >= UPDATE_CONTOUR_SCHEMA_VERSION:
        return payload, False

    saved_contour = str(payload.get(UPDATE_CONTOUR_KEY) or "").strip().lower()
    if saved_contour not in VALID_UPDATE_CONTOURS:
        # The environment is a provisioning default for fresh installations;
        # it must never override an existing tester or release user choice.
        payload[UPDATE_CONTOUR_KEY] = default_update_contour()
    payload[UPDATE_CONTOUR_SCHEMA_KEY] = UPDATE_CONTOUR_SCHEMA_VERSION
    return payload, True

def _source_map() -> dict[str, UpdateSource]:
    return {
        RELEASE_CONTOUR: UpdateSource(
            contour=RELEASE_CONTOUR,
            repo=RELEASE_REPOSITORY,
            display_name_ru="Релизный",
            display_name_en="Release",
            requires_tester_code=False,
        ),
        TEST_CONTOUR: UpdateSource(
            contour=TEST_CONTOUR,
            repo=TEST_REPOSITORY,
            display_name_ru="Тестовый",
            display_name_en="Test",
            requires_tester_code=True,
        ),
    }


def get_selected_update_contour(settings: Any = None, contour: str | None = None) -> str:
    if contour is not None:
        return normalize_update_contour(contour)
    saved_contour = str(_settings_get(settings, UPDATE_CONTOUR_KEY, "") or "").strip().lower()
    if saved_contour in VALID_UPDATE_CONTOURS:
        return saved_contour
    return default_update_contour()


def resolve_update_source(settings: Any = None, contour: str | None = None) -> UpdateSource:
    selected = get_selected_update_contour(settings=settings, contour=contour)
    return _source_map()[selected]


def update_channel_for_source(source: UpdateSource) -> str:
    """Return the only allowed GitHub release channel for a contour.

    Production must never consume prereleases. Test releases are prereleases so
    they are visible only to clients deliberately placed in the test contour.
    """
    return "beta" if source.is_test else "stable"


def get_test_contour_badge(settings: Any = None, contour: str | None = None, *, lang: str = "ru") -> str:
    source = resolve_update_source(settings=settings, contour=contour)
    if not source.is_test:
        return ""
    return "Тестовый контур" if str(lang).lower() != "en" else "Test contour"


def normalize_tester_codes(raw: Any) -> list[str]:
    if raw is None:
        return []

    values: list[str] = []
    if isinstance(raw, str):
        chunks = raw.replace(";", "\n").replace(",", "\n").splitlines()
        values.extend(chunks)
    elif isinstance(raw, (list, tuple, set)):
        for item in raw:
            values.extend(normalize_tester_codes(item))
    else:
        values.append(str(raw))

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def get_tester_codes(settings: Any = None, explicit: Any = None) -> list[str]:
    codes: list[str] = []
    for raw in (
        explicit,
        _settings_get(settings, TESTER_CODES_KEY, None),
        _settings_get(settings, TESTER_CODE_KEY, None),
        os.environ.get(TESTER_CODES_KEY),
        os.environ.get(TESTER_CODE_KEY),
    ):
        for code in normalize_tester_codes(raw):
            if code not in codes:
                codes.append(code)
    return codes


def build_tester_code_settings(explicit: Any, existing: Any = None, *, limit: int = 5) -> dict[str, Any]:
    merged = get_tester_codes(existing, explicit=explicit)
    if limit > 0:
        merged = merged[:limit]
    primary = merged[0] if merged else ""
    return {
        TESTER_CODES_KEY: merged,
        TESTER_CODE_KEY: primary,
    }


def get_installed_sources(settings: Any = None) -> dict[str, dict[str, Any]]:
    raw = _settings_get(settings, INSTALLED_SOURCES_KEY, {})
    if isinstance(raw, dict):
        return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
    return {}


def build_installed_source_record(
    component: str,
    source: UpdateSource,
    *,
    tag: str,
    asset_name: str = "",
    published_at: str = "",
    release_name: str = "",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "component": str(component or "").strip().lower(),
        "contour": source.contour,
        "repo": source.repo,
        "tag": str(tag or "").strip(),
        "asset_name": str(asset_name or "").strip(),
        "published_at": str(published_at or "").strip(),
        "release_name": str(release_name or "").strip(),
        "installed_at": now,
    }


def get_installed_source(settings: Any, component: str) -> dict[str, Any] | None:
    key = str(component or "").strip().lower()
    source_map = get_installed_sources(settings)
    found = source_map.get(key)
    if isinstance(found, dict) and str(found.get("repo") or "").strip():
        return dict(found)

    # Old installations did not record their source. Treating them as a test
    # install causes an unnecessary (and potentially downgrading) migration.
    return None


def is_source_mismatch(selected: UpdateSource, installed: dict[str, Any] | None) -> bool:
    if not installed:
        return False
    installed_repo = str(installed.get("repo") or "").strip()
    installed_contour = normalize_update_contour(installed.get("contour"))
    if not installed_repo:
        return False
    return installed_repo != selected.repo or installed_contour != selected.contour
