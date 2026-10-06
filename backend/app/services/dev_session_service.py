from __future__ import annotations

import logging
import re
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database import SystemSessionLocal
from app.models.app import App
from app.models.dev_session import DevSession

logger = logging.getLogger(__name__)

SUPPORTED_AGENTS = ("opencode", "pi", "antigravity", "bash")


class DevSessionService:
    """Manages persistent App development sessions and native agent bridging."""

    def _normalize_agent(self, agent: str) -> str:
        clean = (agent or "opencode").strip().lower()
        if clean in ("bash", "shell", "sh", "terminal"):
            return "bash"
        if clean in ("agy", "antigravity"):
            return "antigravity"
        if clean in ("pi", "pi-coding-agent"):
            return "pi"
        return "opencode"

    def _generate_external_session_id(self, agent: str) -> str:
        """Mint a clean native session ID accepted by the agent CLI."""
        if agent == "bash":
            return f"sh_{uuid.uuid4().hex[:8]}"
        elif agent == "pi":
            return str(uuid.uuid4())
        elif agent == "antigravity":
            return str(uuid.uuid4())
        else:  # opencode
            return f"oc_{uuid.uuid4().hex[:12]}"

    def _format_tmux_session_name(self, app_id: str, session_id: str) -> str:
        clean_app = re.sub(r"[^a-zA-Z0-9_-]", "-", app_id).strip("-").lower()[:16]
        clean_sess = re.sub(r"[^a-zA-Z0-9_-]", "-", session_id).strip("-").lower()[:20]
        return f"cx_{clean_app}_{clean_sess}"

    def get_session_cli_command(self, session: DevSession) -> str:
        """Assemble the native agent launch command with its persistent session flags."""
        if session.agent == "bash":
            return "exec /bin/bash -l"
        ext_id = session.external_session_id or self._generate_external_session_id(session.agent)
        model = getattr(session, "model", None) or "gpt-5.4-mini"
        if session.agent == "pi":
            return f"pi --session-id {ext_id} --provider compassx --approve --model {model}"
        elif session.agent == "antigravity":
            model_flag = f" --model {model}" if getattr(session, "model", None) else ""
            return f"agy --dangerously-skip-permissions{model_flag}"
        else:  # opencode
            return f"OPENCODE_MODEL={model} opencode -m compassx/{model}"

    def serialize_session(self, session: DevSession) -> Dict[str, Any]:
        return {
            "id": session.id,
            "app_id": session.app_id,
            "workspace_id": session.workspace_id,
            "title": session.title,
            "agent": session.agent,
            "model": getattr(session, "model", None),
            "external_session_id": session.external_session_id,
            "tmux_session_name": session.tmux_session_name,
            "status": session.status,
            "created_by": session.created_by,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
        }

    def list_sessions(self, app: App, include_archived: bool = False) -> List[Dict[str, Any]]:
        """List all development sessions for a given app."""
        with SystemSessionLocal() as db:
            query = db.query(DevSession).filter(DevSession.app_id == app.id)
            if not include_archived:
                query = query.filter(DevSession.status != "archived")
            sessions = query.order_by(
                DevSession.last_active_at.desc().nullslast(),
                DevSession.created_at.desc(),
            ).all()

            # If no sessions exist for this app yet, create a default one
            if not sessions and not include_archived:
                default_session = self._create_session_internal(
                    db=db,
                    app=app,
                    agent="opencode",
                    title="Default Session (OpenCode)",
                )
                return [self.serialize_session(default_session)]

            return [self.serialize_session(s) for s in sessions]

    def get_session(self, app: App, session_id: str) -> Optional[DevSession]:
        """Fetch a specific session for an app."""
        with SystemSessionLocal() as db:
            return (
                db.query(DevSession)
                .filter(DevSession.app_id == app.id, DevSession.id == session_id)
                .first()
            )

    def _create_session_internal(
        self,
        db,
        app: App,
        agent: str,
        title: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> DevSession:
        norm_agent = self._normalize_agent(agent)
        sess_id = f"sess_{uuid.uuid4().hex[:16]}"
        ext_sess_id = self._generate_external_session_id(norm_agent)
        tmux_name = self._format_tmux_session_name(app.id, sess_id)

        clean_title = (title or "").strip()
        if not clean_title:
            agent_display = {
                "opencode": "OpenCode",
                "pi": "Pi",
                "antigravity": "Antigravity",
                "agy": "Antigravity",
                "bash": "Bash Shell",
            }.get(norm_agent, norm_agent.capitalize())
            clean_title = f"Session with {agent_display}"

        dev_session = DevSession(
            id=sess_id,
            app_id=app.id,
            workspace_id=workspace_id,
            title=clean_title,
            agent=norm_agent,  # Immutable once created
            model=model.strip() if (model and model.strip()) else None,
            external_session_id=ext_sess_id,
            tmux_session_name=tmux_name,
            status="active",
            created_by=user_id,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(dev_session)
        db.commit()
        db.refresh(dev_session)
        return dev_session

    def create_session(
        self,
        app: App,
        agent: str,
        title: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new session bound to a single agent for an App."""
        with SystemSessionLocal() as db:
            session = self._create_session_internal(
                db=db,
                app=app,
                agent=agent,
                title=title,
                workspace_id=workspace_id,
                user_id=user_id,
                model=model,
            )
            return self.serialize_session(session)

    def update_session(
        self,
        app: App,
        session_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update session title or status (agent is strictly immutable)."""
        with SystemSessionLocal() as db:
            session = (
                db.query(DevSession)
                .filter(DevSession.app_id == app.id, DevSession.id == session_id)
                .first()
            )
            if not session:
                raise ValueError(f"Session '{session_id}' not found for app '{app.id}'.")

            if title is not None and title.strip():
                session.title = title.strip()
            if status is not None and status.strip():
                session.status = status.strip().lower()

            session.last_active_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)
            return self.serialize_session(session)

    def delete_session(self, app: App, session_id: str) -> Dict[str, Any]:
        """Archive a session and terminate its container tmux session."""
        with SystemSessionLocal() as db:
            session = (
                db.query(DevSession)
                .filter(DevSession.app_id == app.id, DevSession.id == session_id)
                .first()
            )
            if not session:
                return {"deleted": False, "reason": "not_found"}

            session.status = "archived"
            db.commit()

            # Attempt to kill the tmux session in the running container
            dev_container_name = f"compassx-app-dev-{app.id}"
            try:
                base_name = session.tmux_session_name
                subprocess.run(
                    [
                        "docker", "exec", dev_container_name, "bash", "-c",
                        f"for s in $(tmux list-sessions -F '#{{session_name}}' 2>/dev/null); do if [[ \"$s\" == {base_name}* ]]; then tmux kill-session -t \"$s\" 2>/dev/null; fi; done",
                    ],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass

            return {"deleted": True, "session_id": session_id}

    def touch_session(self, app_id: str, session_id: str) -> None:
        """Update last_active_at timestamp for a session."""
        try:
            with SystemSessionLocal() as db:
                session = (
                    db.query(DevSession)
                    .filter(DevSession.app_id == app_id, DevSession.id == session_id)
                    .first()
                )
                if session:
                    session.last_active_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as e:
            logger.debug("Failed to touch session activity: %s", e)


dev_session_service = DevSessionService()
