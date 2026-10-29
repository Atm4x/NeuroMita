"""Measure domain workloads against the SQLite adapter without touching user data."""
from __future__ import annotations

import argparse
import json
import statistics
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.timeline import CausalLink, CausalRelation, EventKind
from infrastructure.timeline.sqlite import SQLiteTimelineRepository
from infrastructure.timeline.context import SQLiteContextSummaries
from services.conversation_timeline import ConversationTimeline
from services.session_timeline import SessionTimeline
from services.timeline_runtime import SessionTimelineRuntime
from services.timeline_context import TimelineContext


def measure(operation, repeats):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000)
    ordered = sorted(samples)
    return {"median_ms": round(statistics.median(samples), 3),
            "max_ms": round(ordered[-1], 3), "runs": repeats}


def benchmark(count, repeats):
    with tempfile.TemporaryDirectory(prefix="neuromita-timeline-benchmark-") as folder:
        path = Path(folder) / "benchmark.db"
        repository = SQLiteTimelineRepository(path)
        timeline = SessionTimeline.create(repository, session_id="benchmark", branch_id="main")
        for character in ("A", "B", "C"):
            timeline.join(character, key=f"join:{character}")
        repository.select("benchmark", timeline.branch_id, expected=None)
        runtime = SessionTimelineRuntime(repository, repository, workspace_name="benchmark")
        conversation = ConversationTimeline(runtime)
        context = TimelineContext(conversation, SQLiteContextSummaries(lambda: sqlite3.connect(path)))
        questions = {}
        started = time.perf_counter()
        for start in range(0, count, 200):
            drafts = []
            for index in range(start, min(count, start + 200)):
                character = ("A", "B", "C")[(index // 2) % 3]
                question = index % 2 == 0
                links = () if question else (CausalLink(CausalRelation.REPLY_TO, questions[character]),)
                draft = timeline.draft(
                    EventKind.PLAYER_MESSAGE if question else EventKind.CHARACTER_MESSAGE,
                    {"message_id": f"message:{index}", "content": f"{index}: " + "a session fact " * 20},
                    actor_id="Player" if question else character, observers=(character,), links=links,
                    key=f"message:{index}",
                )
                if question:
                    questions[character] = draft.event_id
                drafts.append(draft)
            timeline.append(drafts, expected_head=timeline.branch.head_sequence, key=f"batch:{start}")
        append_ms = (time.perf_counter() - started) * 1000
        checkpoint = timeline.checkpoint({"world": {"lives": 3}}, key="checkpoint")
        latest_question = next(reversed(questions.values()))
        context.store("A", conversation.context_messages("A")[:-40], "Synthetic summary of the exact prefix")
        cold_page = measure(lambda: conversation.history_queries.page("main", "A", limit=50), 1)
        output = {
            "events": count, "characters": 3, "text_chars_per_message": 300,
            "append": {"total_ms": round(append_ms, 3), "events_per_second": round(count / (append_ms / 1000), 1)},
            "character_context": measure(lambda: conversation.context_messages("A"), repeats),
            "character_messages": measure(lambda: timeline.messages("A"), repeats),
            "cold_history_page": cold_page,
            "warm_history_page": measure(lambda: conversation.history_queries.page("main", "A", limit=50), repeats),
            "summarized_context": measure(lambda: context.unsummarized("A"), repeats),
            "observer_page": measure(lambda: repository.read("main", observer="A", after=max(0, count - 200)), repeats),
            "point_knowledge": measure(lambda: timeline.knows("A", latest_question), repeats),
            "presence": measure(timeline.present, repeats),
            "archive_export": measure(lambda: repository.export_session("benchmark"), repeats),
        }
        counter = 0

        def fork():
            nonlocal counter
            counter += 1
            timeline.fork(checkpoint.event_id, branch_id=f"branch:{counter}")

        output["fork"] = measure(fork, repeats)
        output["database_bytes"] = path.stat().st_size
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.events < 2 or args.events % 2 or args.repeats < 1:
        parser.error("events must be a positive even number; repeats must be positive")
    print(json.dumps(benchmark(args.events, args.repeats), indent=2))


if __name__ == "__main__":
    main()
