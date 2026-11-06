def _bind():
    import app.portal.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def _bootstrap_default_config(
    workspace_id: str,
    workspace_slug: Optional[str],
    sdb: Session,
    adb: Session,
    user_id: Optional[str] = None,
) -> PortalConfig:
    """Build a sensible default portal configuration using existing apps & dashboards."""
    # Query workspace apps
    app_query = sdb.query(App)
    if workspace_id:
        app_query = app_query.filter(App.workspace_id == workspace_id)
    elif workspace_slug:
        app_query = app_query.filter(App.workspace_slug == workspace_slug)
    apps = app_query.order_by(App.created_at.desc()).all()

    # Query dashboards
    dashboards = adb.query(Dashboard).order_by(Dashboard.created_at.desc()).all()

    sections: List[dict] = []

    # Apps Section
    app_items = []
    for idx, a in enumerate(apps):
        app_items.append({
            "id": f"item_app_{a.id}",
            "type": "app",
            "target_id": a.id,
            "title": a.name,
            "icon": "LayoutGrid" if a.app_type == "react" else "Sparkles" if a.app_type == "streamlit" else "Code2",
            "is_visible": True,
            "order": idx,
            "url": a.route,
            "app_type": a.app_type,
            "status": a.status,
        })

    if app_items:
        sections.append({
            "id": "sec_applications",
            "title": "Applications",
            "items": app_items,
        })

    # Dashboards Section
    dash_items = []
    for idx, d in enumerate(dashboards):
        dash_items.append({
            "id": f"item_dash_{d.id}",
            "type": "dashboard",
            "target_id": str(d.id),
            "title": d.name,
            "icon": "BarChart2",
            "is_visible": True,
            "order": idx,
            "url": None,
            "app_type": None,
            "status": "published" if not d.is_draft else "draft",
        })

    if dash_items:
        sections.append({
            "id": "sec_dashboards",
            "title": "Dashboards",
            "items": dash_items,
        })

    # Fallback if both empty
    if not sections:
        sections.append({
            "id": "sec_applications",
            "title": "Applications",
            "items": [],
        })

    new_cfg = PortalConfig(
        id=f"portal_cfg_{uuid.uuid4().hex[:16]}",
        workspace_id=workspace_id or "default",
        workspace_slug=workspace_slug,
        sections=sections,
        created_by_user_id=user_id,
    )
    sdb.add(new_cfg)
    try:
        sdb.commit()
        sdb.refresh(new_cfg)
    except Exception as e:
        sdb.rollback()
        logger.warning("Could not persist auto-bootstrapped portal config: %s", e)

    return new_cfg


def get_portal_config(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    adb: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve the portal configuration for the specified workspace.

    If no configuration exists, automatically bootstraps one from the workspace's
    deployed apps and dashboards.
    """
    target_ws = workspace_id or guard.workspace_id or "default"
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_id == target_ws).first()

    if not cfg and workspace_slug:
        cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_slug == workspace_slug).first()

    if not cfg:
        cfg = _bootstrap_default_config(
            workspace_id=target_ws,
            workspace_slug=workspace_slug,
            sdb=sdb,
            adb=adb,
            user_id=guard.user_id if hasattr(guard, "user_id") else None,
        )

    return PortalConfigOut(
        id=cfg.id,
        workspace_id=cfg.workspace_id,
        workspace_slug=cfg.workspace_slug,
        sections=cfg.sections or [],
        updated_at=cfg.updated_at or cfg.created_at,
    )
