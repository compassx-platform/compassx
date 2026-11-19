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
            replies = [item for item in loop.messages if item.get("role") == "assistant"]
            self.assertTrue(replies[0].get("tool_calls"))
            self.assertNotIn("tool_calls", replies[-1])

    def test_reply_on_the_next_line_is_not_left_inside_the_thought(self):
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
                max_turns=2,
            )
            transcript = TranscriptStore(os.path.join(root, "transcript.jsonl"))
            llm = MagicMock()
            llm.complete.return_value = {
                "choices": [{
                    "message": {
                        "content": "Thought: The user wants another canvas.\nSure — what should the new canvas contain?",
                    }
                }]
            }
            from sandbox_nova.tools.registry import build_default_registry

            loop = NovaAgentLoop(settings, llm, build_default_registry(settings), transcript)
            loop.handle_turn("another canvas")
            rows = transcript.read_all()
            self.assertEqual(rows[1]["kind"], "thinking")
            self.assertEqual(rows[1]["content"], "The user wants another canvas.")
            self.assertEqual(rows[2]["kind"], "reply")
            self.assertEqual(rows[2]["content"], "Sure — what should the new canvas contain?")

    def test_plan_mode_can_write_a_plan_and_cannot_write_files(self):
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
                max_turns=2,
            )
            transcript = TranscriptStore(os.path.join(root, "transcript.jsonl"))
            llm = MagicMock()
            llm.complete.return_value = {
                "choices": [{
                    "message": {
                        "content": "Thought: research first\n\n# Add a note\n\nWrite the note, then stop.",
                        "tool_calls": [{
                            "id": "call-plan",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"path": "secret.txt", "content": "nope"}),
                            },
                        }],
                    }
                }]
            }
            from sandbox_nova.modes import tool_definitions
            from sandbox_nova.tools.registry import build_default_registry

            registry = build_default_registry(settings)
            names = [item["function"]["name"] for item in tool_definitions(registry.openai_tools(), "plan")]
            self.assertIn("write_plan", names)
            self.assertNotIn("write_file", names)
            self.assertNotIn("create_plan", names)
            loop = NovaAgentLoop(settings, llm, registry, transcript)
            loop.handle_turn("plan the note", mode="plan")
            kinds = [row["kind"] for row in transcript.read_all()]
            self.assertIn("plan", kinds)
            self.assertFalse((Path(root) / "secret.txt").exists())

    def test_stop_file_ends_the_turn_before_the_next_model_call(self):
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
            Path(root, "stop").write_text("1", encoding="utf-8")
            transcript = TranscriptStore(os.path.join(root, "transcript.jsonl"))
            llm = MagicMock()
            from sandbox_nova.tools.registry import build_default_registry

            loop = NovaAgentLoop(settings, llm, build_default_registry(settings), transcript)
            loop.handle_turn("keep going")
            self.assertEqual(llm.complete.call_count, 0)
            self.assertEqual(transcript.read_all()[-1]["content"], "Stopped.")
            self.assertFalse(Path(root, "stop").exists())
