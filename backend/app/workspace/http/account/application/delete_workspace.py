from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_workspace(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.account_id == _admin.account_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.status = "deleting"
    db.commit()
    background_tasks.add_task(_purge_workspace, workspace_id)
    return {"status": "accepted", "workspace_id": workspace_id}
