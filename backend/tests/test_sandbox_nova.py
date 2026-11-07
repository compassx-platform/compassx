"""Unit tests for the in-sandbox Nova CLI."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sandbox_nova.config import NovaSettings
from sandbox_nova.loop import NovaAgentLoop
from sandbox_nova.paths import resolve_workspace_path
from sandbox_nova.tools.local import WriteFileTool
from sandbox_nova.transcript import TranscriptStore


class TestSandboxNova(unittest.TestCase):
    def test_workspace_paths_stay_inside_root(self):
        with tempfile.TemporaryDirectory() as root:
            inside = resolve_workspace_path(root, "src/app.py")
            self.assertTrue(inside.startswith(os.path.abspath(root)))
            with self.assertRaises(ValueError):
                resolve_workspace_path(root, "../secret")

    def test_write_file_and_transcript(self):
        with tempfile.TemporaryDirectory() as root:
            tool = WriteFileTool(root)
            tool.execute({"path": "hello.txt", "content": "hi"})
            self.assertEqual(Path(root, "hello.txt").read_text(encoding="utf-8"), "hi")
            store = TranscriptStore(os.path.join(root, "transcript.jsonl"))
            store.append("reply", "done")
            rows = store.read_all()
            self.assertEqual(rows[0]["kind"], "reply")
            self.assertEqual(rows[0]["content"], "done")

    def test_loop_records_tool_and_reply(self):
        with tempfile.TemporaryDirectory() as root:
            settings = NovaSettings(
                session_id="ars_test",
                workspace_root=root,
                state_dir=root,
                model="gpt-test",
                gateway_url="http://gateway",
                gateway_key="secret",
                platform_url="http://platform",
                workspace_id="ws",
                max_turns=3,
            )
            transcript = TranscriptStore(os.path.join(root, "transcript.jsonl"))
            llm = MagicMock()
            llm.complete.side_effect = [
                {
                    "choices": [{
                        "message": {
                            "content": "Thought: check files\n\nLooking now.",
                            "tool_calls": [{
                                "id": "call1",
                                "function": {"name": "list_files", "arguments": json.dumps({"path": "."})},
                            }],
                        }
                    }]
                },
                {"choices": [{"message": {"content": "The workspace is empty.", "tool_calls": []}}]},
            ]
            from sandbox_nova.tools.registry import build_default_registry

            loop = NovaAgentLoop(settings, llm, build_default_registry(settings), transcript)
            loop.handle_turn("hi")
            kinds = [row["kind"] for row in transcript.read_all()]
            self.assertIn("user", kinds)
            self.assertIn("thinking", kinds)
            self.assertIn("tool", kinds)
            self.assertIn("reply", kinds)
            self.assertEqual(llm.complete.call_count, 2)
