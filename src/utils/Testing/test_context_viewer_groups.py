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
            {"role": "event", "content": "[Event] Player crouched nearby."},
            {"role": "user", "content": "[RUNTIME EVENT] [Past session event: UnityEvent] Player moved."},
            {"role": "event", "content": "[Event: GAME_STARTED] Game started."},
            {"role": "event", "content": "[Unity Runtime Events] These events occurred after the previous dispatch."},
        ])
        self.assertTrue(viewer._is_event_row(0))
        self.assertTrue(viewer._is_event_row(1))
        self.assertTrue(viewer._is_event_row(2))
        # Блок рантайм-событий текущего хода остаётся отдельной строкой.
        self.assertFalse(viewer._is_event_row(3))


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
        viewer._first_history_idx = 1
        self.assertEqual(viewer._group_key(0), "prompt")

    def test_unknown_section_before_history_is_prompt(self):
        # Новый блок промпта без записи в таблице не должен поднимать
        # «Активный контекст» выше истории.
        viewer = _viewer([
            {"role": "system", "content": "[Brand New Block]\ntext"},
            {"role": "assistant", "content": "hi"},
        ])
        viewer._est_by_index = {
            0: {"tokens": 40, "images": 0, "section": "brand new block"},
            1: {"tokens": 10, "images": 0, "section": "history"},
        }
        viewer._first_history_idx = 1
        self.assertEqual(viewer._group_key(0), "prompt")
        self.assertEqual(viewer._group_key(1), "history")



class LoadedSkillsViewerTests(unittest.TestCase):
    def test_loaded_skill_names_are_visible_in_history(self):
        msg = {
            "role": "system",
            "content": (
                "[LOADED SKILLS]\n"
                "Instructions for the current scene.\n"
                "## Easel drawing (easel)\nDraw with varied strokes.\n"
                "## Tea making (tea)\nPrepare a cup.\n"
                "[/LOADED SKILLS]"
            ),
        }
        self.assertEqual(
            classify_message_section(msg, is_last_user=False, seen_dialogue=True),
            "loaded skills",
        )
        viewer = _viewer([msg])
        viewer._est_by_index = {0: {"tokens": 220, "section": "loaded skills"}}
        self.assertEqual(viewer._group_key(0), "history")
        label = viewer._classify_message_label(msg, "system", 1, 0)
        self.assertIn("Easel drawing (easel)", label)
        self.assertIn("Tea making (tea)", label)
        self.assertEqual(viewer._message_icon_name(msg, "system"), "fa6s.puzzle-piece")

    def test_old_dump_with_missing_or_wrong_token_metadata_still_shows_skills(self):
        msg = {"role": "system", "content": "[LOADED SKILLS]\n## Drawing (drawing)\n..."}
        viewer = _viewer([msg])
        viewer._est_by_index = {0: {"tokens": 100, "section": "history"}}
        self.assertEqual(viewer._group_key(0), "history")
        viewer._est_by_index = {}
        self.assertEqual(viewer._group_key(0), "history")

    def test_eager_skills_remain_part_of_the_static_prompt(self):
        msg = {"role": "system", "content": "[LOADED SKILLS]\\n## Drawing (drawing)\\nText"}
        section = classify_message_section(msg, is_last_user=False, seen_dialogue=False)
        self.assertEqual(section, "character prompts")
        viewer = _viewer([msg])
        viewer._est_by_index = {0: {"tokens": 100, "section": section}}
        self.assertEqual(viewer._group_key(0), "prompt")

    def test_native_tool_reply_is_history(self):
        msg = {"role": "tool", "content": "[LOADED SKILLS]\\n[skill: Drawing]\\nText"}
        section = classify_message_section(msg, is_last_user=False, seen_dialogue=True)
        self.assertEqual(section, "loaded skills")
        viewer = _viewer([{"role": "assistant", "content": "loading"}, msg])
        viewer._first_history_idx = 0
        viewer._est_by_index = {
            0: {"tokens": 10, "section": "history"},
            1: {"tokens": 100, "section": section},
        }
        self.assertEqual(viewer._group_key(1), "history")


if __name__ == "__main__":
    unittest.main()
