from __future__ import annotations

def get_session(service, session_id: str) -> Optional[AgentRuntimeSession]:
    import app.agent_runtime.service as _origin
    AgentRuntimeSessionDB = _origin.AgentRuntimeSessionDB
    logger = _origin.logger
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                row = db.query(AgentRuntimeSessionDB).filter(AgentRuntimeSessionDB.id == session_id).first()
                if row:
                    sess = row.to_pydantic()
                    with service._lock:
                        service._sessions[sess.id] = sess
                    return sess
    except Exception as e:
        logger.warning("[AgentRuntimeService] Failed to get session from DB, falling back to memory: %s", e)

    with service._lock:
        return service._sessions.get(session_id)
