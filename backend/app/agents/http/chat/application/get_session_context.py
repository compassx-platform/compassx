def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_session_context(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Report how much of the model's context window this session is using.

    The response includes the rolling summary, which is a condensation of the
    transcript — so it takes the same privilege as reading the transcript.
    """
    agent = _get_agent_or_404(db, agent_id, guard, Privilege.BROWSE)
    session = _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    llm_conn = _resolve_llm_connection(db, agent)

    context_window = resolve_model_context_window(llm_conn)
    model_name = getattr(llm_conn, "model_name", None) or "Default"

    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    turns = group_messages_into_turns(all_messages)

    candidate_msgs = []
    if session.summary:
        candidate_msgs.append({"role": "system", "content": session.summary})
    for t in turns:
        candidate_msgs.extend(t.to_llm_messages())

    total_tokens = estimate_messages_tokens(candidate_msgs)
    high_watermark = int(context_window * DEFAULT_HIGH_WATERMARK_RATIO)
    usage_percent = round((total_tokens / max(context_window, 1)) * 100, 1)

    return ContextUsageResponse(
        total_tokens=total_tokens,
        context_window=context_window,
        high_watermark=high_watermark,
        usage_percent=min(usage_percent, 100.0),
        total_turns=len(turns),
        retained_turns=min(len(turns), DEFAULT_LOW_WATERMARK_K),
        has_summary=bool(session.summary and session.summary.strip()),
        summary=session.summary,
        summary_updated_at=session.summary_updated_at,
        model_name=model_name,
    )
