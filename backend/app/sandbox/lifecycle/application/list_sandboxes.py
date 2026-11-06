from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.sandbox.models import SandboxInstance, SandboxStatus
from app.sandbox.shared.support import _normalize_key, logger


class ListSandboxes:
    def execute(
        self,
        service,
        workspace_id: Optional[str] = None,
        consumer_module: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SandboxInstance]:
        combined: Dict[str, SandboxInstance] = dict(service._instances)

        def _find_matching_key(item_id: str, c_key: Optional[str] = None) -> Optional[str]:
            norm_item = _normalize_key(item_id)
            norm_c = _normalize_key(c_key) if c_key else None
            for k, existing in list(combined.items()):
                if _normalize_key(k) == norm_item or _normalize_key(existing.id) == norm_item:
                    return k
                if norm_c and (
                    _normalize_key(existing.consumer_key) == norm_c
                    or _normalize_key(existing.labels.get("compassx.consumer-key") if existing.labels else None) == norm_c
                    or _normalize_key(existing.labels.get("compassx.consumer_key") if existing.labels else None) == norm_c
                    or _normalize_key(existing.metadata.get("app_id") if existing.metadata else None) == norm_c
                ):
                    return k
            return None

        driver = service._get_driver_for_mode()
        try:
            discovered = driver.discover_active_instances()
            for item in discovered:
                matched_key = _find_matching_key(item.id, item.consumer_key)
                if not matched_key:
                    combined[item.id] = item
                else:
                    existing_entry = combined[matched_key]
                    existing_entry.status = item.status
                    if item.endpoints:
                        existing_entry.endpoints = item.endpoints
                    if item.pod_name:
                        existing_entry.pod_name = item.pod_name
                    if item.image:
                        existing_entry.image = item.image
        except Exception as exc:
            logger.debug("Sandbox driver discovery error: %s", exc)

        try:
            from app.database import SystemSessionLocal
            from app.models.dev_workspace import DevWorkspace
            from app.models.app import App

            with SystemSessionLocal() as db:
                dev_workspaces = db.query(DevWorkspace).filter(DevWorkspace.status == "active").all()
                for ws in dev_workspaces:
                    app = db.query(App).filter(App.id == ws.app_id).first()
                    dev_sb_id = f"dev-app-{ws.app_id}"
                    c_key = f"app_{ws.app_id}"
                    matched_key = _find_matching_key(dev_sb_id, c_key)
                    if not matched_key:
                        app_name = app.name if app else ws.app_id
                        combined[dev_sb_id] = SandboxInstance(
                            id=dev_sb_id,
                            consumer_key=c_key,
                            name=f"{app_name} (Dev Sandbox)",
                            consumer_module="app",
                            workspace_id=app.workspace_id if app else None,
                            status=SandboxStatus.RUNNING,
                            runtime_mode=driver.__class__.__name__.replace("SandboxDriver", "").lower(),
                            image="compassx-dev-host:latest",
                            created_at=ws.created_at.isoformat() if ws.created_at else datetime.now(timezone.utc).isoformat(),
                            started_at=ws.updated_at.isoformat() if ws.updated_at else None,
                            metadata={"app_id": ws.app_id, "folder_path": ws.folder_path},
                        )
        except Exception as dev_err:
            logger.debug("Dev workspace discovery error: %s", dev_err)

        results = list(combined.values())

        if workspace_id:
            results = [r for r in results if not r.workspace_id or r.workspace_id == workspace_id]
        if consumer_module:
            results = [r for r in results if r.consumer_module.lower() == consumer_module.lower()]
        if status:
            results = [r for r in results if r.status.value.lower() == status.lower()]

        results.sort(key=lambda x: x.created_at or "", reverse=True)
        return results


def list_sandboxes(service, workspace_id=None, consumer_module=None, status=None):
    return ListSandboxes().execute(service, workspace_id, consumer_module, status)
