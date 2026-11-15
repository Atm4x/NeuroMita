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

from utils.structured_response_parser import StructuredResponseParseError, parse_structured_response_with_meta

_LORE_ROW = re.compile(r"(?m)^\s*\[[^\n\]]+\]\s+N:(\d+)\s*\(seed_lore\b")
_DELIVERED_DIALOGUE = re.compile(r"(?m)^\s*(?:\[RUNTIME EVENT\]\s+\[Event\]|\[DialogueAuto\])\s+(?=\[DIALOGUE\])")
_RAG_BLOCK = re.compile(r"<relevant_memories>.*?</relevant_memories>", re.DOTALL)


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


def audit_sample(sample, counts):
    if not isinstance(sample, dict):
        counts["invalid_record"] += 1
        return
    counts["records"] += 1
    if not sample.get("character_id") or sample["character_id"] == "unknown":
        counts["unattributed_requests"] += 1
        return

    counts["character_requests"] += 1
    texts = [message_text(m.get("content")) for m in sample.get("messages", [])
             if isinstance(m, dict) and m.get("role") in {"system", "developer", "user"}]
    delivered = [event.strip() for text in texts for event in _DELIVERED_DIALOGUE.split(text)[1:]]
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
