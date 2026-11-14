from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def list_changes(session_id: str):
    """List git changes in the session sandbox workspace."""
    return _workspace_call(agent_runtime_service.list_workspace_changes, session_id)
