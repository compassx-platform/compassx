def _bind():
    import app.portal.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

from app.portal.application.workspace_items import (
    selected_workspace_id,
    workspace_apps,
    workspace_dashboards,
)


def get_available_items(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    adb: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve all candidate apps and dashboards available to be pinned/linked into the Portal."""
    target_ws = selected_workspace_id(workspace_id, workspace_slug, guard, adb)
    apps = workspace_apps(sdb, target_ws, workspace_slug)
    dashboards = workspace_dashboards(adb, target_ws)

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
