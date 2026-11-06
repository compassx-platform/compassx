def _bind():
    import app.agents.http.artifacts.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_session_assets(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return all assets registered in the known-assets registry for this session (G1).

    BROWSE on the agent — this is a list of the catalog objects the agent
    touched during the conversation, which is part of the transcript.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    entries = known_assets_registry.get_all(session_id)
    if not entries:
        from app.models.agents import ChatMessage, MessageRole
        from app.agents.services.agent.known_assets_registry import register_from_tool_result
        tool_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == MessageRole.tool)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        for msg in tool_messages:
            if msg.tool_result and isinstance(msg.tool_result, dict):
                res = msg.tool_result.get("result") or {}
                if isinstance(res, dict) and msg.tool_name:
                    register_from_tool_result(session_id, msg.tool_name, res)
        entries = known_assets_registry.get_all(session_id)

    return [
        {
            "full_name": e.full_name,
            "object_type": e.object_type,
            "first_seen_turn": e.first_seen_turn,
            "source": e.source,
            "action": e.action,
            "plan_id": e.plan_id,
            "url": _resolve_asset_url(e.full_name, e.object_type),
        }
        for e in entries
    ]
