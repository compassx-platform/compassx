def _bind():
    import app.agents.http.llm_calls.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_llm_call_log_detail(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return one call in full: prompt, history, tools, and response."""
    log = (
        db.query(LlmCallLog)
        .filter(
            LlmCallLog.id == call_id,
            LlmCallLog.workspace_id == guard.workspace_id,
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="LLM call log not found")

    agent = authorized_agent(db, guard, log.agent_id, Privilege.BROWSE)
    agent_name = agent.name if agent else None

    # Resolve message history
    resolved_history = []
    history_list = log.message_history or []

    # Handle legacy records that used message_id references
    message_ids = [item.get("message_id") for item in history_list if isinstance(item, dict) and item.get("message_id") is not None]
    messages_map = {}
    if message_ids:
        db_messages = db.query(ChatMessage).filter(ChatMessage.id.in_(message_ids)).all()
        for msg in db_messages:
            messages_map[msg.id] = {
                "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                "content": msg.content,
                "tool_name": msg.tool_name,
                "tool_result": msg.tool_result,
            }

    for item in history_list:
        if not isinstance(item, dict):
            continue
        if "role" in item and ("content" in item or "tool_calls" in item or "tool_call_id" in item or "name" in item):
            resolved_history.append(item)
        elif item.get("message_id") in messages_map:
            resolved_history.append(messages_map[item["message_id"]])
        else:
            resolved_history.append(item)

    return LlmCallLogDetailResponse(
        id=log.id,
        agent_id=log.agent_id,
        agent_name=agent_name,
        session_id=log.session_id,
        call_sequence_number=log.call_sequence_number,
        created_at=log.created_at,
        model=log.model,
        model_params=log.model_params or {},
        system_prompt_base=log.system_prompt_base,
        skills_available=log.skills_available or [],
        skills_injected=log.skills_injected or [],
        message_history=resolved_history,
        tools_available=log.tools_available or [],
        response_text=log.response_text,
        response_tool_calls=log.response_tool_calls or [],
        finish_reason=log.finish_reason,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
    )
