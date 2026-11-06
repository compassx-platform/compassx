def _bind():
    import app.agents.http.budgets.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_budget(
    request: Request,
    body: BudgetCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new budget configuration, validating that the referenced scope exists."""
    guard.require_workspace_admin("Creating a budget")
    workspace_id = guard.workspace_id

    # Validate scope target
    if body.scope_type == "agent":
        try:
            agent_id = int(body.scope_id)
        except ValueError:
            raise HTTPException(400, f"Invalid agent ID format: {body.scope_id}")
        # Resolves in this workspace or 404s. A budget naming an agent from
        # another workspace would silently never apply to anything.
        authorized_agent(db, guard, agent_id, Privilege.BROWSE)

    # Prevent duplicate active budgets for the same scope and period within workspace context
    if body.is_active:
        existing = (
            db.query(Budget)
            .filter(
                Budget.workspace_id == workspace_id,
                Budget.scope_type == body.scope_type,
                Budget.scope_id == body.scope_id,
                Budget.period == body.period,
                Budget.is_active == True,
            )
            .first()
        )
        if existing:
            raise HTTPException(400, f"An active {body.period} budget already exists for {body.scope_type} {body.scope_id}")

    budget = Budget(
        workspace_id=workspace_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        period=body.period,
        limit_amount=body.limit_amount,
        warn_threshold_pct=body.warn_threshold_pct,
        on_exceeded=body.on_exceeded,
        is_active=body.is_active,
        created_by=str(guard.principal.id),
    )
    db.add(budget)
    try:
        db.commit()
        db.refresh(budget)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to save budget configuration: {exc}") from exc
    return budget
