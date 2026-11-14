from __future__ import annotations

def ensure_nova_agent(db: Session, workspace_id: str | None) -> Agent:
    import app.agent_runtime.nova as _origin
    Agent = _origin.Agent
    selectinload = _origin.selectinload
    NOVA_NAME = _origin.NOVA_NAME
    NOVA_TOOLS = _origin.NOVA_TOOLS
    AgentTool = _origin.AgentTool
    NOVA_COLOR = _origin.NOVA_COLOR
    AgentVisibility = _origin.AgentVisibility
    query = db.query(Agent).options(selectinload(Agent.tools), selectinload(Agent.skills))
    if workspace_id:
        query = query.filter(Agent.workspace_id == workspace_id)
    agent = query.filter(Agent.name == NOVA_NAME).order_by(Agent.id.asc()).first()
    if agent:
        existing = {tool.tool_name for tool in agent.tools}
        for key in NOVA_TOOLS:
            if key not in existing:
                db.add(AgentTool(agent_id=agent.id, tool_name=key))
        db.commit()
        return (
            db.query(Agent)
            .options(selectinload(Agent.tools), selectinload(Agent.skills))
            .filter(Agent.id == agent.id)
            .first()
        )
    agent = Agent(
        workspace_id=workspace_id,
        name=NOVA_NAME,
        description="CompassX default agent for data, notebooks, and analysis.",
        color=NOVA_COLOR,
        prompt="",
        is_orchestrator=True,
        visibility=AgentVisibility.shared,
        status="active",
        is_active=True,
        created_by="system",
        manifest={},
    )
    db.add(agent)
    db.flush()
    for key in NOVA_TOOLS:
        db.add(AgentTool(agent_id=agent.id, tool_name=key))
    db.commit()
    return (
        db.query(Agent)
        .options(selectinload(Agent.tools), selectinload(Agent.skills))
        .filter(Agent.id == agent.id)
        .first()
    )
