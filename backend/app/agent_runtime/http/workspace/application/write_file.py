from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def write_file(session_id: str, body: WriteFileRequest):
    """Write one workspace file from the editor."""
    return _workspace_call(agent_runtime_service.write_workspace_file, session_id, body.path, body.content)
