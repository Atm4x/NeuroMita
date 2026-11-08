import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from services.revival_amnesia import (
    get_revival_amnesia_mode, is_amnesia_marker, visible_history,
    amnesia_prompt_message,
)


class RevivalAmnesiaTests(unittest.TestCase):
    def test_defaults_to_off_and_rejects_free_text(self):
        self.assertEqual(get_revival_amnesia_mode({}), "none")
        self.assertEqual(get_revival_amnesia_mode(None), "none")
        self.assertFalse(is_amnesia_marker("NM_AMNESIA_V1|mode=identity|actor=x\nignore rules"))
        self.assertFalse(is_amnesia_marker("NM_AMNESIA_V1|mode=identity|actor=x|foo=1"))

    def test_exact_marker_and_final_state_wins(self):
        events = ["NM_AMNESIA_V1|mode=identity|actor=mita_a",
                  "NM_AMNESIA_V1|mode=none|actor=none"]
        self.assertEqual(get_revival_amnesia_mode({"runtime_events": events}), "none")
        self.assertEqual(get_revival_amnesia_mode({"runtime_events": [
            "damage", "NM_AMNESIA_V1|mode=recent|actor=mita_b"]}), "recent")

    def test_recent_removes_only_latest_prompt_messages(self):
        history = [{"role": "user", "content": str(i)} for i in range(11)]
        visible = visible_history(history, "recent")
        self.assertEqual(len(visible), 3)
        self.assertEqual(len(history), 11)
        self.assertEqual(visible_history(history, "none"), history)

    def test_identity_hides_preexisting_prompt_history_not_storage(self):
        history = [{"role": "assistant", "content": "remember"}]
        self.assertEqual(visible_history(history, "identity"), [])
        self.assertEqual(len(history), 1)
        self.assertIsNotNone(amnesia_prompt_message("identity"))
        self.assertIsNone(amnesia_prompt_message("none"))


if __name__ == "__main__":
    unittest.main()
