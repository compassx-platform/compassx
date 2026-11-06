def _bind():
    import app.agents.http.skills.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_skill(
    request: Request,
    skill_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Soft delete a skill by setting is_active = False.

    Admin: it detaches the skill from every agent that had it, which changes
    the behaviour of agents belonging to other people.
    """
    guard.require_workspace_admin("Deleting a skill")
    skill = _get_skill(db, skill_id, guard)
    skill.is_active = False
    skill.updated_at = _utcnow()

    # Detach from all agents
    db.query(AgentSkillAttachment).filter(AgentSkillAttachment.skill_id == skill_id).delete()

    db.commit()
    return
