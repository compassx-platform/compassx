from __future__ import annotations

def sandbox_git(service, sandbox_id: str) -> GitInfoResponse:
    import app.agent_runtime.service as _origin
    git_info_command = _origin.git_info_command
    GitInfoResponse = _origin.GitInfoResponse
    service._require_running_sandbox(sandbox_id)
    payload = service._exec_json(sandbox_id, git_info_command(), timeout=15)
    branches = [str(name) for name in (payload.get("branches") or []) if name]
    return GitInfoResponse(
        repo=bool(payload.get("repo")),
        branch=str(payload.get("branch") or ""),
        branches=branches,
    )
