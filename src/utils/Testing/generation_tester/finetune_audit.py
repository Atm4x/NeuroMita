"""Audit saved FineTuneData requests and responses without loading a provider.

The report contains aggregate counters only. It never prints message text or
applies a recorded operation to a database from another point in time.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

SRC = Path(__file__).resolve().parents[3]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.dialogue_roster_context import historical_dialogue_observation
from utils.structured_response_parser import StructuredResponseParseError, parse_structured_response_with_meta

_LORE_ROW = re.compile(r"(?m)^\s*\[[^\n\]]+\]\s+N:(\d+)\s*\(seed_lore\b")
_DELIVERED_DIALOGUE = re.compile(r"(?m)^\s*(\[RUNTIME EVENT\]\s+\[Event\]|\[DialogueAuto\])\s+(?=\[DIALOGUE\])")
_CURRENT_EVENT = re.compile(r"(?m)^\s*(?:\[RUNTIME EVENT\]\s+)?\[Current UnityEvent\][ \t]*")
_DECODER = json.JSONDecoder()
_RAG_BLOCK = re.compile(r"<relevant_memories>.*?</relevant_memories>", re.DOTALL)
_LEGACY_SUMMARY_LINE = re.compile(r"(?m)^(\[[0-9 .:-]+\] )?\[(Character or System|Player)\]:")


def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content if isinstance(part, dict)
                         and part.get("type") == "text" and isinstance(part.get("text"), str))
    return ""


def mentions_id(spec, ids):
    for value in spec.split(","):
        first, sep, last = value.partition("-")
        start, end = parse_id(first), parse_id(last)
        if start is None:
            continue
        if not sep and start in ids:
            return True
        if sep and end is not None and any(start <= item <= end for item in ids):
            return True
    return False


def parse_id(value):
    value = value.strip()
    return int(value) if re.fullmatch(r"[0-9]{1,18}", value) else None


def audit_summary_request(texts, counts):
    for text in texts:
        if text.startswith("You are an assistant tasked with summarizing dialogue history of "):
            _, start, history = text.partition("\n<HISTORY>\n")
            history, end, _ = history.rpartition("\n</HISTORY>")
            if not start or not end:
                continue
        elif text.startswith("Summarize the conversation below into a compact factual memory"):
            _, start, history = text.partition("\nConversation:\n")
            history, end, _ = history.rpartition("\nSummary:")
            if not start or not end:
                continue
        else:
            continue
        counts["summary_requests"] += 1
        lines = _LEGACY_SUMMARY_LINE.findall(history)
        counts["summary_generic_author_lines"] += sum(speaker == "Character or System" for _, speaker in lines)
        counts["summary_player_label_lines"] += sum(speaker == "Player" for _, speaker in lines)
        counts["summary_requests_with_log_timestamps"] += any(stamp for stamp, _ in lines)
        break


def audit_sample(sample, counts):
    if not isinstance(sample, dict):
        counts["invalid_record"] += 1
        return
    counts["records"] += 1
    texts = [message_text(m.get("content")) for m in sample.get("messages", [])
             if isinstance(m, dict) and m.get("role") in {"system", "developer", "user", "event"}]
    audit_summary_request(texts, counts)
    if not sample.get("character_id") or sample["character_id"] == "unknown":
        counts["unattributed_requests"] += 1
        return

    counts["character_requests"] += 1
    delivered = []
    reacts = set()
    current = set()
    for text in texts:
        for match in _CURRENT_EVENT.finditer(text):
            try:
                event, _ = _DECODER.raw_decode(text, match.end())
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("name") == "DialogueAuto":
                description = event.get("description")
                if isinstance(description, str):
                    current.add(description.strip())
        pieces = _DELIVERED_DIALOGUE.split(text)
        for delivery, chunk in zip(pieces[1::2], pieces[2::2]):
            event = chunk.strip()
            delivered.append(event)
            if delivery == "[DialogueAuto]":
                reacts.add(event)
                continue
            historical = historical_dialogue_observation(event)
            if historical is not None:
                counts["recognized_historical_dialogue_envelopes"] += 1
                counts["historical_dialogue_characters_saved"] += len(event) - len(historical)
    if current & reacts:
        counts["turns_with_duplicate_current_dialogue"] += 1
    if delivered:
        headers = [event.splitlines()[0] for event in delivered]
        counts["turns_with_dialogue_tags"] += 1
        for name, items in (("headers", headers), ("payloads", delivered)):
            repeats = len(items) - len(set(items))
            counts[f"turns_with_repeated_dialogue_{name}"] += bool(repeats)
            counts[f"repeated_dialogue_{name}"] += repeats
    seed_ids = {
        int(number) for text in texts for block in _RAG_BLOCK.findall(text)
        for number in _LORE_ROW.findall(block)
    }
    if seed_ids:
        counts["turns_with_rendered_canon"] += 1

    try:
        parsed = parse_structured_response_with_meta(sample.get("response", ""))
    except StructuredResponseParseError:
        counts["unparsed_character_responses"] += 1
        return
    counts["parsed_character_responses"] += 1
    counts["repaired_character_responses"] += parsed.repaired
    result = parsed.response
    for field in ("memory_add", "memory_update", "memory_delete", "memory_merge"):
        operations = getattr(result, field) or []
        counts[f"turns_with_{field}"] += bool(operations)
        counts[field] += len(operations)
    specs = (
        list(result.memory_delete or [])
        + [item.partition("|")[0] for item in (result.memory_update or [])]
        + [item.partition(":")[0] for item in (result.memory_merge or [])]
    )
    if seed_ids and any(mentions_id(spec, seed_ids) for spec in specs):
        counts["turns_targeting_rendered_canon"] += 1


def audit(path):
    counts = Counter()
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid_jsonl_lines"] += 1
                continue
            audit_sample(sample, counts)
    return dict(sorted(counts.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    report = [{"file": path.name, "counts": audit(path)} for path in args.samples]
    formatted = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(formatted + "\n", encoding="utf-8")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
