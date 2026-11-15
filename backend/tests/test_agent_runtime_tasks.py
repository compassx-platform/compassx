"""Tasks live in Agent Runtime and start a session only when a person marks one ready."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.agent_runtime.models import CreateAgentTaskRequest
from app.agent_runtime.service import AgentRuntimeService
from app.agent_runtime import tasks as agent_tasks
from app.sandbox.models import SandboxInstance, SandboxStatus


class TestAgentRuntimeTasks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = patch(
            "app.agent_runtime.tasks.TASKS_STORE_PATH",
            os.path.join(self.tmp.name, "tasks.json"),
        )
        self.session_path_patch = patch(
            "app.agent_runtime.service.SESSIONS_STORE_PATH",
            os.path.join(self.tmp.name, "sessions.json"),
        )
        self.db_patch = patch("app.database.SystemSessionLocal", None)
        self.path_patch.start()
        self.session_path_patch.start()
        self.db_patch.start()
        self.service = AgentRuntimeService()
        self.service._tasks.clear()
        self.sb_patch = patch("app.agent_runtime.service.sandbox_service")
        self.mock_sb = self.sb_patch.start()
        self.mock_sb.ensure_sandbox.return_value = SandboxInstance(
            id="sb-task-1",
            name="Task Sandbox",
            consumer_module="agent",
            status=SandboxStatus.RUNNING,
            runtime_mode="docker",
        )
        self.service.deliver_prompt = MagicMock()

    def tearDown(self):
        self.sb_patch.stop()
        self.db_patch.stop()
        self.session_path_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def _file(self, title="Write the migration"):
        return agent_tasks.create_task(
            self.service,
            CreateAgentTaskRequest(title=title, brief="Add the tasks table.", actor="person", agent_type="antigravity"),
        )

    def test_filing_stays_draft(self):
        task = self._file()
        self.assertEqual(task.stage, "draft")
        self.assertIsNone(task.session_id)
        self.mock_sb.ensure_sandbox.assert_not_called()

    def test_agent_cannot_mark_ready(self):
        task = self._file()
        with self.assertRaises(ValueError):
            agent_tasks.mark_ready(self.service, task.id, "agent")

    def test_ready_starts_session(self):
        task = self._file()
        started = agent_tasks.mark_ready(self.service, task.id, "person")
        self.assertEqual(started.stage, "in_progress")
        self.assertTrue(started.session_id)
        self.service.deliver_prompt.assert_called_once()
        prompt = self.service.deliver_prompt.call_args.args[1]
        self.assertIn("Write the migration", prompt)
        self.assertIn("Add the tasks table.", prompt)

    def test_failed_start_stays_ready(self):
        self.service.deliver_prompt.side_effect = RuntimeError("sandbox down")
        task = self._file()
        started = agent_tasks.mark_ready(self.service, task.id, "person")
        self.assertEqual(started.stage, "ready")
        self.assertIn("sandbox down", started.start_error)
        self.assertIsNone(started.session_id)

    def test_park_requires_a_reason(self):
        task = self._file()
        with self.assertRaises(ValueError):
            agent_tasks.mark_waiting(self.service, task.id, "  ", "person")

    def test_review_accepts_only_from_a_person(self):
        task = agent_tasks.mark_ready(self.service, self._file().id, "person")
        submitted = agent_tasks.submit_task(self.service, task.id, "Migration is in place.", "agent")
        self.assertEqual(submitted.stage, "in_review")
        with self.assertRaises(ValueError):
            agent_tasks.accept_task(self.service, submitted.id, "agent")
        done = agent_tasks.accept_task(self.service, submitted.id, "person")
        self.assertEqual(done.stage, "done")

    def test_changes_continue_the_same_session(self):
        task = agent_tasks.mark_ready(self.service, self._file().id, "person")
        submitted = agent_tasks.submit_task(self.service, task.id, "", "agent")
        self.service.deliver_prompt.reset_mock()
        continued = agent_tasks.request_changes(self.service, submitted.id, "Also cover downgrade.", "person")
        self.assertEqual(continued.stage, "in_progress")
        self.assertEqual(continued.session_id, task.session_id)
        self.service.deliver_prompt.assert_called_once()
        self.assertIn("Also cover downgrade.", self.service.deliver_prompt.call_args.args[1])

    def test_finished_nova_reply_moves_to_review(self):
        from app.agent_runtime.models import AgentChatMessage, CreateAgentTaskRequest

        task = agent_tasks.create_task(
            self.service,
            CreateAgentTaskRequest(title="Say hi", brief="say hi", actor="person", agent_type="nova"),
        )
        started = agent_tasks.mark_ready(self.service, task.id, "person")
        session = self.service.get_session(started.session_id)
        session.messages = [
            AgentChatMessage(id="u", role="user", content="say hi"),
            AgentChatMessage(id="a", role="assistant", content="Hi.", kind="reply"),
        ]
        self.service._sessions[session.id] = session
        with patch(
            "app.agent_runtime.sandbox_controller.nova_sandbox_controller.inbox_names",
            return_value=["turn.done.json"],
        ):
            released = agent_tasks.release_finished_session(self.service, session.id)
        self.assertEqual(released.stage, "in_review")
        self.assertEqual(agent_tasks.get_task(self.service, task.id).stage, "in_review")

    def test_running_turn_stays_in_progress(self):
        from app.agent_runtime.models import AgentChatMessage, CreateAgentTaskRequest

        task = agent_tasks.create_task(
            self.service,
            CreateAgentTaskRequest(title="Say hi", brief="say hi", actor="person", agent_type="nova"),
        )
        started = agent_tasks.mark_ready(self.service, task.id, "person")
        session = self.service.get_session(started.session_id)
        session.messages = [
            AgentChatMessage(id="u", role="user", content="say hi"),
            AgentChatMessage(id="a", role="assistant", content="Hi.", kind="reply"),
        ]
        self.service._sessions[session.id] = session
        with patch(
            "app.agent_runtime.sandbox_controller.nova_sandbox_controller.inbox_names",
            return_value=["turn.json.working"],
        ):
            released = agent_tasks.release_finished_session(self.service, session.id)
        self.assertIsNone(released)
        self.assertEqual(agent_tasks.get_task(self.service, task.id).stage, "in_progress")

    def test_agent_files_a_draft_from_the_current_session(self):
        from app.agent_runtime.models import CreateAgentSessionRequest
        from app.agent_runtime.sandbox_tools import file_task_from_session

        session = self.service.create_session(
            CreateAgentSessionRequest(title="Working session", agent_type="nova", sandbox_mode="new"),
            workspace_id="ws-1",
        )
        filed = file_task_from_session(
            session,
            {"title": "Filed from chat", "brief": "Do this later."},
            service=self.service,
        )
        task = agent_tasks.get_task(self.service, filed["task_id"])
        self.assertEqual(task.stage, "draft")
        self.assertEqual(task.source_session_id, session.id)
        self.assertEqual(task.title, "Filed from chat")
        self.assertEqual(filed["stage"], "draft")
        self.service.deliver_prompt.assert_not_called()
