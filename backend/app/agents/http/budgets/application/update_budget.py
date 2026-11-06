def _bind():
    import app.agents.http.budgets.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_budget(
    request: Request,
    budget_id: int,
    body: BudgetUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Update a budget configuration."""
    guard.require_workspace_admin("Editing a budget")
    budget = _get_budget_or_404(db, budget_id, guard)

    data = body.model_dump(exclude_none=True)

    # If activating, ensure no duplicate active budget exists for scope and period within workspace context
    if data.get("is_active"):
        existing = (
            db.query(Budget)
            .filter(
                Budget.workspace_id == guard.workspace_id,
                Budget.scope_type == budget.scope_type,
                Budget.scope_id == budget.scope_id,
                Budget.period == budget.period,
                Budget.is_active == True,
                Budget.id != budget.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(400, f"Another active {budget.period} budget already exists for this scope")

    for field, value in data.items():
        setattr(budget, field, value)

    try:
        db.commit()
        db.refresh(budget)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to update budget configuration: {exc}") from exc
    return budget
