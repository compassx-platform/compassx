"""Tests for the Agent Runtime Module."""
import unittest
from unittest.mock import MagicMock, patch

from app.agent_runtime.models import CreateAgentSessionRequest
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
        self.assertEqual(len(sess.messages), 1)
        self.assertEqual(sess.messages[0].role, "assistant")
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
    def test_send_message_and_reply(self, mock_sb):
        mock_instance = SandboxInstance(
            id="sb-opencode-1",
            name="OpenCode SB",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        mock_sb.get_sandbox.return_value = mock_instance
        req = CreateAgentSessionRequest(
            title="Chat Session",
            agent_type="opencode",
            sandbox_mode="existing",
            sandbox_id="sb-opencode-1",
        )
        sess = self.service.create_session(req)

        reply = self.service.send_message(sess.id, "How do I build the docker image?")
        self.assertEqual(reply.role, "assistant")
        self.assertIn("OpenCode", reply.content)
        self.assertEqual(len(sess.messages), 3)  # greeting, user, assistant

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


if __name__ == "__main__":
    unittest.main()

