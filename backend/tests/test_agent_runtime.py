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


if __name__ == "__main__":
    unittest.main()
