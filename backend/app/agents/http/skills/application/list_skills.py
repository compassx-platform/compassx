def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_skills(
    request: Request,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the active skills in this workspace.

    Readable by any member: the library is what someone picks from when
    configuring an agent, and a skill body is instructions, not data.
    """
    query = db.query(Skill).filter(
        Skill.is_active.is_(True),
        Skill.workspace_id == guard.workspace_id,
    )
    if isinstance(search, str) and search.strip():
        query = query.filter(
            Skill.name.ilike(f"%{search.strip()}%") | Skill.description.ilike(f"%{search.strip()}%")
        )
    return query.order_by(Skill.name).all()
