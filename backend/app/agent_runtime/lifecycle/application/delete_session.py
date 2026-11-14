from __future__ import annotations

def delete_session(service, session_id: str) -> bool:
    import app.agent_runtime.service as _origin
    AgentRuntimeSessionDB = _origin.AgentRuntimeSessionDB
    logger = _origin.logger
    with service._lock:
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

        if session_id in service._sessions:
            del service._sessions[session_id]
            service._persist_sessions()
            deleted = True

        return deleted
