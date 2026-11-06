def _bind():
    import app.agents.http.git_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def test_git_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Call the provider with the stored PAT and report the result.

    USE_COMPUTE: this decrypts the token and makes a real authenticated call.
    The response names the account the token belongs to and how many projects
    it can reach, which is a description of the credential itself.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    if not conn.pat_enc:
        return PingResponse(success=False, message="No PAT configured for this connection.")

    pat = decrypt_field(conn.pat_enc)

    if conn.provider == "github":
        success, message = _test_github(pat, conn.base_url)
    elif conn.provider == "azure_devops":
        success, message = _test_azure_devops(pat, conn.organization, conn.base_url)
    else:
        success, message = False, f"Unknown provider: {conn.provider}"

    return PingResponse(success=success, message=message)
