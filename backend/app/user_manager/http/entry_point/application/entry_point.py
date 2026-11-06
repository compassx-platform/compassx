def _bind():
    import app.user_manager.http.entry_point.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def entry_point(
    deep_link_workspace_id: str | None = Query(None),
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Resolve post-login landing per §4. Called once per session bootstrap."""
    result = resolve_entry_point(
        user_id=user.id,
        account_db=account_db,
        system_db=system_db,
        deep_link_workspace_id=deep_link_workspace_id,
    )
    return EntryPointOut(**result)
