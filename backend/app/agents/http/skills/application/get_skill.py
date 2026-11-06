def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_skill(
    request: Request,
    skill_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Get a single skill by ID."""
    return _get_skill(db, skill_id, guard)
