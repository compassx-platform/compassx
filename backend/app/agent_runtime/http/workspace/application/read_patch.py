from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def read_patch(session_id: str):
    """Return one diff of every uncommitted workspace change."""
    return _workspace_call(agent_runtime_service.read_workspace_patch, session_id)
