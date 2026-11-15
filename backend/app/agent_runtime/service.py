"""Agent Runtime Service — orchestrates agent sessions bound to compute sandboxes."""
import base64
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.agent_runtime.models import (
    AgentChatMessage,
    AgentRuntimeProject,
    AgentRuntimeProjectDB,
    AgentRuntimeSession,
    AgentRuntimeSessionDB,
    AgentRuntimeTaskDB,
    ChangeEntry,
    ChangesResponse,
    CommitEntry,
    CreateAgentSessionRequest,
    CreateProjectRequest,
    DiffResponse,
    FileContentResponse,
    GitInfoResponse,
    WriteFileResponse,
    WorkspaceEntry,
    WorkspaceFilesResponse,
)
from app.agent_runtime.workspace import (
    changes_command,
    diff_command,
    patch_command,
    file_content_command,
    checkout_branch_command,
    files_command,
    git_info_command,
    write_file_command,
    parse_json_stdout,
    safe_relative_path,
)
from app.sandbox.agent_cli import deliver_prompt_command, detached_start_command, ensure_pane_log_command, pane_capture_command, read_pane_log_command
from app.sandbox.agents import agent_registry, is_nova_agent
from app.sandbox.models import SandboxSpec, SandboxStatus
from app.sandbox.service import sandbox_service

logger = logging.getLogger(__name__)


def _notice_already_shown(notice: str, existing: list[str] | set[str]) -> bool:
    compact = " ".join((notice or "").split())
    if not compact:
        return True
    for other in existing:
        other_compact = " ".join((other or "").split())
        if not other_compact:
            continue
        if compact == other_compact or other_compact.startswith(compact) or compact.startswith(other_compact):
            return True
    return False

SESSIONS_STORE_PATH = os.path.join(
    os.path.expanduser("~"), ".compassx", "agent_runtime_sessions.json"
)
PROJECTS_STORE_PATH = os.path.join(
    os.path.expanduser("~"), ".compassx", "agent_runtime_projects.json"
)


class AgentRuntimeService:
    """Manages agent runtime sessions, their immutable sandbox bindings, and chat interactions with PostgreSQL persistence."""

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, AgentRuntimeSession] = {}
        self._projects: Dict[str, AgentRuntimeProject] = {}
        self._tasks: Dict[str, object] = {}
        self._starting_task_ids: set[str] = set()
        self._ensure_table_exists()
        self._sync_and_load_sessions()
        self._load_projects()
        from app.agent_runtime.tasks import load_tasks
        load_tasks(self)

    def _ensure_table_exists(self):
        try:
            from sqlalchemy import text
            from app.database import system_engine, SystemBase
            if system_engine is not None:
                SystemBase.metadata.create_all(
                    bind=system_engine,
                    tables=[
                        AgentRuntimeProjectDB.__table__,
                        AgentRuntimeSessionDB.__table__,
                        AgentRuntimeTaskDB.__table__,
                    ],
                    checkfirst=True,
                )
                if system_engine.dialect.name == "postgresql":
                    with system_engine.connect() as conn:
                        conn.execute(text(
                            "ALTER TABLE agent_runtime_sessions ADD COLUMN IF NOT EXISTS project_id VARCHAR(64)"
                        ))
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS ix_agent_runtime_sessions_project_id ON agent_runtime_sessions (project_id)"
                        ))
                        conn.execute(text(
                            "ALTER TABLE agent_runtime_sessions ADD COLUMN IF NOT EXISTS llm_model VARCHAR(255)"
                        ))
                        conn.execute(text(
                            "ALTER TABLE agent_runtime_sessions ADD COLUMN IF NOT EXISTS nova_chat_session_id INTEGER"
                        ))
                        conn.commit()
        except Exception as e:
            logger.debug("[AgentRuntimeService] Table ensure warning: %s", e)

    def _load_sessions(self):
        try:
            if os.path.exists(SESSIONS_STORE_PATH):
                with open(SESSIONS_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        sess = AgentRuntimeSession(**item)
                        self._sessions[sess.id] = sess
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to load stored sessions from file: %s", e)

    def _persist_sessions(self):
        try:
            os.makedirs(os.path.dirname(SESSIONS_STORE_PATH), exist_ok=True)
            with open(SESSIONS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump([s.model_dump() for s in self._sessions.values()], f, indent=2)
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to persist sessions to file fallback: %s", e)

    def _sync_and_load_sessions(self):
        # 1. Load from fallback file
        self._load_sessions()

        # 2. Migrate any local JSON sessions to PostgreSQL
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    for sid, s in list(self._sessions.items()):
                        try:
                            if not (s.workspace_id or "").strip():
                                continue
                            existing = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == sid).first()
                            if not existing:
                                db_row = AgentRuntimeSessionDB(
                                    id=s.id,
                                    workspace_id=s.workspace_id,
                                    title=s.title,
                                    agent_type=s.agent_type,
                                    sandbox_id=s.sandbox_id,
                                    project_id=s.project_id,
                                    status=s.status,
                                    created_at=datetime.fromisoformat(s.created_at) if s.created_at else datetime.now(timezone.utc),
                                    updated_at=datetime.fromisoformat(s.updated_at) if s.updated_at else datetime.now(timezone.utc),
                                    messages=[m.model_dump() for m in s.messages],
                                )
                                db.add(db_row)
                                db.commit()
                        except Exception as sync_err:
                            db.rollback()
                            logger.debug("[AgentRuntimeService] Migration sync item non-fatal: %s", sync_err)
        except Exception as e:
            logger.debug("[AgentRuntimeService] Initial DB sync non-fatal: %s", e)

    def list_sessions(self, workspace_id: Optional[str] = None) -> List[AgentRuntimeSession]:
        from app.agent_runtime.lifecycle.application.list_sessions import list_sessions as _action
        return _action(self, workspace_id)

    def get_session(self, session_id: str) -> Optional[AgentRuntimeSession]:
        from app.agent_runtime.lifecycle.application.get_session import get_session as _action
        return _action(self, session_id)

    def create_session(
        self, req: CreateAgentSessionRequest, workspace_id: Optional[str] = None
    ) -> AgentRuntimeSession:
        from app.agent_runtime.lifecycle.application.create_session import create_session as _action
        return _action(self, req, workspace_id)

    def delete_session(self, session_id: str) -> bool:
        from app.agent_runtime.lifecycle.application.delete_session import delete_session as _action
        return _action(self, session_id)

    def list_projects(self, workspace_id: Optional[str] = None) -> List[AgentRuntimeProject]:
        from app.agent_runtime.lifecycle.application.list_projects import list_projects as _action
        return _action(self, workspace_id)

    def get_project(self, project_id: str) -> Optional[AgentRuntimeProject]:
        from app.agent_runtime.lifecycle.application.get_project import get_project as _action
        return _action(self, project_id)

    def create_project(self, req: CreateProjectRequest, workspace_id: Optional[str] = None) -> AgentRuntimeProject:
        from app.agent_runtime.lifecycle.application.create_project import create_project as _action
        return _action(self, req, workspace_id)

    def delete_project(self, project_id: str) -> bool:
        from app.agent_runtime.lifecycle.application.delete_project import delete_project as _action
        return _action(self, project_id)

    def _load_projects(self):
        try:
            if os.path.exists(PROJECTS_STORE_PATH):
                with open(PROJECTS_STORE_PATH, "r", encoding="utf-8") as handle:
                    for item in json.load(handle):
                        project = AgentRuntimeProject(**item)
                        self._projects[project.id] = project
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to load stored projects from file: %s", e)

    def _persist_projects(self):
        try:
            os.makedirs(os.path.dirname(PROJECTS_STORE_PATH), exist_ok=True)
            with open(PROJECTS_STORE_PATH, "w", encoding="utf-8") as handle:
                json.dump([project.model_dump() for project in self._projects.values()], handle, indent=2)
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to persist projects to file fallback: %s", e)

    def send_message(self, session_id: str, content: str) -> AgentChatMessage:
        """Deliver a follow-up prompt into the session's tmux agent."""
        from app.agent_runtime.lifecycle.application.send_message import send_message as _action
        return _action(self, session_id, content)

    def _browser_key(self, session_id: str, tab_id: str) -> str:
        self._require_session(session_id)
        raw = (tab_id or "browser").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", raw):
            raise ValueError("Unknown browser tab.")
        return f"{session_id}:{raw}"

    def open_browser(self, session_id: str, tab_id: str, url: str, width: int, height: int) -> dict:
        from app.agent_runtime.lifecycle.application.open_browser import open_browser as _action
        return _action(self, session_id, tab_id, url, width, height)

    def browser_frame(self, session_id: str, tab_id: str) -> tuple[bytes, int, int]:
        from app.agent_runtime.lifecycle.application.browser_frame import browser_frame as _action
        return _action(self, session_id, tab_id)

    def inspect_browser(self, session_id: str, tab_id: str, x: float, y: float) -> dict:
        from app.agent_runtime.lifecycle.application.inspect_browser import inspect_browser as _action
        return _action(self, session_id, tab_id, x, y)

    def browser_input(self, session_id: str, tab_id: str, kind: str, x: float, y: float, delta_y: float, key_name: str, text: str) -> None:
        from app.agent_runtime.lifecycle.application.browser_input import browser_input as _action
        return _action(self, session_id, tab_id, kind, x, y, delta_y, key_name, text)

    def send_browser_note(self, session_id: str, tab_id: str, instruction: str, x: float, y: float, width: float, height: float) -> AgentChatMessage:
        """Capture the host browser and deliver the note plus screenshot to the agent."""
        from app.agent_runtime.lifecycle.application.send_browser_note import send_browser_note as _action
        return _action(self, session_id, tab_id, instruction, x, y, width, height)

    def _save_note_image(self, sandbox_id: str, data: bytes) -> str:
        self._require_running_sandbox(sandbox_id)
        path = f"/tmp/cx-notes/note-{uuid.uuid4().hex[:10]}.jpg"
        script = """
import os, json, base64
path = os.environ["CX_PATH"]
if not path.startswith("/tmp/cx-notes/"):
    raise SystemExit("refused")
os.makedirs("/tmp/cx-notes", exist_ok=True)
raw = base64.b64decode(os.environ["CX_BODY"])
with open(path, "wb") as handle:
    handle.write(raw)
print(json.dumps({"path": path, "bytes": len(raw)}))
"""
        from app.agent_runtime.workspace import _python_command

        command = _python_command(script)
        self._exec_json(
            sandbox_id,
            command,
            timeout=20,
            env={"CX_PATH": path, "CX_BODY": base64.b64encode(data).decode("ascii")},
        )
        return path

    def deliver_prompt(self, session_id: str, content: str, image: str | None = None, llm_model: str | None = None) -> AgentChatMessage:
        """Start the agent tmux session if needed, then type the prompt into it."""
        from app.agent_runtime.lifecycle.application.deliver_prompt import deliver_prompt as _action
        return _action(self, session_id, content, image, llm_model)

    def list_workspace_files(self, session_id: str) -> WorkspaceFilesResponse:
        from app.agent_runtime.lifecycle.application.list_workspace_files import list_workspace_files as _action
        return _action(self, session_id)

    def read_workspace_file(self, session_id: str, path: str) -> FileContentResponse:
        from app.agent_runtime.lifecycle.application.read_workspace_file import read_workspace_file as _action
        return _action(self, session_id, path)

    def write_workspace_file(self, session_id: str, path: str, content: str) -> WriteFileResponse:
        from app.agent_runtime.lifecycle.application.write_workspace_file import write_workspace_file as _action
        return _action(self, session_id, path, content)

    def list_workspace_changes(self, session_id: str) -> ChangesResponse:
        from app.agent_runtime.lifecycle.application.list_workspace_changes import list_workspace_changes as _action
        return _action(self, session_id)

    def read_workspace_patch(self, session_id: str) -> DiffResponse:
        from app.agent_runtime.lifecycle.application.read_workspace_patch import read_workspace_patch as _action
        return _action(self, session_id)

    def read_workspace_diff(self, session_id: str, path: str) -> DiffResponse:
        from app.agent_runtime.lifecycle.application.read_workspace_diff import read_workspace_diff as _action
        return _action(self, session_id, path)

    def _require_session(self, session_id: str) -> AgentRuntimeSession:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")
        return session

    def sandbox_git(self, sandbox_id: str) -> GitInfoResponse:
        from app.agent_runtime.lifecycle.application.sandbox_git import sandbox_git as _action
        return _action(self, sandbox_id)

    def _checkout_workspace_branch(self, sandbox_id: str, branch: str) -> None:
        self._require_running_sandbox(sandbox_id)
        result = self._exec(sandbox_id, checkout_branch_command(branch), timeout=20)
        if not result.success:
            detail = (result.stderr or result.stdout or "Failed to check out the branch.").strip()
            raise ValueError(detail[:400])

    def _require_running_sandbox(self, sandbox_id: str) -> None:
        sandbox = sandbox_service.get_sandbox(sandbox_id)
        status = sandbox.status if sandbox else None
        if isinstance(status, str):
            ready = status.lower() in (SandboxStatus.RUNNING.value, SandboxStatus.READY.value)
        else:
            ready = status in (SandboxStatus.RUNNING, SandboxStatus.READY)
        if not ready:
            current = status.value if hasattr(status, "value") else (status or "missing")
            raise RuntimeError(f"Sandbox '{sandbox_id}' is not running (status: {current}).")

    def _exec(self, sandbox_id: str, command: str, timeout: int = 30, env: dict | None = None):
        return sandbox_service.exec_in_sandbox(
            sandbox_id,
            command,
            working_dir="/workspace",
            env=env,
            timeout=timeout,
        )

    def _sync_antigravity_login(self, session: AgentRuntimeSession, *, force: bool = False) -> None:
        """Save this sandbox's Antigravity login, or restore the workspace login into it."""
        if (session.agent_type or "").lower() not in ("antigravity", "agy"):
            return
        workspace_id = (session.workspace_id or "").strip()
        if not workspace_id or not session.sandbox_id:
            return
        try:
            self._require_running_sandbox(session.sandbox_id)
        except RuntimeError:
            return
        from app.services.sandbox_credentials import sync_antigravity_for_sandbox

        def run(command: str) -> str:
            result = self._exec(session.sandbox_id, command, timeout=20)
            if not result.success and not (result.stdout or "").strip():
                detail = (result.stderr or result.stdout or "credential command failed").strip()
                raise RuntimeError(detail[:300])
            return result.stdout or ""

        sync_antigravity_for_sandbox(
            workspace_id,
            run,
            sandbox_id=session.sandbox_id,
            force=force,
        )

    def _exec_json(self, sandbox_id: str, command: str, timeout: int = 30, env: dict | None = None) -> dict:
        result = self._exec(sandbox_id, command, timeout=timeout, env=env)
        if not result.success and not (result.stdout or "").strip():
            detail = (result.stderr or result.stdout or "command failed").strip()
            raise RuntimeError(detail[:500])
        try:
            return parse_json_stdout(result.stdout or "")
        except (ValueError, json.JSONDecodeError) as exc:
            detail = (result.stderr or result.stdout or str(exc)).strip()
            raise RuntimeError(detail[:500]) from exc

    def _ensure_agent_tmux(self, session: AgentRuntimeSession) -> None:
        if is_nova_agent(session.agent_type):
            from app.agent_runtime.sandbox_controller import nova_sandbox_controller

            nova_sandbox_controller.prepare(session, self._exec, session.llm_model)
            return
        command = detached_start_command(session.agent_type, session.id, "/workspace")
        result = self._exec(session.sandbox_id, command, timeout=30)
        if not result.success:
            detail = (result.stderr or result.stdout or "Failed to start the agent.").strip()
            raise RuntimeError(detail[:500])
        self._exec(session.sandbox_id, ensure_pane_log_command(session.id), timeout=10)

    def _wait_for_agent_pane(self, session: AgentRuntimeSession, timeout: float = 15.0) -> None:
        command = pane_capture_command(session.id)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self._exec(session.sandbox_id, command, timeout=8)
            text = (result.stdout or "").strip()
            if len(re.sub(r"\s+", "", text)) >= 20:
                return
            time.sleep(0.4)

    def capture_agent_output(self, session_id: str) -> str:
        """Read the live agent pane so the chat view stays aligned with the terminal."""
        from app.agent_runtime.lifecycle.application.capture_agent_output import capture_agent_output as _action
        return _action(self, session_id)

    def _type_prompt(self, session: AgentRuntimeSession, prompt: str) -> None:
        adapter = agent_registry.get(session.agent_type)
        command = adapter.deliver_command(session.id, prompt) if adapter else deliver_prompt_command(session.id, prompt)
        result = self._exec(session.sandbox_id, command, timeout=20)
        if not result.success:
            detail = (result.stderr or result.stdout or "Failed to deliver the prompt.").strip()
            raise RuntimeError(detail[:500])

    def _append_user_message(self, session: AgentRuntimeSession, content: str) -> AgentChatMessage:
        return self._append_message(session, "user", content)

    def sync_terminal_notices(self, session_id: str) -> AgentRuntimeSession:
        """Store terminal errors that are not already in the chat."""
        from app.agent_runtime.lifecycle.application.sync_terminal_notices import sync_terminal_notices as _action
        return _action(self, session_id)

    def _read_activities(self, session: AgentRuntimeSession, adapter, pane_text: str) -> list[dict]:
        from app.sandbox.activity import activities_from_pane

        activities = [] if (session.agent_type or "").lower().strip() in ("antigravity", "agy") else list(activities_from_pane(pane_text))
        user_texts = [message.content for message in session.messages if message.role == "user" and message.content]
        command = adapter.activity_command(user_texts, session_id=session.id) if adapter else None
        if not command:
            return activities
        result = self._exec(session.sandbox_id, command, timeout=20)
        if not result.success:
            logger.debug("Agent activity command failed: %s", (result.stderr or result.stdout or "")[:300])
            return activities
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            logger.debug("Agent activity command returned invalid JSON")
            return activities
        requests: list[str] = []
        rows: list = []
        if isinstance(payload, dict):
            requests = [str(item) for item in (payload.get("requests") or [])]
            rows = payload.get("activities") or []
        elif isinstance(payload, list):
            rows = payload
        for item in rows:
            if not isinstance(item, dict):
                continue
            if requests and "requests" not in item:
                item["requests"] = requests
            activities.append(item)
        return activities

    def _sync_activities(self, session: AgentRuntimeSession, activities: list[dict]) -> None:
        for activity in activities:
            kind = str(activity.get("kind") or "")
            content = str(activity.get("content") or "").strip()
            source_id = str(activity.get("source_id") or "").strip()
            if kind not in ("thinking", "tool", "reply", "error") or not content:
                continue
            current = self._require_session(session.id)
            match = None
            for message in current.messages:
                if source_id and message.source_id == source_id:
                    match = message
                    break
                if (
                    not source_id
                    and message.kind == kind
                    and " ".join((message.content or "").split()) == " ".join(content.split())
                ):
                    match = message
                    break
            if match:
                stamp = self._activity_timestamp(current, activity)
                if match.content != content or (stamp and match.timestamp != stamp):
                    self._replace_message_content(current, match.id, content, timestamp=stamp)
                continue
            self._append_message(
                current,
                "assistant",
                content,
                kind=kind,
                source_id=source_id or None,
                timestamp=self._activity_timestamp(current, activity),
            )

    def _activity_timestamp(self, session: AgentRuntimeSession, activity: dict) -> str | None:
        """Place a transcript step just after the user message it answers."""
        requests = [" ".join(str(item).split()) for item in (activity.get("requests") or []) if str(item).strip()]
        try:
            request_index = int(activity.get("request_index"))
            order = int(activity.get("order") or 1)
        except (TypeError, ValueError):
            return None
        if request_index < 0 or request_index >= len(requests):
            return None
        users = [message for message in session.messages if message.role == "user"]
        cursor = 0
        matched: dict[int, object] = {}
        for index, request in enumerate(requests):
            scan = cursor
            while scan < len(users) and " ".join((users[scan].content or "").split()) != request:
                scan += 1
            if scan >= len(users):
                continue
            matched[index] = users[scan]
            cursor = scan + 1
        target = matched.get(request_index)
        if target is None:
            return None
        try:
            base = datetime.fromisoformat(target.timestamp)
        except ValueError:
            return None
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return (base + timedelta(milliseconds=max(order, 1))).isoformat()

    def _drop_terminal_errors(self, session: AgentRuntimeSession) -> None:
        with self._lock:
            current = self._sessions.get(session.id) or session
            kept = [message for message in current.messages if message.kind != "error"]
            if len(kept) == len(current.messages):
                return
            current.messages = kept
            now_utc = datetime.now(timezone.utc)
            current.updated_at = now_utc.isoformat()
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session.id).first()
                        if row:
                            row.messages = [message.model_dump() for message in kept]
                            row.updated_at = now_utc
                            db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to drop terminal error notices: %s", db_err)
            self._sessions[session.id] = current
            self._persist_sessions()

    def _collapse_duplicate_notices(self, session: AgentRuntimeSession) -> None:
        seen: list[str] = []
        kept_ids: set[str] = set()
        errors = [
            message
            for message in session.messages
            if message.role == "assistant"
            and message.kind not in ("thinking", "tool", "reply")
            and not (message.content or "").startswith("👋")
        ]
        for message in sorted(errors, key=lambda item: len(item.content or ""), reverse=True):
            if _notice_already_shown(message.content, seen):
                continue
            seen.append(message.content)
            kept_ids.add(message.id)
        kept = []
        changed = False
        for message in session.messages:
            if (
                message.role == "assistant"
                and message.kind not in ("thinking", "tool", "reply")
                and not (message.content or "").startswith("👋")
                and message.id not in kept_ids
            ):
                changed = True
                continue
            kept.append(message)
        if not changed:
            return
        with self._lock:
            current = self._sessions.get(session.id) or session
            current.messages = kept
            now_utc = datetime.now(timezone.utc)
            current.updated_at = now_utc.isoformat()
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session.id).first()
                        if row:
                            row.messages = [message.model_dump() for message in kept]
                            row.updated_at = now_utc
                            db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to collapse duplicate notices: %s", db_err)
            self._sessions[session.id] = current
            self._persist_sessions()

    def _replace_message_content(self, session: AgentRuntimeSession, message_id: str, content: str, timestamp: str | None = None) -> None:
        with self._lock:
            current = self._sessions.get(session.id) or session
            for message in current.messages:
                if message.id == message_id:
                    message.content = content
                    if timestamp:
                        message.timestamp = timestamp
                    break
            now_utc = datetime.now(timezone.utc)
            current.updated_at = now_utc.isoformat()
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session.id).first()
                        if row:
                            row.messages = [message.model_dump() for message in current.messages]
                            row.updated_at = now_utc
                            db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to update an activity message: %s", db_err)
            self._sessions[session.id] = current
            self._persist_sessions()

    def _is_nova(self, session: AgentRuntimeSession) -> bool:
        return is_nova_agent(session.agent_type)

    def _persist_session_row(self, session: AgentRuntimeSession) -> None:
        now_utc = datetime.now(timezone.utc)
        session.updated_at = now_utc.isoformat()
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session.id).first()
                    if row:
                        row.status = session.status
                        row.llm_model = session.llm_model
                        row.nova_chat_session_id = session.nova_chat_session_id
                        row.messages = [m.model_dump() for m in session.messages]
                        row.updated_at = now_utc
                        db.commit()
        except Exception as db_err:
            logger.warning("[AgentRuntimeService] Failed to persist session row: %s", db_err)
        with self._lock:
            self._sessions[session.id] = session
            self._persist_sessions()

    def _deliver_nova(self, session: AgentRuntimeSession, prompt: str, image: str | None = None, llm_model: str | None = None) -> AgentChatMessage:
        from app.agent_runtime.sandbox_controller import nova_sandbox_controller

        user_msg = self._append_message(session, "user", prompt, image=image)
        nova_sandbox_controller.deliver(session, prompt, self._exec, llm_model=llm_model or session.llm_model)
        return user_msg

    def _append_message(
        self,
        session: AgentRuntimeSession,
        role: str,
        content: str,
        kind: str | None = None,
        source_id: str | None = None,
        timestamp: str | None = None,
        image: str | None = None,
    ) -> AgentChatMessage:
        user_msg = AgentChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role=role,
            content=content,
            kind=kind,
            source_id=source_id,
            image=image,
            **({"timestamp": timestamp} if timestamp else {}),
        )
        with self._lock:
            current = self._sessions.get(session.id) or session
            current.messages.append(user_msg)
            now_utc = datetime.now(timezone.utc)
            current.updated_at = now_utc.isoformat()
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session.id).first()
                        if row:
                            row.messages = [m.model_dump() for m in current.messages]
                            row.updated_at = now_utc
                            db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to persist messages to DB: %s", db_err)
            self._sessions[session.id] = current
            self._persist_sessions()
        return user_msg


agent_runtime_service = AgentRuntimeService()
