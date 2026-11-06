def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def create_app(
    body: AppCreate,
    request: Request,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create and register a new workspace-scoped application in the system DB."""
    workspace_id = guard.workspace_id or "default"
    ctx = getattr(request.state, "workspace", None)
    workspace_slug = getattr(ctx, "workspace_slug", None) if ctx else None
    slug = body.slug or _to_slug(body.name)
    route = body.route or f"/{slug}"
    if not route.startswith("/"):
        route = f"/{route}"

    # Generate dedicated App Workspace Identity
    identity_id = f"id_app_{uuid.uuid4().hex[:12]}"
    workspace_identity = {
        "identity_id": identity_id,
        "principal_type": "app_workload",
        "workspace_id": workspace_id,
        "role": "app_executor",
        "scopes": [
            "catalog:read",
            "compute:run",
            "models:inference",
            "agents:invoke",
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Encrypt Git PAT if supplied
    git_pat_enc = encrypt_field(body.git_pat) if body.git_pat else None
    git_ref = body.git_ref or body.git_branch or "main"

    app_id = f"app_{uuid.uuid4().hex[:16]}"
    app = App(
        id=app_id,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        name=body.name,
        slug=slug,
        description=body.description,
        app_type=body.app_type,
        status="active",
        route=route,
        git_provider=body.git_provider or "github",
        git_repo_url=body.git_repo_url,
        git_ref=git_ref,
        git_ref_type=body.git_ref_type or "branch",
        git_branch=git_ref,
        git_subdir=body.git_subdir,
        entrypoint=body.entrypoint,
        git_credential_type=body.git_credential_type or ("pat" if body.git_pat else "none"),
        git_credential_nickname=body.git_credential_nickname,
        git_connection_id=body.git_connection_id,
        git_pat_enc=git_pat_enc,
        workspace_identity=workspace_identity,
        config=body.config or {},
        created_by_user_id=str(guard.principal.id) if guard.principal else None,
    )

    db.add(app)
    db.commit()
    db.refresh(app)
    logger.info("Created app '%s' (id=%s) for workspace '%s'", app.name, app.id, workspace_id)

    # Automatically provision Ingress with Let's Encrypt TLS so certificates are generated immediately
    try:
        from app.services.ingress_service import ingress_service
        ingress_service.ensure_app_ingress(app)
    except Exception as ing_err:
        logger.warning("Non-fatal app ingress initialization error for %s: %s", app.slug, ing_err)

    return _to_response(app)
