def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_skill(
    request: Request,
    skill_id: int,
    body: SkillUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Update a skill. Increments the version field.

    Admin, for the reason given in the module docstring: the edit propagates
    to every agent this skill is attached to, whoever owns them.
    """
    guard.require_workspace_admin("Editing a skill")
    skill = _get_skill(db, skill_id, guard)

    if body.name is not None:
        name_clean = body.name.strip()
        if name_clean.lower() != skill.name.lower():
            existing = (
                db.query(Skill)
                .filter(
                    Skill.name.ilike(name_clean),
                    Skill.is_active.is_(True),
                    Skill.workspace_id == guard.workspace_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(400, "Skill with this name already exists")
        skill.name = name_clean

    if body.description is not None:
        skill.description = body.description.strip()

    if body.body is not None:
        skill.body = body.body

    if body.trigger_hints is not None:
        skill.trigger_hints = body.trigger_hints

    # Increment version upon update
    skill.version += 1
    skill.updated_at = _utcnow()

    db.commit()
    db.refresh(skill)
    return skill
