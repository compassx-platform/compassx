"""Tests for the Agent Runtime Module."""
import unittest
from unittest.mock import MagicMock, patch

from app.agent_runtime.models import CreateAgentSessionRequest, CreateProjectRequest
from app.agent_runtime.service import AgentRuntimeService
from app.sandbox.models import SandboxInstance, SandboxStatus


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.service = AgentRuntimeService()
        self.service._sessions.clear()

    @patch("app.agent_runtime.service.sandbox_service")
    def test_create_session_with_new_sandbox(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-test-123",
            name="Test Sandbox",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.ensure_sandbox.return_value = mock_instance

        req = CreateAgentSessionRequest(
            title="Analysis Task",
            agent_type="antigravity",
            sandbox_mode="new",
        )
        sess = self.service.create_session(req, workspace_id="ws-1")

        self.assertEqual(sess.title, "Analysis Task")
        self.assertEqual(sess.agent_type, "antigravity")
        self.assertEqual(sess.sandbox_id, "sb-test-123")
        self.assertEqual(len(sess.messages), 0)
        mock_sb.ensure_sandbox.assert_called_once()

    @patch("app.agent_runtime.service.sandbox_service")
    def test_create_session_with_existing_sandbox(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-existing-999",
            name="Existing Sandbox",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance

        req = CreateAgentSessionRequest(
            title="Bugfix Task",
            agent_type="pi",
            sandbox_mode="existing",
            sandbox_id="sb-existing-999",
        )
        sess = self.service.create_session(req, workspace_id="ws-1")

        self.assertEqual(sess.title, "Bugfix Task")
        self.assertEqual(sess.agent_type, "pi")
        self.assertEqual(sess.sandbox_id, "sb-existing-999")
        mock_sb.ensure_sandbox.assert_not_called()

    @patch("app.agent_runtime.service.sandbox_service")
    def test_send_message_delivers_prompt_to_tmux(self, mock_sb):
        from app.sandbox.models import ExecResult

        mock_instance = SandboxInstance(
            id="sb-opencode-1",
            name="OpenCode SB",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance

        def exec_side_effect(_sandbox_id, command, **_kwargs):
            if "capture-pane" in command:
                return ExecResult(exit_code=0, stdout="agent pane is ready and drawing", success=True)
            return ExecResult(exit_code=0, stdout="", stderr="", success=True)

        mock_sb.exec_in_sandbox.side_effect = exec_side_effect
        req = CreateAgentSessionRequest(
            title="Chat Session",
            agent_type="opencode",
            sandbox_mode="existing",
            sandbox_id="sb-opencode-1",
        )
        sess = self.service.create_session(req)

        reply = self.service.send_message(sess.id, "How do I build the docker image?")
        self.assertEqual(reply.role, "user")
        self.assertIn("docker image", reply.content)
        stored = self.service.get_session(sess.id)
        self.assertEqual(stored.messages[-1].content, reply.content)
        self.assertEqual(stored.messages[-1].role, "user")
        commands = [call.args[1] for call in mock_sb.exec_in_sandbox.call_args_list]
        self.assertTrue(any("tmux new-session" in command for command in commands))
        self.assertTrue(any("tmux paste-buffer" in command for command in commands))
        self.assertTrue(any("opencode" in command for command in commands))

    @patch("app.agent_runtime.service.sandbox_service")
    def test_nova_prompt_starts_sandbox_cli(self, mock_sb):
        from app.sandbox.models import ExecResult

        mock_instance = SandboxInstance(
            id="sb-nova-1",
            name="Nova SB",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance
        mock_sb.exec_in_sandbox.return_value = ExecResult(exit_code=0, stdout="ok", success=True)
        sess = self.service.create_session(
            CreateAgentSessionRequest(
                title="Nova Session",
                agent_type="nova",
                sandbox_mode="existing",
                sandbox_id="sb-nova-1",
            )
        )
        with patch("app.agent_runtime.sandbox_controller.orchestrate_stream", create=True):
            self.service.deliver_prompt(sess.id, "hi")
        commands = [call.args[1] for call in mock_sb.exec_in_sandbox.call_args_list]
        self.assertTrue(any("tmux new-session" in command for command in commands))
        self.assertTrue(any("nova" in command.lower() for command in commands))
        joined = " ".join(commands)
        self.assertNotIn("orchestrate_stream", joined)

    @patch("app.agent_runtime.service.sandbox_service")
    def test_workspace_reads_and_rejects_parent_paths(self, mock_sb):
        from app.sandbox.models import ExecResult

        mock_instance = SandboxInstance(
            id="sb-files",
            name="Files",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance
        mock_sb.exec_in_sandbox.return_value = ExecResult(
            exit_code=0,
            stdout='{"root":"/workspace","entries":[{"path":"src/app.py","type":"file","size":12}]}',
            success=True,
        )
        req = CreateAgentSessionRequest(
            title="Files",
            agent_type="pi",
            sandbox_mode="existing",
            sandbox_id="sb-files",
        )
        sess = self.service.create_session(req)
        listed = self.service.list_workspace_files(sess.id)
        self.assertEqual(listed.entries[0].path, "src/app.py")
        with self.assertRaises(ValueError):
            self.service.read_workspace_file(sess.id, "../etc/passwd")
        mock_sb.exec_in_sandbox.return_value = ExecResult(
            exit_code=0,
            stdout='{"path":"src/app.py","bytes":8}',
            success=True,
        )
        written = self.service.write_workspace_file(sess.id, "src/app.py", "print(2)\n")
        self.assertEqual(written.bytes, 8)
        command = mock_sb.exec_in_sandbox.call_args.args[1]
        self.assertIn("CX_REL", command)
        with self.assertRaises(ValueError):
            self.service.write_workspace_file(sess.id, "../etc/passwd", "nope")

    @patch("app.agent_runtime.service.sandbox_service")
    def test_delete_session(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-del-1",
            name="Delete SB",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance
        req = CreateAgentSessionRequest(
            title="To Delete",
            agent_type="antigravity",
            sandbox_mode="existing",
            sandbox_id="sb-del-1",
        )
        sess = self.service.create_session(req)
        self.assertTrue(self.service.delete_session(sess.id))
        self.assertIsNone(self.service.get_session(sess.id))

    @patch("app.agent_runtime.service.sandbox_service")
    def test_list_sessions_filter_by_workspace(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-ws-test",
            name="WS Test",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.ensure_sandbox.return_value = mock_instance

        # Create session in ws-alpha
        req1 = CreateAgentSessionRequest(title="Alpha Session", agent_type="antigravity", sandbox_mode="new")
        s1 = self.service.create_session(req1, workspace_id="ws-alpha")

        # Create session in ws-beta
        req2 = CreateAgentSessionRequest(title="Beta Session", agent_type="pi", sandbox_mode="new")
        s2 = self.service.create_session(req2, workspace_id="ws-beta")

        # Filter by ws-alpha
        alpha_list = self.service.list_sessions(workspace_id="ws-alpha")
        alpha_ids = [s.id for s in alpha_list]
        self.assertIn(s1.id, alpha_ids)
        self.assertNotIn(s2.id, alpha_ids)

        # Filter by ws-beta
        beta_list = self.service.list_sessions(workspace_id="ws-beta")
        beta_ids = [s.id for s in beta_list]
        self.assertIn(s2.id, beta_ids)
        self.assertNotIn(s1.id, beta_ids)

        # Unfiltered lists all
        all_list = self.service.list_sessions(workspace_id=None)
        all_ids = [s.id for s in all_list]
        self.assertIn(s1.id, all_ids)
        self.assertIn(s2.id, all_ids)

    @patch("app.agent_runtime.service.sandbox_service")
    def test_session_belongs_to_project(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-project-1",
            name="Project Sandbox",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.ensure_sandbox.return_value = mock_instance

        project = self.service.create_project(CreateProjectRequest(name="Billing"))
        self.assertTrue(project.id.startswith("arp_"))
        self.assertEqual(project.name, "Billing")

        sess = self.service.create_session(
            CreateAgentSessionRequest(title="Fix invoice", agent_type="pi", project_id=project.id),
            workspace_id="ws-1",
        )
        self.assertEqual(sess.project_id, project.id)

        with self.assertRaises(ValueError):
            self.service.create_session(
                CreateAgentSessionRequest(title="Missing", project_id="arp_missing"),
            )

        self.assertTrue(self.service.delete_project(project.id))
        listed = self.service.list_projects()
        self.assertNotIn(project.id, [item.id for item in listed])
        reloaded = self.service.get_session(sess.id)
        self.assertIsNone(reloaded.project_id)


class TestAgentAdapters(unittest.TestCase):
    def test_builtin_agents_launch_through_the_registry(self):
        from app.sandbox.agent_cli import agent_inner_command
        from app.sandbox.agents import agent_registry

        self.assertIn("pi --approve", agent_inner_command("pi", "ars_1"))
        self.assertIn("opencode", agent_inner_command("opencode", "ars_1"))
        self.assertIn("agy", agent_inner_command("antigravity", "ars_1"))
        self.assertIn("claude --dangerously-skip-permissions", agent_inner_command("claude", "ars_1"))
        self.assertIn("codex --dangerously-bypass-approvals-and-sandbox", agent_inner_command("codex", "ars_1"))
        self.assertIn("cursor-agent", agent_inner_command("cursor", "ars_1"))
        ids = [item["id"] for item in agent_registry.catalog()]
        self.assertEqual(ids, ["nova", "antigravity", "pi", "opencode", "claude", "codex", "cursor"])
        self.assertIn("nova serve", agent_inner_command("nova", "ars_1"))

    def test_nova_and_cli_agents_are_isolated(self):
        from app.sandbox.agents import is_cli_agent, is_nova_agent

        self.assertTrue(is_nova_agent("nova"))
        self.assertFalse(is_cli_agent("nova"))
        self.assertTrue(is_cli_agent("antigravity"))
        self.assertFalse(is_nova_agent("antigravity"))

    def test_antigravity_activity_is_scoped_to_the_runtime_session(self):
        import base64
        from app.sandbox.activity import antigravity_activity_command

        command = antigravity_activity_command(["hi"], "ars_session1")
        encoded = command.split("base64.b64decode('")[1].split("')")[0]
        decoded = base64.b64decode(encoded).decode()
        self.assertIn("ars_session1", decoded)
        self.assertIn("conv_id", decoded)
        self.assertIn("read_antigravity_activities", decoded)

    def test_new_agent_registers_without_changing_the_dispatcher(self):
        from app.sandbox.agents import AgentRegistry, TmuxCodingAgent

        registry = AgentRegistry()

        class DemoAgent(TmuxCodingAgent):
            id = "demo"
            label = "Demo"

            def launch_command(self, session_id: str | None) -> str:
                return "demo-agent --yes"

        registry.register(DemoAgent())
        self.assertEqual(registry.get("demo").launch_command("ars_1"), "demo-agent --yes")
        delivered = registry.get("demo").deliver_command("ars_1", "hello")
        self.assertIn("tmux paste-buffer", delivered)
        self.assertIn("copy-mode -q", delivered)
        from app.sandbox.agent_cli import interactive_shell_command

        attached = interactive_shell_command("antigravity", "ars_1", "/workspace")
        self.assertIn("mouse on", attached)
        self.assertIn("history-limit 50000", attached)
        self.assertIsNone(registry.get("missing"))

    def test_branch_checkout_rejects_unsafe_names(self):
        from app.agent_runtime.workspace import checkout_branch_command, safe_branch_name

        self.assertEqual(safe_branch_name("feature/billing"), "feature/billing")
        with self.assertRaises(ValueError):
            safe_branch_name("../main")
        import base64

        command = checkout_branch_command("main")
        encoded = command.split()[-1].strip("'")
        self.assertIn(b"checkout", base64.b64decode(encoded))

    def test_thinking_and_tool_calls_are_read_from_agent_transcripts(self):
        from app.sandbox.activity import activities_from_opencode_parts, activities_from_pane, activities_from_pi_entries

        opencode = activities_from_opencode_parts(
            [
                ("prt_user", '{"role":"user"}', '{"type":"text","text":"hi"}'),
                ("prt_think", '{"role":"assistant"}', '{"type":"reasoning","text":"I should list the workspace."}'),
                (
                    "prt_tool",
                    '{"role":"assistant"}',
                    '{"type":"tool","tool":"bash","state":{"status":"completed","input":{"command":"ls"},"output":"app.py"}}',
                ),
            ]
        )
        self.assertEqual(opencode[0]["kind"], "thinking")
        self.assertIn("list the workspace", opencode[0]["content"])
        self.assertEqual(opencode[1]["content"].splitlines()[0], "bash")
        self.assertIn("ls", opencode[1]["content"])
        self.assertIn("app.py", opencode[1]["content"])

        pi = activities_from_pi_entries(
            [
                {
                    "type": "message",
                    "id": "abc",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "Look at the file first."},
                            {"type": "toolCall", "id": "call_1", "name": "read", "arguments": {"path": "src/app.py"}},
                        ],
                    },
                },
                {
                    "type": "message",
                    "id": "def",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": "call_1",
                        "toolName": "read",
                        "content": [{"type": "text", "text": "print(1)"}],
                        "isError": False,
                    },
                },
            ]
        )
        self.assertEqual(pi[0]["kind"], "thinking")
        self.assertEqual(pi[1]["source_id"], "call_1")
        self.assertIn("src/app.py", pi[1]["content"])
        self.assertIn("print(1)", pi[1]["content"])

        pane = activities_from_pane("Thinking: check the tests\nread src/app.py\nhi\n")
        self.assertEqual([item["kind"] for item in pane], ["thinking", "tool"])

    def test_antigravity_transcript_syncs_replies_and_tool_calls(self):
        from app.sandbox.activity import activities_from_antigravity_steps, antigravity_conversation_score

        read_prompt = "Read /workspace/src/app.py and tell me exactly what it prints."
        steps = [
            {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "<USER_REQUEST>\nhi\n</USER_REQUEST>"},
            {"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Hello! How can I help you today?"},
            {"step_index": 2, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "<USER_REQUEST>\n%s\n</USER_REQUEST>" % read_prompt},
            {
                "step_index": 3,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"Path": "/workspace/src/app.py"}}],
            },
            {"step_index": 4, "source": "MODEL", "type": "GENERIC", "content": "Created At: 2026-10-30T02:09:46Z\n1: print(1)"},
            {
                "step_index": 5,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "content": "The file [app.py](file:///workspace/src/app.py) contains:\n\nprint(1)",
            },
        ]
        parsed = activities_from_antigravity_steps(steps, "conv")
        kinds = [item["kind"] for item in parsed["activities"]]
        self.assertEqual(kinds, ["reply", "tool", "reply"])
        self.assertEqual(parsed["activities"][0]["content"], "Hello! How can I help you today?")
        self.assertEqual(parsed["activities"][0]["request_index"], 0)
        self.assertIn("read_file", parsed["activities"][1]["content"])
        self.assertIn("/workspace/src/app.py", parsed["activities"][1]["content"])
        self.assertIn("print(1)", parsed["activities"][1]["content"])
        self.assertNotIn("Created At:", parsed["activities"][1]["content"])
        self.assertIn("app.py", parsed["activities"][2]["content"])
        self.assertNotIn("file://", parsed["activities"][2]["content"])
        self.assertEqual(parsed["activities"][1]["request_index"], 1)
        self.assertEqual(parsed["activities"][2]["order"], 2)
        self.assertEqual(antigravity_conversation_score(steps, ["hi", read_prompt]), 2)
        self.assertEqual(antigravity_conversation_score(steps, ["Reply with the single word ok."]), 0)

        from app.agent_runtime.models import AgentChatMessage, AgentRuntimeSession
        from app.agent_runtime.service import AgentRuntimeService

        session = AgentRuntimeSession(
            id="ars_test",
            title="t",
            agent_type="antigravity",
            sandbox_id="sb",
            status="active",
            messages=[
                AgentChatMessage(id="1", role="user", content=read_prompt, timestamp="2026-10-30T01:39:50+00:00"),
                AgentChatMessage(id="2", role="user", content="hi", timestamp="2026-10-30T02:06:21+00:00"),
                AgentChatMessage(id="3", role="user", content=read_prompt, timestamp="2026-10-30T02:09:42+00:00"),
            ],
        )
        service = object.__new__(AgentRuntimeService)
        hello_at = service._activity_timestamp(
            session,
            {"requests": parsed["requests"], "request_index": 0, "order": 1},
        )
        answer_at = service._activity_timestamp(
            session,
            {"requests": parsed["requests"], "request_index": 1, "order": 2},
        )
        self.assertTrue(hello_at.startswith("2026-10-30T02:06:21"))
        self.assertTrue(answer_at.startswith("2026-10-30T02:09:42"))

        counted = activities_from_antigravity_steps(
            [
                {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "<USER_REQUEST>\nhow many files are there?\n</USER_REQUEST>"},
                {
                    "step_index": 1,
                    "source": "MODEL",
                    "type": "PLANNER_RESPONSE",
                    "content": "",
                    "thinking": "The request is to determine the number of files within the workspace.",
                    "tool_calls": [{
                        "name": "run_command",
                        "args": {
                            "CommandLine": "find /workspace -type f | wc -l",
                            "WaitMsBeforeAsync": 5000,
                            "toolSummary": "Count files in workspace",
                        },
                    }],
                },
                {"step_index": 2, "source": "MODEL", "type": "GENERIC", "content": "Command exited with code 0.\nCommand output:\n0"},
                {"step_index": 3, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "There are currently 0 files."},
            ],
            "count",
        )
        self.assertEqual([item["kind"] for item in counted["activities"]], ["thinking", "tool", "reply"])
        self.assertIn("number of files", counted["activities"][0]["content"])
        self.assertIn("find /workspace", counted["activities"][1]["content"])
        self.assertNotIn("waitmsbeforeasync", counted["activities"][1]["content"].lower())
        self.assertNotIn("{", counted["activities"][1]["content"])

    def test_terminal_errors_are_captured_without_agent_chrome(self):
        from app.sandbox.agents import extract_terminal_notices

        pane = """
  ┃
  ┃  hi
  ┃
  ┃  Failed to process error response
  ┃
  ┃  hello
  ┃
  ┃  Forbidden: request was blocked by a gateway or proxy. You
  ┃  may not have permission to access this resource — check your
  ┃  account and provider settings.
  ┃
     ▣  Build · MiMo V2.5 Free
   /workspace                          tab agents  ctrl+p commands
"""
        notices = extract_terminal_notices(pane)
        self.assertEqual(
            notices,
            [
                "Failed to process error response",
                "Forbidden: request was blocked by a gateway or proxy. You\nmay not have permission to access this resource — check your\naccount and provider settings.",
            ],
        )


if __name__ == "__main__":
    unittest.main()

