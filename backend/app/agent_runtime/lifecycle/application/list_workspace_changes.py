from __future__ import annotations

def list_workspace_changes(service, session_id: str) -> ChangesResponse:
    import app.agent_runtime.service as _origin
    changes_command = _origin.changes_command
    ChangeEntry = _origin.ChangeEntry
    CommitEntry = _origin.CommitEntry
    ChangesResponse = _origin.ChangesResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    payload = service._exec_json(session.sandbox_id, changes_command(), timeout=30)
    entries = [
        ChangeEntry(
            path=str(item.get("path") or ""),
            status=str(item.get("status") or "modified"),
            additions=int(item.get("additions") or 0),
            deletions=int(item.get("deletions") or 0),
            staged=bool(item.get("staged")),
            unstaged=bool(item.get("unstaged", True)),
        )
        for item in payload.get("entries") or []
        if item.get("path")
    ]
    commits = [
        CommitEntry(
            hash=str(item.get("hash") or ""),
            subject=str(item.get("subject") or ""),
            author=str(item.get("author") or ""),
            date=str(item.get("date") or ""),
        )
        for item in payload.get("commits") or []
        if item.get("hash")
    ]
    return ChangesResponse(entries=entries, branch=str(payload.get("branch") or ""), commits=commits)
