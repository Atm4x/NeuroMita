from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from update_contours import (  # noqa: E402
    RELEASE_CONTOUR,
    TEST_CONTOUR,
    build_tester_code_settings,
    get_installed_source,
    get_selected_update_contour,
    get_tester_codes,
    is_source_mismatch,
    migrate_update_contour_settings,
    resolve_update_source,
    update_channel_for_source,
)


def test_default_selected_contour_is_release():
    assert get_selected_update_contour({}) == RELEASE_CONTOUR


def test_resolve_update_source_switches_repo_by_contour():
    release_source = resolve_update_source({"UPDATE_CONTOUR": RELEASE_CONTOUR})
    test_source = resolve_update_source({"UPDATE_CONTOUR": TEST_CONTOUR})

    assert release_source.contour == RELEASE_CONTOUR
    assert test_source.contour == TEST_CONTOUR
    assert release_source.repo != test_source.repo
    assert release_source.requires_tester_code is False
    assert test_source.requires_tester_code is True


def test_build_tester_code_settings_keeps_recent_unique_codes():
    payload = build_tester_code_settings(
        "new-code",
        existing={"TESTER_CODE": "old-code", "TESTER_CODES": ["old-code", "older-code"]},
    )

    assert payload["TESTER_CODE"] == "new-code"
    assert payload["TESTER_CODES"] == ["new-code", "old-code", "older-code"]


def test_get_tester_codes_merges_single_and_history():
    codes = get_tester_codes({"TESTER_CODE": "single", "TESTER_CODES": ["history", "single"]})

    assert codes == ["history", "single"]


def test_get_installed_source_is_unknown_without_metadata():
    assert get_installed_source({}, "python") is None


def test_existing_test_contour_survives_migration_without_environment(monkeypatch):
    monkeypatch.delenv("NEUROMITA_TEST_CONTOUR", raising=False)

    payload, changed = migrate_update_contour_settings({"UPDATE_CONTOUR": TEST_CONTOUR})

    assert changed is True
    assert payload["UPDATE_CONTOUR"] == TEST_CONTOUR
    assert payload["UPDATE_CONTOUR_SCHEMA_VERSION"] == 1


def test_existing_release_contour_survives_test_environment(monkeypatch):
    monkeypatch.setenv("NEUROMITA_TEST_CONTOUR", "1")

    payload, changed = migrate_update_contour_settings({"UPDATE_CONTOUR": RELEASE_CONTOUR})

    assert changed is True
    assert payload["UPDATE_CONTOUR"] == RELEASE_CONTOUR


def test_fresh_settings_use_release_without_test_environment(monkeypatch):
    monkeypatch.delenv("NEUROMITA_TEST_CONTOUR", raising=False)

    payload, changed = migrate_update_contour_settings({})

    assert changed is True
    assert payload["UPDATE_CONTOUR"] == RELEASE_CONTOUR


def test_fresh_settings_use_test_with_explicit_test_environment(monkeypatch):
    monkeypatch.setenv("NEUROMITA_TEST_CONTOUR", "1")

    payload, changed = migrate_update_contour_settings({})

    assert changed is True
    assert payload["UPDATE_CONTOUR"] == TEST_CONTOUR


def test_invalid_saved_contour_uses_provisioning_default(monkeypatch):
    monkeypatch.setenv("NEUROMITA_TEST_CONTOUR", "1")

    payload, _changed = migrate_update_contour_settings({"UPDATE_CONTOUR": "invalid"})

    assert payload["UPDATE_CONTOUR"] == TEST_CONTOUR

def test_unknown_source_is_not_a_mismatch():
    release_source = resolve_update_source({"UPDATE_CONTOUR": RELEASE_CONTOUR})

    assert is_source_mismatch(release_source, None) is False

def test_same_tag_from_other_repo_is_source_mismatch():
    release_source = resolve_update_source({"UPDATE_CONTOUR": RELEASE_CONTOUR})
    installed = {
        "component": "python",
        "contour": TEST_CONTOUR,
        "repo": resolve_update_source({"UPDATE_CONTOUR": TEST_CONTOUR}).repo,
        "tag": "v1.2.3",
    }

    assert is_source_mismatch(release_source, installed) is True


def test_contour_controls_the_only_allowed_release_channel():
    assert update_channel_for_source(resolve_update_source({"UPDATE_CONTOUR": RELEASE_CONTOUR})) == "stable"
    assert update_channel_for_source(resolve_update_source({"UPDATE_CONTOUR": TEST_CONTOUR})) == "beta"


def test_invalid_contour_falls_back_to_release():
    assert get_selected_update_contour({"UPDATE_CONTOUR": "unknown"}) == RELEASE_CONTOUR


def test_test_contour_requires_explicit_launcher_opt_in(monkeypatch):
    monkeypatch.setenv("NEUROMITA_TEST_CONTOUR", "1")

    assert get_selected_update_contour({}) == TEST_CONTOUR
