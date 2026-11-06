def _bind():
    import app.agents.http.git_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_git_connection(
    request: Request,
    body: GitConnectionCreate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a git provider.

    Admin: the stored PAT carries whatever repository access it was issued
    with, and anyone later granted USE_COMPUTE acts with it.
    """
    guard.require_workspace_admin("Creating a git connection")
    workspace_id = guard.workspace_id
    conn = GitConnection(
        workspace_id=workspace_id,
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        organization=body.organization,
        default_project=body.default_project,
        pat_enc=encrypt_field(body.pat) if body.pat else None,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)
