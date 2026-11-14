from __future__ import annotations

def create_session(
    service, req: CreateAgentSessionRequest, workspace_id: Optional[str] = None
) -> AgentRuntimeSession:
    import app.agent_runtime.service as _origin
    uuid = _origin.uuid
    agent_registry = _origin.agent_registry
    sandbox_service = _origin.sandbox_service
    SandboxSpec = _origin.SandboxSpec
    os = _origin.os
    datetime = _origin.datetime
    timezone = _origin.timezone
    AgentRuntimeSession = _origin.AgentRuntimeSession
    AgentRuntimeSessionDB = _origin.AgentRuntimeSessionDB
    logger = _origin.logger
    with service._lock:
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
        if project_id and not service.get_project(project_id):
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
            service._checkout_workspace_branch(bound_sandbox_id, branch)

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

        service._sessions[session_id] = session
        service._persist_sessions()
        if clean_agent == "antigravity":
            service._sync_antigravity_login(session, force=True)
        return session
