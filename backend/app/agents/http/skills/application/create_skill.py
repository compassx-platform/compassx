def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_skill(
    request: Request,
    body: SkillCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Add a skill to the workspace library.

    Admin: the library is shared, and anyone who can add to it can put text in
    front of an agent that other people will later attach without reading.
    """
    guard.require_workspace_admin("Creating a skill")
    workspace_id = guard.workspace_id
    existing = (
        db.query(Skill)
        .filter(
            Skill.name.ilike(body.name),
            Skill.is_active.is_(True),
            Skill.workspace_id == workspace_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(400, "Skill with this name already exists")

    skill = Skill(
        workspace_id=workspace_id,
        name=body.name.strip(),
        description=body.description.strip(),
        body=body.body,
        trigger_hints=body.trigger_hints,
        version=1,
        is_active=True,
        created_by=str(guard.principal.id),
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill
