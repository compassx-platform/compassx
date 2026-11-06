def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_candidate_principals(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Return all account-level users, groups, and service principals NOT yet assigned to this workspace."""
    _require_ws_admin(workspace_id, user, account_db, system_db)

    # Get already assigned principal IDs
    assigned_rows = system_db.query(UmWorkspaceRoleAssignment.principal_id).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id
    ).all()
    assigned_ids = {r[0] for r in assigned_rows}

    candidates: list[CandidatePrincipalOut] = []

    # 1. Users
    users = account_db.query(UmUser).filter(
        UmUser.account_id == user.account_id,
        UmUser.status != "deactivated",
    ).all()
    for u in users:
        if u.id not in assigned_ids:
            candidates.append(CandidatePrincipalOut(
                id=u.id,
                type="user",
                display_name=u.display_name or u.email,
                email_or_client_id=u.email,
                details=f"User ({u.status})",
            ))

    # 2. Groups
    groups = account_db.query(UmGroup).filter(
        UmGroup.account_id == user.account_id
    ).all()
    for g in groups:
        if g.id not in assigned_ids:
            candidates.append(CandidatePrincipalOut(
                id=g.id,
                type="group",
                display_name=g.name,
                details=f"Group · {len(g.members)} members",
            ))

    # 3. Service Principals
    sps = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.account_id == user.account_id,
        UmServicePrincipal.active == True,
    ).all()
    for sp in sps:
        if sp.id not in assigned_ids:
            candidates.append(CandidatePrincipalOut(
                id=sp.id,
                type="service_principal",
                display_name=sp.display_name,
                email_or_client_id=sp.client_id,
                details="Service Principal (OAuth)",
            ))

    return candidates
