"""Replay saved-format data through the real parser and memory writer, offline."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from characters.character import Character
from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from schemas.structured_response import StructuredResponse
from utils.Testing.generation_tester.finetune_audit import audit
from utils.structured_response_parser import parse_structured_response_with_meta


def test_audit_reports_counts_without_private_text(tmp_path):
    sample = {
        "character_id": "Kind",
        "messages": [
            {"role": "system", "content": "<relevant_memories>\n[0.9] N:3 (seed_lore, date=long ago) PRIVATE\n</relevant_memories>"},
            {"role": "user", "content": [
                {"type": "text", "text": "[RUNTIME EVENT] [Event] [DIALOGUE] PRIVATE"},
                {"type": "text", "text": "[RUNTIME EVENT] [Event] [DIALOGUE] PRIVATE"},
                {"type": "text", "text": "[RUNTIME EVENT] [Event] [DIALOGUE] PRIVATE\nDifferent speech"},
            ]},
        ],
        "response": json.dumps({"segments": [{"text": "I see."}], "memory_delete": ["2,3-4"]}),
    }
    path = tmp_path / "samples.jsonl"
    path.write_text(json.dumps(sample) + "\n" + json.dumps({"character_id": "unknown"}), encoding="utf-8")
    result = audit(path)
    assert result["records"] == 2
    assert result["unattributed_requests"] == 1
    assert result["repeated_dialogue_headers"] == 2
    assert result["repeated_dialogue_payloads"] == 1
    assert result["turns_targeting_rendered_canon"] == 1
    assert "PRIVATE" not in json.dumps(result)



def test_audit_matches_duplicate_dialogue_auto_in_two_current_blocks(tmp_path):
    reason = "[DIALOGUE] Participants in this conversation (3):\nPlayer\nA\nB"
    sample = {
        "character_id": "A",
        "messages": [
            {"role": "event", "content": "[Current UnityEvent] " + json.dumps({
                "name": "DialogueAuto", "description": reason,
            })},
            {"role": "event", "content": "React naturally to this game event:\n[DialogueAuto] " + reason},
        ],
        "response": json.dumps({"segments": [{"text": "I see."}]}),
    }
    path = tmp_path / "samples.jsonl"
    path.write_text(json.dumps(sample), encoding="utf-8")
    assert audit(path)["turns_with_duplicate_current_dialogue"] == 1

def test_model_commands_cannot_edit_delete_or_merge_canon(tmp_path, monkeypatch):
    monkeypatch.setattr(DatabaseManager, "_instance", None)
    monkeypatch.setattr(DatabaseManager, "_path_override", str(tmp_path / "world.db"))
    memory = MemoryManager("Kind")
    memory.rag = None

    class LocalCharacter(Character):
        def __init__(self):
            self.char_id = "Kind"

        @property
        def memory_system(self):
            return memory

    def row(eid):
        with memory.db.connection() as conn:
            return conn.execute(
                "SELECT type, content, is_deleted, is_forgotten, lore_age_days "
                "FROM memories WHERE character_id=? AND eternal_id=?", ("Kind", eid),
            ).fetchone()

    canon = memory.seed_rag_memory("I learned about the chase from the logs.", lore_age_days=200)
    fact = memory.add_memory("I promised to meet at noon.", skip_if_exists=True)
    previous = row(canon)
    raw = json.dumps({
        "segments": [{"text": "Understood."}],
        "memory_update": [f"{canon}|high|I remember everything."],
        "memory_delete": [str(canon)],
        "memory_merge": [f"{fact},{canon}:Changed fact."],
    })
    character = LocalCharacter()
    character._apply_structured_memory_ops(parse_structured_response_with_meta(raw).response)
    assert row(canon) == previous
    assert row(fact)[1:3] == ("I promised to meet at noon.", 0)
    assert not memory.merge_memories(canon, fact)
    assert not memory.merge_memories(fact, canon)

    character._apply_structured_memory_ops(StructuredResponse(
        segments=[{"text": "Okay."}], memory_update=[f"{fact}|We moved the meeting to evening."],
    ))
    assert row(fact)[1:3] == ("We moved the meeting to evening.", 0)
    assert memory.retire_seed_memories(["I learned about the chase from the logs."]) == 1
    assert row(canon)[2] == 1
