def _bind():
    import app.agents.http.budgets.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_budget_statuses(
    request: Request,
    scope_type: str,
    scope_id: Optional[str] = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """
    Get the running spend status logs for all active budgets of the given scope.
    Lazily creates status records for the current period if they don't exist.
    """
    workspace_id = guard.workspace_id
    budgets_q = db.query(Budget).filter(
        Budget.workspace_id == workspace_id,
        Budget.scope_type == scope_type,
        Budget.is_active == True,
    )
    if scope_id:
        budgets_q = budgets_q.filter(Budget.scope_id == scope_id)
    budgets = budgets_q.all()

    now = datetime.now(timezone.utc)
    tz_str = get_org_timezone_str(db, workspace_id)
    statuses = []

    for budget in budgets:
        try:
            status = get_or_create_status(db, budget.scope_type, budget.scope_id, budget.period, now, tz_str, workspace_id)
            statuses.append(status)
        except Exception as e:
            logger.error(f"Error resolving budget status for budget ID {budget.id}: {e}")

    # Commit any lazily created statuses
    db.commit()
    return statuses
