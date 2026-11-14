from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def read_diff(session_id: str, path: str = Query(...)):
    """Return the unified diff for one workspace path."""
    return _workspace_call(agent_runtime_service.read_workspace_diff, session_id, path)
