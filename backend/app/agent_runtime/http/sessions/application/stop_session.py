from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def stop_session(session_id: str):
    """Stop the agent that is working on this session."""
    return agent_runtime_service.stop_turn(session_id)
