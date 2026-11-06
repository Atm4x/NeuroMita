"""Группировка сообщений в дереве просмотрщика контекста."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from ui.dialogs.context_viewer_dialog import ContextViewerDialog
from utils.context_token_stats import classify_message_section


def _viewer(messages: list[dict]) -> ContextViewerDialog:
    viewer = ContextViewerDialog.__new__(ContextViewerDialog)
    viewer._message_meta = {}
    viewer._messages = messages
    viewer._data = {"character_name": "Crazy Mita"}
    return viewer


class EventRowTests(unittest.TestCase):
    def test_past_session_events_are_recognised(self):
        viewer = _viewer([
            {"role": "event", "content": "[Past session event: UnityEvent] Player crouched nearby."},
            {"role": "user", "content": "[RUNTIME EVENT] [Past session event: UnityEvent] Player moved."},
            {"role": "event", "content": "[Unity Runtime Events] These events occurred after the previous dispatch."},
        ])
        self.assertTrue(viewer._is_event_row(0))
        self.assertTrue(viewer._is_event_row(1))
        # Блок рантайм-событий текущего хода остаётся отдельной строкой.
        self.assertFalse(viewer._is_event_row(2))


class StageSectionTests(unittest.TestCase):
    def test_stage_blocks_are_part_of_the_prompt(self):
        header = classify_message_section(
            {"role": "system", "content": "[Current Stage]\nstage: introduction\nmode: automatic"},
            is_last_user=False,
            seen_dialogue=True,
        )
        block = classify_message_section(
            {"role": "system", "content": "# STAGE: introduction — Знакомство\nТвоё первое впечатление."},
            is_last_user=False,
            seen_dialogue=True,
        )
        self.assertEqual(header, "stage")
        self.assertEqual(block, "stage")


class SkillCatalogSectionTests(unittest.TestCase):
    """[SKILLS] — статика промпта: она не должна поднимать «Активный контекст»."""

    def test_skills_catalog_stays_with_the_prompt(self):
        section = classify_message_section(
            {"role": "system", "content": "[SKILLS]\nSkills you can load on demand: tv"},
            is_last_user=False,
            seen_dialogue=False,
        )
        self.assertEqual(section, "skills catalog")

        viewer = _viewer([{"role": "system", "content": "[SKILLS]\ntv"}])
        viewer._est_by_index = {0: {"tokens": 120, "images": 0, "section": section}}
        self.assertEqual(viewer._group_key(0), "prompt")


if __name__ == "__main__":
    unittest.main()
