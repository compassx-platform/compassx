def _bind():
    import app.agents.http.budgets.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_budget(
    request: Request,
    budget_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a budget configuration.

    Removing a cap is the same act as raising one, so it takes the same
    privilege as setting it.
    """
    guard.require_workspace_admin("Deleting a budget")
    budget = _get_budget_or_404(db, budget_id, guard)

    db.delete(budget)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(400, f"Failed to delete budget configuration: {exc}") from exc
