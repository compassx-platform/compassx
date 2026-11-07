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
        self._ensure_table_exists()
        self._sync_and_load_sessions()
        self._load_projects()

    def _ensure_table_exists(self):
        try:
            from sqlalchemy import text
            from app.database import system_engine, SystemBase
            if system_engine is not None:
                SystemBase.metadata.create_all(
                    bind=system_engine,
                    tables=[AgentRuntimeProjectDB.__table__, AgentRuntimeSessionDB.__table__],
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
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    query = db.query(AgentRuntimeSessionDB)
                    if workspace_id:
                        query = query.filter(
                            (AgentRuntimeSessionDB.workspace_id == workspace_id) |
                            (AgentRuntimeSessionDB.workspace_id.is_(None))
                        )
                    rows = query.order_by(AgentRuntimeSessionDB.updated_at.desc()).all()
                    db_sessions = [r.to_pydantic() for r in rows]
                    with self._lock:
                        for s in db_sessions:
                            self._sessions[s.id] = s
                    return db_sessions
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to query sessions from DB, falling back to memory: %s", e)

        with self._lock:
            sessions = list(self._sessions.values())
            if workspace_id:
                sessions = [s for s in sessions if not s.workspace_id or s.workspace_id == workspace_id]
            return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def get_session(self, session_id: str) -> Optional[AgentRuntimeSession]:
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session_id).first()
                    if row:
                        sess = row.to_pydantic()
                        with self._lock:
                            self._sessions[sess.id] = sess
                        return sess
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to get session from DB, falling back to memory: %s", e)

        with self._lock:
            return self._sessions.get(session_id)

    def create_session(
        self, req: CreateAgentSessionRequest, workspace_id: Optional[str] = None
    ) -> AgentRuntimeSession:
        with self._lock:
            session_id = f"ars_{uuid.uuid4().hex[:12]}"
            clean_title = (req.title or "").strip() or "Agent Session"
            clean_agent = (req.agent_type or "nova").lower().strip()
            if clean_agent == "agy":
                clean_agent = "antigravity"
            elif clean_agent in ("claude-code", "claudecode"):
                clean_agent = "claude"
            elif clean_agent in ("cursor-agent", "cursorcli"):
                clean_agent = "cursor"
            elif clean_agent in ("compassx", "compass"):
                clean_agent = "nova"
            known = {item["id"] for item in agent_registry.catalog()}
            known.update({"bash"})
            if clean_agent not in known:
                clean_agent = "nova"
            llm_model = (req.llm_model or "").strip() or None
            project_id = (req.project_id or "").strip() or None
            if project_id and not self.get_project(project_id):
                raise ValueError(f"Project '{project_id}' does not exist.")

            bound_sandbox_id: str = ""

            instance = None
            # 1. Resolve or provision the bound sandbox
            if req.sandbox_mode == "existing" and req.sandbox_id:
                existing = sandbox_service.get_sandbox(req.sandbox_id)
                if not existing:
                    raise ValueError(f"Selected sandbox '{req.sandbox_id}' does not exist.")
                bound_sandbox_id = existing.id
                instance = existing
            else:
                # Provision a new sandbox running compassx-sandbox-host
                spec = SandboxSpec(
                    name=f"{clean_title} ({clean_agent.capitalize()})",
                    consumer_module="agent",
                    image=os.environ.get("COMPASSX_SANDBOX_IMAGE") or "ghcr.io/compassx-platform/compassx-sandbox-host:latest",
                    ports=[8080],
                    working_dir="/workspace",
                    workspace_id=workspace_id,
                )
                instance = sandbox_service.ensure_sandbox(spec)
                bound_sandbox_id = instance.id

            branch = (req.branch or "").strip()
            if branch and req.sandbox_mode == "existing" and bound_sandbox_id:
                self._checkout_workspace_branch(bound_sandbox_id, branch)

            init_status = "active"
            if hasattr(instance, "status"):
                status_val = instance.status.value if hasattr(instance.status, "value") else str(instance.status)
                if status_val in ("failed", "provisioning"):
                    init_status = status_val

            now_utc = datetime.now(timezone.utc)
            session = AgentRuntimeSession(
                id=session_id,
                workspace_id=workspace_id,
                title=clean_title,
                agent_type=clean_agent,
                sandbox_id=bound_sandbox_id,
                project_id=project_id,
                llm_model=llm_model,
                status=init_status,
                created_at=now_utc.isoformat(),
                updated_at=now_utc.isoformat(),
                messages=[],
            )

            # Persist to PostgreSQL
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        db_row = AgentRuntimeSessionDB(
                            id=session_id,
                            workspace_id=workspace_id,
                            title=clean_title,
                            agent_type=clean_agent,
                            sandbox_id=bound_sandbox_id,
                            project_id=project_id,
                            llm_model=llm_model,
                            status=init_status,
                            created_at=now_utc,
                            updated_at=now_utc,
                            messages=[],
                        )
                        db.add(db_row)
                        db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to save session to DB: %s", db_err)

            self._sessions[session_id] = session
            self._persist_sessions()
            if clean_agent == "antigravity":
                self._sync_antigravity_login(session, force=True)
            return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            deleted = False
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session_id).first()
                        if row:
                            db.delete(row)
                            db.commit()
                            deleted = True
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to delete session from DB: %s", db_err)

            if session_id in self._sessions:
                del self._sessions[session_id]
                self._persist_sessions()
                deleted = True

            return deleted

    def list_projects(self, workspace_id: Optional[str] = None) -> List[AgentRuntimeProject]:
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    query = db.query(AgentRuntimeProjectDB)
                    if workspace_id:
                        query = query.filter(
                            (AgentRuntimeProjectDB.workspace_id == workspace_id) |
                            (AgentRuntimeProjectDB.workspace_id.is_(None))
                        )
                    rows = query.order_by(AgentRuntimeProjectDB.updated_at.desc()).all()
                    projects = [row.to_pydantic() for row in rows]
                    with self._lock:
                        for project in projects:
                            self._projects[project.id] = project
                    return projects
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to query projects from DB, falling back to memory: %s", e)

        with self._lock:
            projects = list(self._projects.values())
            if workspace_id:
                projects = [project for project in projects if not project.workspace_id or project.workspace_id == workspace_id]
            return sorted(projects, key=lambda project: project.updated_at, reverse=True)

    def get_project(self, project_id: str) -> Optional[AgentRuntimeProject]:
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    row = db.query(AgentRuntimeProjectDB).filter(AgentRuntimeProjectDB.id == project_id).first()
                    if row:
                        project = row.to_pydantic()
                        with self._lock:
                            self._projects[project.id] = project
                        return project
        except Exception as e:
            logger.warning("[AgentRuntimeService] Failed to get project from DB, falling back to memory: %s", e)

        with self._lock:
            return self._projects.get(project_id)

    def create_project(self, req: CreateProjectRequest, workspace_id: Optional[str] = None) -> AgentRuntimeProject:
        name = (req.name or "").strip()
        if not name:
            raise ValueError("Project name is empty.")
        if len(name) > 80:
            name = name[:80]
        now_utc = datetime.now(timezone.utc)
        project = AgentRuntimeProject(
            id=f"arp_{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            name=name,
            created_at=now_utc.isoformat(),
            updated_at=now_utc.isoformat(),
        )
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    db.add(AgentRuntimeProjectDB(
                        id=project.id,
                        workspace_id=workspace_id,
                        name=name,
                        created_at=now_utc,
                        updated_at=now_utc,
                    ))
                    db.commit()
        except Exception as db_err:
            logger.warning("[AgentRuntimeService] Failed to save project to DB: %s", db_err)

        with self._lock:
            self._projects[project.id] = project
            self._persist_projects()
        return project

    def delete_project(self, project_id: str) -> bool:
        deleted = False
        now_utc = datetime.now(timezone.utc)
        try:
            from app.database import SystemSessionLocal
            if SystemSessionLocal is not None:
                with SystemSessionLocal() as db:
                    row = db.query(AgentRuntimeProjectDB).filter(AgentRuntimeProjectDB.id == project_id).first()
                    if row:
                        db.query(AgentRuntimeSessionDB).filter(
                            AgentRuntimeSessionDB.project_id == project_id
                        ).update({AgentRuntimeSessionDB.project_id: None, AgentRuntimeSessionDB.updated_at: now_utc})
                        db.delete(row)
                        db.commit()
                        deleted = True
        except Exception as db_err:
            logger.warning("[AgentRuntimeService] Failed to delete project from DB: %s", db_err)

        with self._lock:
            if project_id in self._projects:
                del self._projects[project_id]
                deleted = True
            for session in self._sessions.values():
                if session.project_id == project_id:
                    session.project_id = None
                    session.updated_at = now_utc.isoformat()
            self._persist_projects()
            self._persist_sessions()
        return deleted

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
        return self.deliver_prompt(session_id, content)

    def _browser_key(self, session_id: str, tab_id: str) -> str:
        self._require_session(session_id)
        raw = (tab_id or "browser").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", raw):
            raise ValueError("Unknown browser tab.")
        return f"{session_id}:{raw}"

    def open_browser(self, session_id: str, tab_id: str, url: str, width: int, height: int) -> dict:
        from app.agent_runtime.browser_host import browser_host

        return browser_host.open(self._browser_key(session_id, tab_id), url, width, height)

    def browser_frame(self, session_id: str, tab_id: str) -> tuple[bytes, int, int]:
        from app.agent_runtime.browser_host import browser_host

        return browser_host.frame(self._browser_key(session_id, tab_id))

    def inspect_browser(self, session_id: str, tab_id: str, x: float, y: float) -> dict:
        from app.agent_runtime.browser_host import browser_host

        return browser_host.inspect(self._browser_key(session_id, tab_id), x, y)

    def browser_input(self, session_id: str, tab_id: str, kind: str, x: float, y: float, delta_y: float, key_name: str, text: str) -> None:
        from app.agent_runtime.browser_host import browser_host

        browser_host.input(self._browser_key(session_id, tab_id), kind, x, y, delta_y, key_name, text)

    def send_browser_note(self, session_id: str, tab_id: str, instruction: str, x: float, y: float, width: float, height: float) -> AgentChatMessage:
        """Capture the host browser and deliver the note plus screenshot to the agent."""
        from app.agent_runtime.browser_host import browser_host

        note = (instruction or "").strip()
        if not note:
            raise ValueError("Message is empty.")
        shot, target = browser_host.capture(self._browser_key(session_id, tab_id), x, y, width, height)
        session = self._require_session(session_id)
        path = ""
        try:
            path = self._save_note_image(session.sandbox_id, shot)
        except Exception as exc:
            logger.warning("[AgentRuntimeService] Could not store the annotation screenshot: %s", exc)
        prompt = f"Browser annotation\n{target['detail']}\n\n{note}"
        if path:
            prompt += f"\n\nScreenshot file: {path}\nRead that screenshot file before changing the page."
        image = "data:image/jpeg;base64," + base64.b64encode(shot).decode("ascii")
        return self.deliver_prompt(session_id, prompt, image=image)

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
        session = self._require_session(session_id)
        prompt = (content or "").strip()
        if not prompt:
            raise ValueError("Message is empty.")
        self._require_running_sandbox(session.sandbox_id)
        if llm_model and llm_model.strip():
            session.llm_model = llm_model.strip()
            self._persist_session_row(session)
        if is_nova_agent(session.agent_type):
            return self._deliver_nova(session, prompt, image=image, llm_model=llm_model)
        self._sync_antigravity_login(session, force=True)
        self._ensure_agent_tmux(session)
        self._wait_for_agent_pane(session)
        self._type_prompt(session, prompt)
        return self._append_message(session, "user", prompt, image=image)

    def list_workspace_files(self, session_id: str) -> WorkspaceFilesResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        payload = self._exec_json(session.sandbox_id, files_command(), timeout=30)
        entries = [
            WorkspaceEntry(
                path=str(item.get("path") or ""),
                type=str(item.get("type") or "file"),
                size=int(item.get("size") or 0),
            )
            for item in payload.get("entries") or []
            if item.get("path")
        ]
        return WorkspaceFilesResponse(root=str(payload.get("root") or "/workspace"), entries=entries)

    def read_workspace_file(self, session_id: str, path: str) -> FileContentResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        relative = safe_relative_path(path)
        payload = self._exec_json(session.sandbox_id, file_content_command(relative), timeout=20)
        return FileContentResponse(
            path=str(payload.get("path") or relative),
            content=str(payload.get("content") or ""),
            truncated=bool(payload.get("truncated")),
            missing=bool(payload.get("missing")),
        )

    def write_workspace_file(self, session_id: str, path: str, content: str) -> WriteFileResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        relative = safe_relative_path(path)
        payload = self._exec_json(session.sandbox_id, write_file_command(relative, content or ""), timeout=30)
        return WriteFileResponse(path=str(payload.get("path") or relative), bytes=int(payload.get("bytes") or 0))

    def list_workspace_changes(self, session_id: str) -> ChangesResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        payload = self._exec_json(session.sandbox_id, changes_command(), timeout=30)
        entries = [
            ChangeEntry(
                path=str(item.get("path") or ""),
                status=str(item.get("status") or "modified"),
                additions=int(item.get("additions") or 0),
                deletions=int(item.get("deletions") or 0),
                staged=bool(item.get("staged")),
                unstaged=bool(item.get("unstaged", True)),
            )
            for item in payload.get("entries") or []
            if item.get("path")
        ]
        commits = [
            CommitEntry(
                hash=str(item.get("hash") or ""),
                subject=str(item.get("subject") or ""),
                author=str(item.get("author") or ""),
                date=str(item.get("date") or ""),
            )
            for item in payload.get("commits") or []
            if item.get("hash")
        ]
        return ChangesResponse(entries=entries, branch=str(payload.get("branch") or ""), commits=commits)

    def read_workspace_patch(self, session_id: str) -> DiffResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        payload = self._exec_json(session.sandbox_id, patch_command(), timeout=30)
        return DiffResponse(path="", diff=str(payload.get("diff") or ""))

    def read_workspace_diff(self, session_id: str, path: str) -> DiffResponse:
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        relative = safe_relative_path(path)
        payload = self._exec_json(session.sandbox_id, diff_command(relative), timeout=30)
        return DiffResponse(path=str(payload.get("path") or relative), diff=str(payload.get("diff") or ""))

    def _require_session(self, session_id: str) -> AgentRuntimeSession:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")
        return session

    def sandbox_git(self, sandbox_id: str) -> GitInfoResponse:
        self._require_running_sandbox(sandbox_id)
        payload = self._exec_json(sandbox_id, git_info_command(), timeout=15)
        branches = [str(name) for name in (payload.get("branches") or []) if name]
        return GitInfoResponse(
            repo=bool(payload.get("repo")),
            branch=str(payload.get("branch") or ""),
            branches=branches,
        )

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
        session = self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        result = self._exec(session.sandbox_id, pane_capture_command(session.id), timeout=10)
        return result.stdout or ""

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
        session = self._require_session(session_id)
        if is_nova_agent(session.agent_type):
            self._require_running_sandbox(session.sandbox_id)
            from app.agent_runtime.sandbox_controller import nova_sandbox_controller

            self._sync_activities(session, nova_sandbox_controller.read_activities(session, self._exec))
            return self._require_session(session_id)
        self._require_running_sandbox(session.sandbox_id)
        self._sync_antigravity_login(session)
        self._exec(session.sandbox_id, ensure_pane_log_command(session.id), timeout=10)
        captured = self._exec(session.sandbox_id, pane_capture_command(session.id, 200), timeout=10)
        logged = self._exec(session.sandbox_id, read_pane_log_command(session.id), timeout=10)
        pane_text = f"{captured.stdout or ''}\n{logged.stdout or ''}"
        adapter = agent_registry.get(session.agent_type)
        # Antigravity already emits thoughts, tool calls, and replies from its transcript.
        # The pane scrape treats status lines such as "2 failed" as errors and copies the reply into them.
        if (session.agent_type or "").lower().strip() in ("antigravity", "agy"):
            self._drop_terminal_errors(session)
            notices = []
        else:
            notices = list(dict.fromkeys(adapter.extract_notices(pane_text) if adapter else []))
        self._collapse_duplicate_notices(session)
        session = self._require_session(session_id)
        self._sync_activities(session, self._read_activities(session, adapter, pane_text))
        session = self._require_session(session_id)
        stored = {
            message.content
            for message in session.messages
            if message.role == "assistant" and (message.kind in (None, "", "error")) and not (message.content or "").startswith("👋")
        }
        for notice in notices:
            if _notice_already_shown(notice, stored):
                continue
            self._append_message(session, "assistant", notice, kind="error")
            stored.add(notice)
        return self._require_session(session_id)

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
