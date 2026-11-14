from __future__ import annotations

def list_projects(service, workspace_id: Optional[str] = None) -> List[AgentRuntimeProject]:
    import app.agent_runtime.service as _origin
    AgentRuntimeProjectDB = _origin.AgentRuntimeProjectDB
    logger = _origin.logger
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
                with service._lock:
                    for project in projects:
                        service._projects[project.id] = project
                return projects
    except Exception as e:
        logger.warning("[AgentRuntimeService] Failed to query projects from DB, falling back to memory: %s", e)

    with service._lock:
        projects = list(service._projects.values())
        if workspace_id:
            projects = [project for project in projects if not project.workspace_id or project.workspace_id == workspace_id]
        return sorted(projects, key=lambda project: project.updated_at, reverse=True)
