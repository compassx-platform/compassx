from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def read_output(session_id: str):
    """Return the live agent pane so chat stays in sync with the terminal."""
    try:
        return AgentOutputResponse(output=agent_runtime_service.capture_agent_output(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read agent output: {str(exc)}")
