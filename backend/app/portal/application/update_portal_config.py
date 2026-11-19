def _bind():
    import app.portal.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

from app.portal.application.workspace_items import selected_workspace_id


def update_portal_config(
    body: PortalConfigUpdate,
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
    adb: Session = None,
):
    """Save updated portal navigation layout (sections, items, ordering, icons, visibility)."""
    principal = getattr(guard, "principal", None)
    role = principal.workspace_role(guard.workspace_id) if principal is not None else None
    if role != "admin":
        guard.require_workspace_admin("Saving the portal sidebar")
    target_ws = selected_workspace_id(workspace_id, workspace_slug, guard, adb) or "default"
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_id == target_ws).first()

    sections_data = [sec.dict() for sec in body.sections]

    if not cfg:
        cfg = PortalConfig(
            id=f"portal_cfg_{uuid.uuid4().hex[:16]}",
            workspace_id=target_ws,
            workspace_slug=workspace_slug,
            sections=sections_data,
            created_by_user_id=guard.user_id if hasattr(guard, "user_id") else None,
        )
        sdb.add(cfg)
    else:
        cfg.sections = sections_data
        if workspace_slug:
            cfg.workspace_slug = workspace_slug
        cfg.updated_at = datetime.now(timezone.utc)
        flag_modified(cfg, "sections")

    sdb.commit()
    sdb.refresh(cfg)

    stored = cfg.settings if isinstance(getattr(cfg, "settings", None), dict) else {}
    return PortalConfigOut(
        id=cfg.id,
        workspace_id=cfg.workspace_id,
        workspace_slug=cfg.workspace_slug,
        sections=cfg.sections or [],
        settings={"logo": stored.get("logo") or None},
        updated_at=cfg.updated_at or cfg.created_at,
    )
