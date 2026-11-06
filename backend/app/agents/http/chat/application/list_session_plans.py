def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_session_plans(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return all stored plans for this session directly from PlanService."""
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    from app.agents.services.agent.plan_service import PlanService
    ps = PlanService()
    plans = ps.get_plans_for_session(session_id)
    return [p.model_dump() for p in plans]
