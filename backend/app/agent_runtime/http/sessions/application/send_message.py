def _bind():
    import app.agent_runtime.http.sessions.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def send_message(session_id: str, body: SendMessageRequest):
    """Send a user message to the agent and receive its response."""
    try:
        return agent_runtime_service.send_message(session_id, body.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")
