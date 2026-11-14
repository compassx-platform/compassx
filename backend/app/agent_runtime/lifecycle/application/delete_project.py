from __future__ import annotations

def delete_project(service, project_id: str) -> bool:
    import app.agent_runtime.service as _origin
    datetime = _origin.datetime
    timezone = _origin.timezone
    AgentRuntimeProjectDB = _origin.AgentRuntimeProjectDB
    AgentRuntimeSessionDB = _origin.AgentRuntimeSessionDB
    logger = _origin.logger
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

    with service._lock:
        if project_id in service._projects:
            del service._projects[project_id]
            deleted = True
        for session in service._sessions.values():
            if session.project_id == project_id:
                session.project_id = None
                session.updated_at = now_utc.isoformat()
        service._persist_projects()
        service._persist_sessions()
    return deleted
