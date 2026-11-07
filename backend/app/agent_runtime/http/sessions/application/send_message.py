def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def send_message(session_id: str, body: SendMessageRequest):
    """Send a follow-up prompt into the running tmux agent."""
    try:
        return agent_runtime_service.deliver_prompt(
            session_id, body.content, llm_model=getattr(body, "llm_model", None)
        )
    except ValueError as e:
        status = 400 if "empty" in str(e).lower() else 404
        raise HTTPException(status_code=status, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")
