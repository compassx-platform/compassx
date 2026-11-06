def _bind():
    import app.portal.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_available_items(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    adb: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve all candidate apps and dashboards available to be pinned/linked into the Portal."""
    target_ws = workspace_id or guard.workspace_id
    app_query = sdb.query(App)
    if target_ws:
        app_query = app_query.filter(App.workspace_id == target_ws)
    elif workspace_slug:
        app_query = app_query.filter(App.workspace_slug == workspace_slug)

    apps = app_query.order_by(App.created_at.desc()).all()
    dashboards = adb.query(Dashboard).order_by(Dashboard.created_at.desc()).all()

    app_list = [
        AvailableAppItem(
            id=a.id,
            name=a.name,
            slug=a.slug,
            description=a.description,
            app_type=a.app_type,
            status=a.status,
            route=a.route,
        )
        for a in apps
    ]

    dash_list = [
        AvailableDashboardItem(
            id=str(d.id),
            name=d.name,
            description=None,
            is_draft=bool(d.is_draft),
            published_at=d.published_at,
        )
        for d in dashboards
    ]

    return PortalAvailableItemsResponse(
        apps=app_list,
        dashboards=dash_list,
    )
