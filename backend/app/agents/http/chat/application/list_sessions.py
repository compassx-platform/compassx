def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_sessions(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's chat sessions, with a preview of the last message.

    Sessions belong to the agent rather than to the person who opened them, so
    BROWSE on the agent is what admits someone to the history. That is the
    existing product behaviour — a shared workspace for the agent — made
    explicit rather than changed.
    """
    _get_agent_or_404(db, agent_id, guard, Privilege.BROWSE)
    sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.agent_id == agent_id,
            ChatSession.archived.is_(False),
            ChatSession.workspace_id == guard.workspace_id,
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    session_ids = [s.id for s in sessions]
    if not session_ids:
        return []

    from sqlalchemy import func
    subq = (
        db.query(
            ChatMessage.session_id,
            func.max(ChatMessage.id).label("max_id"),
            func.count(ChatMessage.id).label("msg_count"),
        )
        .filter(ChatMessage.session_id.in_(session_ids))
        .group_by(ChatMessage.session_id)
        .all()
    )
    max_id_map = {row.session_id: row.max_id for row in subq}
    count_map = {row.session_id: row.msg_count for row in subq}

    last_msgs: dict[int, str] = {}
    if max_id_map:
        msgs = db.query(ChatMessage).filter(ChatMessage.id.in_(max_id_map.values())).all()
        for m in msgs:
            text = m.content or ""
            if text:
                text = text.replace("\n", " ").strip()
                if len(text) > 90:
                    text = text[:87] + "..."
            last_msgs[m.session_id] = text

    has_changes_map: dict[int, bool] = {}
    changes_count_map: dict[int, int] = {}
    try:
        from app.agents.models.agents import ChangeRecord
        change_rows = (
            db.query(
                ChangeRecord.session_id,
                func.count(ChangeRecord.change_id).label("change_count"),
            )
            .filter(ChangeRecord.session_id.in_([str(sid) for sid in session_ids]))
            .group_by(ChangeRecord.session_id)
            .all()
        )
        for row in change_rows:
            try:
                sid = int(row.session_id)
                cnt = int(row.change_count)
                has_changes_map[sid] = cnt > 0
                changes_count_map[sid] = cnt
            except Exception:
                pass
    except Exception:
        pass

    result = []
    for s in sessions:
        res = ChatSessionResponse(
            id=s.id,
            agent_id=s.agent_id,
            title=s.title,
            archived=s.archived,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_message=last_msgs.get(s.id),
            message_count=count_map.get(s.id, 0),
            has_changes=has_changes_map.get(s.id, False),
            files_changed_count=changes_count_map.get(s.id, 0),
        )
        result.append(res)
    return result
