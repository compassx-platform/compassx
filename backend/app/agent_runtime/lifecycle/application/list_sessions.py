from __future__ import annotations

def list_sessions(service, workspace_id: Optional[str] = None) -> List[AgentRuntimeSession]:
    import app.agent_runtime.service as _origin
    AgentRuntimeSessionDB = _origin.AgentRuntimeSessionDB
    logger = _origin.logger
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
                with service._lock:
                    for s in db_sessions:
                        service._sessions[s.id] = s
                return db_sessions
    except Exception as e:
        logger.warning("[AgentRuntimeService] Failed to query sessions from DB, falling back to memory: %s", e)

    with service._lock:
        sessions = list(service._sessions.values())
        if workspace_id:
            sessions = [s for s in sessions if not s.workspace_id or s.workspace_id == workspace_id]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
