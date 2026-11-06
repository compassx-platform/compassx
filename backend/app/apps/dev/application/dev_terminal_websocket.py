def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

async def dev_terminal_websocket(
    websocket: WebSocket,
    app_id: str,
    token: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    workspace_name: Optional[str] = Query(None),
    cols: int = Query(100),
    rows: int = Query(30),
    agent: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """Interactive real-time WebSocket terminal inside the dev pod/container."""
    from app.database import SystemSessionLocal
    from app.workspace.middleware import WorkspaceAuthError, resolve_workspace_context

    with SystemSessionLocal() as db:
        app = db.query(App).filter(App.id == app_id).first()
        if not app:
            await websocket.accept()
            await websocket.send_text(f"\r\n\x1b[1;31mApp '{app_id}' not found.\x1b[0m\r\n")
            await websocket.close(code=4404, reason=f"App '{app_id}' not found")
            return
        workspace_key = str(app.workspace_id) if app.workspace_id else None
        db.expunge(app)

    try:
        if workspace_key:
            resolve_workspace_context(workspace_key, token)
        elif not token:
            raise WorkspaceAuthError(401, "missing auth token")
        else:
            from app.user_manager.auth_utils import decode_access_token
            decode_access_token(token)
    except WorkspaceAuthError as exc:
        await websocket.accept()
        await websocket.send_text(f"\r\n\x1b[1;31m{exc.message}\x1b[0m\r\n")
        await websocket.close(code=4401 if exc.status_code == 401 else 4403, reason=exc.message[:120])
        return
    except Exception:
        await websocket.accept()
        await websocket.send_text("\r\n\x1b[1;31mInvalid or expired token.\x1b[0m\r\n")
        await websocket.close(code=4401, reason="invalid or expired token")
        return

    unified_reaper_service.touch_app_activity(app.id)
    _sync_agent_login(app, force=True)
    await dev_terminal_service.handle_terminal_websocket(
        websocket=websocket,
        app=app,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        cols=cols,
        rows=rows,
        agent=agent,
        session_id=session_id,
    )
