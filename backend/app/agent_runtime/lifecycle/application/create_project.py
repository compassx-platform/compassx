from __future__ import annotations

def create_project(service, req: CreateProjectRequest, workspace_id: Optional[str] = None) -> AgentRuntimeProject:
    import app.agent_runtime.service as _origin
    datetime = _origin.datetime
    timezone = _origin.timezone
    AgentRuntimeProject = _origin.AgentRuntimeProject
    uuid = _origin.uuid
    AgentRuntimeProjectDB = _origin.AgentRuntimeProjectDB
    logger = _origin.logger
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

    with service._lock:
        service._projects[project.id] = project
        service._persist_projects()
    return project
