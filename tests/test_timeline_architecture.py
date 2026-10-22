from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TimelineArchitectureTests(unittest.TestCase):
    def test_domain_and_application_keep_storage_and_gui_dependencies_outside(self):
        domain = tuple((ROOT / "src/domain/timeline").glob("*.py"))
        application = tuple(ROOT / "src/services" / name for name in (
            "session_timeline.py", "conversation_timeline.py", "timeline_runtime.py",
            "timeline_context.py", "timeline_history_queries.py", "timeline_assets.py", "unity_timeline.py",
        ))
        for path in (*domain, *application):
            allowed = sys.stdlib_module_names | ({"domain"} if path in domain else {"domain", "services", "core"})
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules = [node.module or ""]
                else:
                    continue
                for module in modules:
                    root = module.split(".", 1)[0]
                    with self.subTest(path=path.name, dependency=module):
                        self.assertIn(root, allowed)
                        self.assertNotIn(root, {"sqlite3", "dbm", "shelve"})

    def test_sqlite_foundation_runs_without_site_packages_or_application_startup(self):
        source = textwrap.dedent('''
            import sqlite3
            import sys
            import tempfile
            from pathlib import Path
            sys.path.insert(0, sys.argv[1])
            from domain.timeline import JsonDocument
            from domain.timeline.archive import SessionArchive
            from infrastructure.timeline.sqlite import SQLiteTimelineRepository
            from infrastructure.timeline.assets import SQLiteTimelineAssets
            from services.conversation_timeline import ConversationTimeline
            from services.timeline_runtime import SessionTimelineRuntime
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "world.db"
                repository = SQLiteTimelineRepository(path)
                runtime = SessionTimelineRuntime(repository, repository)
                conversation = ConversationTimeline(runtime, SQLiteTimelineAssets(lambda: sqlite3.connect(path)))
                conversation.record_message({"message_id": "input", "content": "Hello"}, ("A",),
                                            actor_id="Player", player=True)
                checkpoint = runtime.timeline.checkpoint({"world": {"lives": 3}}, key="save")
                restored = runtime.restore(checkpoint.event_id)
                assert restored.to_dict() == {"world": {"lives": 3}}
                assert conversation.messages("A")[0]["content"] == "Hello"
                archive = repository.export_session(runtime.timeline.branch.session_id)
                decoded = SessionArchive.from_document(JsonDocument.parse(archive.to_document().canonical))
                target = SQLiteTimelineRepository(Path(folder) / "copy.db")
                target.import_session(decoded)
                assert target.export_session(archive.session_id).to_document() == archive.to_document()
        ''')
        result = subprocess.run([sys.executable, "-S", "-c", source, str(ROOT / "src")],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
