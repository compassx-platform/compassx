def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def detach_skill(
    request: Request,
    skill_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Detach a skill from an agent."""
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    _get_skill(db, skill_id, guard)

    attachment = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.skill_id == skill_id,
        AgentSkillAttachment.agent_id == agent_id,
    ).first()
    if not attachment:
        raise HTTPException(404, "Attachment not found")

    db.delete(attachment)
    db.commit()
    return
