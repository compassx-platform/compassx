def _bind():
    import app.agents.http.budgets.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_budgets(
    request: Request,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List all budget configurations with optional scope filtering."""
    query = db.query(Budget).filter(Budget.workspace_id == guard.workspace_id)

    if scope_type:
        query = query.filter(Budget.scope_type == scope_type)
    if scope_id:
        query = query.filter(Budget.scope_id == scope_id)
    return query.order_by(Budget.created_at.desc()).all()
