from __future__ import annotations

def get_project(service, project_id: str) -> Optional[AgentRuntimeProject]:
    import app.agent_runtime.service as _origin
    AgentRuntimeProjectDB = _origin.AgentRuntimeProjectDB
    logger = _origin.logger
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                row = db.query(AgentRuntimeProjectDB).filter(AgentRuntimeProjectDB.id == project_id).first()
                if row:
                    project = row.to_pydantic()
                    with service._lock:
                        service._projects[project.id] = project
                    return project
    except Exception as e:
        logger.warning("[AgentRuntimeService] Failed to get project from DB, falling back to memory: %s", e)

    with service._lock:
        return service._projects.get(project_id)
