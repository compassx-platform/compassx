"""Agent Runtime Service — orchestrates agent sessions bound to compute sandboxes."""
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.agent_runtime.models import (
    AgentChatMessage,
    AgentRuntimeSession,
    AgentRuntimeSessionDB,
    CreateAgentSessionRequest,
)
from app.sandbox.models import SandboxSpec
from app.sandbox.service import sandbox_service

logger = logging.getLogger(__name__)

SESSIONS_STORE_PATH = os.path.join(
    os.path.expanduser("~"), ".compassx", "agent_runtime_sessions.json"
)


class AgentRuntimeService:
    """Manages agent runtime sessions, their immutable sandbox bindings, and chat interactions with PostgreSQL persistence."""

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, AgentRuntimeSession] = {}
        self._ensure_table_exists()
        self._sync_and_load_sessions()

    def _ensure_table_exists(self):
        try:
            from app.database import system_engine, SystemBase
            if system_engine is not None:
                SystemBase.metadata.create_all(bind=system_engine, tables=[AgentRuntimeSessionDB.__table__], checkfirst=True)
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
            clean_agent = (req.agent_type or "antigravity").lower().strip()
            if clean_agent not in ("antigravity", "pi", "opencode", "bash"):
                clean_agent = "antigravity"

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

            # 2. Prepare welcome message based on agent type
            agent_names = {
                "antigravity": "Google Antigravity (agy)",
                "pi": "Pi Coding Agent",
                "opencode": "OpenCode AI",
                "bash": "Shell Terminal",
            }
            display_name = agent_names.get(clean_agent, clean_agent.capitalize())

            greeting = (
                f"👋 Hello! I am **{display_name}**.\n\n"
                f"I am actively attached to your compute sandbox (`{bound_sandbox_id}`) in `/workspace`.\n\n"
                f"- Ask me to examine files, write code, run commands, or perform refactoring.\n"
                f"- Switch to the **Terminal** tab anytime to interact directly with the live shell or run commands in real time."
            )

            welcome_msg = AgentChatMessage(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                role="assistant",
                content=greeting,
            )

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
                status=init_status,
                created_at=now_utc.isoformat(),
                updated_at=now_utc.isoformat(),
                messages=[welcome_msg],
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
                            status=init_status,
                            created_at=now_utc,
                            updated_at=now_utc,
                            messages=[welcome_msg.model_dump()],
                        )
                        db.add(db_row)
                        db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to save session to DB: %s", db_err)

            self._sessions[session_id] = session
            self._persist_sessions()
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

    def send_message(self, session_id: str, content: str) -> AgentChatMessage:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                session = self.get_session(session_id)
            if not session:
                raise ValueError(f"Session '{session_id}' not found.")

            # 1. Append user message
            user_msg = AgentChatMessage(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                role="user",
                content=content.strip(),
            )
            session.messages.append(user_msg)

            # 2. Generate agent response
            agent_resp = self._generate_agent_reply(session, content.strip())
            session.messages.append(agent_resp)
            now_utc = datetime.now(timezone.utc)
            session.updated_at = now_utc.isoformat()

            # 3. Persist updated messages to PostgreSQL
            try:
                from app.database import SystemSessionLocal
                if SystemSessionLocal is not None:
                    with SystemSessionLocal() as db:
                        row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session_id).first()
                        if row:
                            row.messages = [m.model_dump() for m in session.messages]
                            row.updated_at = now_utc
                            db.commit()
            except Exception as db_err:
                logger.warning("[AgentRuntimeService] Failed to persist messages to DB: %s", db_err)

            self._sessions[session_id] = session
            self._persist_sessions()
            return agent_resp



    def _generate_agent_reply(self, session: AgentRuntimeSession, user_input: str) -> AgentChatMessage:
        agent_type = session.agent_type
        sandbox_id = session.sandbox_id

        # Quick command execution check (e.g. if user starts with $ or runs bash command)
        if user_input.startswith("$"):
            raw_cmd = user_input[1:].strip()
            exec_res = sandbox_service.exec_command(sandbox_id, raw_cmd, timeout=30)
            output = exec_res.stdout or exec_res.stderr or f"[Process exited with code {exec_res.exit_code}]"
            reply_text = f"**Executed in Sandbox (`{sandbox_id}`):**\n```bash\n$ {raw_cmd}\n{output}\n```"
        else:
            # Check sandbox status
            sb = sandbox_service.get_sandbox(sandbox_id)
            sb_status = sb.status.value if sb else "unknown"

            agent_names = {
                "antigravity": "Google Antigravity",
                "pi": "Pi Coding Agent",
                "opencode": "OpenCode AI",
                "bash": "Shell Terminal",
            }
            display_name = agent_names.get(agent_type, agent_type.capitalize())

            reply_text = (
                f"**[{display_name} Response]**\n\n"
                f"I processed your request: *\"{user_input}\"* inside sandbox `{sandbox_id}` (Status: `{sb_status}`).\n\n"
                f"You can switch to the **Terminal** tab to verify filesystem changes, run tests, or invoke `{session.agent_type}` directly from the shell prompt."
            )

        return AgentChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role="assistant",
            content=reply_text,
        )


agent_runtime_service = AgentRuntimeService()
