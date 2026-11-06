def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def attach_skill(
    request: Request,
    skill_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Attach a skill to an agent.

    EDIT on the agent — this is an edit to its instructions, reached by a
    different URL. Reading the library takes nothing beyond membership, so the
    skill lookup adds no check of its own.
    """
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    _get_skill(db, skill_id, guard)

    # Check if already attached
    existing = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.skill_id == skill_id,
        AgentSkillAttachment.agent_id == agent_id,
    ).first()
    if existing:
        return db.query(AgentSkillAttachment).options(selectinload(AgentSkillAttachment.skill)).filter(
            AgentSkillAttachment.id == existing.id
        ).first()

    # Get max position
    max_pos = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.agent_id == agent_id
    ).count()

    attachment = AgentSkillAttachment(
        agent_id=agent_id,
        skill_id=skill_id,
        position=max_pos,
        attached_at=_utcnow(),
    )
    db.add(attachment)
    db.commit()

    return db.query(AgentSkillAttachment).options(selectinload(AgentSkillAttachment.skill)).filter(
        AgentSkillAttachment.id == attachment.id
    ).first()
