def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_audit_log(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    actor_user_id: str | None = Query(None),
    action: str | None = Query(None),
    workspace_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    q = account_db.query(UmAuditLog).filter(UmAuditLog.account_id == admin.account_id)
    if actor_user_id:
        q = q.filter(UmAuditLog.actor_user_id == actor_user_id)
    if action:
        q = q.filter(UmAuditLog.action == action)
    if workspace_id:
        q = q.filter(UmAuditLog.workspace_id == workspace_id)
    rows = q.order_by(UmAuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [AuditLogItem(
        id=r.id, actor_user_id=r.actor_user_id, action=r.action,
        target_type=r.target_type, target_id=r.target_id,
        workspace_id=r.workspace_id, metadata=r.metadata_,
        created_at=r.created_at,
    ) for r in rows]
