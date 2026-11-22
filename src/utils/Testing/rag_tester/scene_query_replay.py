"""Replay alternate player questions against a selected FineTuneData request.

The local manifest selects the exact dialogue messages from each saved request.
Only this verified dialogue tail is replayed; saved system blocks and responses
never become facts. The snapshot, when given, is opened read-only.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import logging
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "generation_tester"), str(HERE)]
from finetune_audit import message_text
from canon_benchmark import seed_character
from controllers.model_controller import ModelController
from controllers.prompt_controller import PromptController
from managers.database_manager import DatabaseManager
from managers.memory_manager import MemoryManager
from managers.rag.rag_manager import RAGManager
from managers.settings_manager import SettingsManager
from profile_benchmark import PROFILES, TUNING_PROFILES
from rag_tester_core import LEXICAL_ONLY_OVERRIDES, SettingsOverride, setup_test_db, RagTesterService
from services.contracts import PromptBuildRequest, RequestPolicy

CONFIG = {
    **LEXICAL_ONLY_OVERRIDES, "RAG_SEARCH_MEMORY": True, "RAG_SEARCH_HISTORY": False,
    "RAG_MEMORY_MODE": "all", "RAG_KEYWORD_SEARCH": True, "RAG_USE_FTS": True,
    "RAG_USE_RRF": False, "RAG_NOISE_MAX": 0, "RAG_DETAILED_LOGS": False,
    "RAG_MAX_RESULTS": 5, "RAG_SIM_THRESHOLD": 0.4,
}


def selected_tail(sample, entries):
    messages = sample["messages"]
    current = next((i for i in range(len(messages) - 1, -1, -1)
                    if messages[i].get("role") == "user" and messages[i].get("sender") == "Player"), None)
    if current is None:
        raise ValueError("Sample has no identifiable final player input")
    selected = []
    previous = -1
    for entry in entries:
        index = entry["index"]
        if not previous < index < current:
            raise ValueError("Tail indexes must be ordered and precede the final player input")
        previous = index
        message = messages[index]
        if message.get("role") not in ("user", "assistant"):
            raise ValueError("Selected tail must contain dialogue messages")
        text = message_text(message.get("content")).strip()
        if not text or text.startswith(("[RUNTIME EVENT]", "[WORKING STATE]", "<", "React naturally")):
            raise ValueError("Selected message is empty or a context/event wrapper")
        selected.append({"role": message["role"], "content": text, "speaker": entry["speaker"]})
    return selected


def replay(scenario, sample, snapshot, profiles):
    cid = sample["character_id"]
    if cid != scenario["character"]:
        raise ValueError("Scenario and sample character differ")
    tail = selected_tail(sample, scenario["tail"])
    with tempfile.TemporaryDirectory(prefix="nm_scene_replay_", ignore_cleanup_errors=True) as directory:
        path = Path(directory) / "world.db"
        if snapshot:
            with closing(sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as src:
                with closing(sqlite3.connect(path)) as dst:
                    src.backup(dst)
        setup_test_db(str(path))
        RAGManager._INSTANCES = {}
        db = DatabaseManager()
        with db.connection() as connection, connection:
            connection.execute("UPDATE history SET is_active=0 WHERE character_id=?", (cid,))
        with SettingsOverride({**CONFIG, "RAG_SEARCH_GRAPH": True}), patch.object(MemoryManager, "_schedule_embed"):
            seed_character(cid)
            inserted = RagTesterService(lexical_only=True).insert_history_messages(
                cid, tail, is_active=1, embed_now=False,
            )
            if inserted != len(tail):
                raise RuntimeError(f"Incomplete dialogue tail for {scenario['label']}")
        model = object.__new__(ModelController)
        model.settings = SettingsManager
        prompt = PromptController()
        prompt._build_system_messages = lambda *_a, **_k: ([], [], [])
        prompt._build_system_state_message = lambda *_a, **_k: {"role": "system", "content": "[test state]"}
        char = SimpleNamespace(char_id=cid, get_variable=lambda key, default=None: default)
        report = []
        with patch.object(RAGManager, "_track_access_async"):
            for question in scenario["questions"]:
                for name, options in profiles.items():
                    report.extend(check_question(model, prompt, char, question, name, options))
        return {"scene": scenario["label"], "tail_rows": len(tail), "runs": report}


def check_question(model, prompt, char, question, profile, options):
    result = []
    for size in (0, 1, 2):
        with SettingsOverride({**CONFIG, **options, "RAG_QUERY_TAIL_MESSAGES": size}):
            block = model.process_rag(char.char_id, "", question["text"]) or ""
            built = prompt.build(PromptBuildRequest(
                character=char, event_type="chat", user_input=question["text"], rag_context=block,
                policy=RequestPolicy(use_history_in_prompt=False),
            ))
        delivered = "\n".join(
            str(item.get("content") or "") for item in built.messages
            if block and isinstance(item, dict) and item.get("role") == "system"
            and item.get("content") == block
        ).casefold()
        result.append({
            "variant": question["label"], "tail": size, "profile": profile, "rag_present": bool(delivered),
            "expected": {mark: any(word.casefold() in delivered for word in terms)
                         for mark, terms in question.get("expected", {}).items()},
            "forbidden": {mark: any(word.casefold() in delivered for word in terms)
                          for mark, terms in question.get("forbidden", {}).items()},
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    profiles = {name: profile for name, profile in {**PROFILES, **TUNING_PROFILES}.items()
                if not profile["RAG_VECTOR_SEARCH_ENABLED"]}
    parser.add_argument("--profiles", nargs="+", choices=tuple(profiles), default=["lexical"])
    args = parser.parse_args()
    if args.output.resolve() in {path.resolve() for path in (args.samples, args.manifest, args.snapshot) if path}:
        parser.error("The report path must differ from all input files")
    logging.disable(logging.CRITICAL)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    ids = {item["sample"] for item in manifest}
    samples = {}
    with args.samples.open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                if row.get("id") in ids:
                    samples[row["id"]] = row
    if ids - samples.keys():
        parser.error("One or more requested sample IDs were not found")
    selected = {name: profiles[name] for name in args.profiles}
    report = [replay(scene, samples[scene["sample"]], args.snapshot, selected) for scene in manifest]
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
