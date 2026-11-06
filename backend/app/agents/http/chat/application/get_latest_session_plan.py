def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_latest_session_plan(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return the most recent plan for this session directly from PlanService."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    from app.agents.services.agent.plan_service import PlanService
    ps = PlanService()
    plan = ps.get_latest_plan_for_session(session_id)
    return plan.model_dump() if plan else None
