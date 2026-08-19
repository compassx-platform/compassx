"""Source control backend factory.

Resolution order (§4):
  1. git_config WHERE scope='workspace' AND workspace_id=<current>
  2. git_config WHERE scope='platform'
  3. NativeSourceControlBackend (fallback)
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import GitConfig
from app.apps.services.source_control.backend import SourceControlBackend
from app.apps.services.source_control.native_backend import NativeSourceControlBackend
from app.apps.services.source_control.git_backend import GitSourceControlBackend


def get_blob_backend(db: Session):
    """Retrieve default/active blob storage backend from config or active workspace."""
    from app.database import AccountSessionLocal
    account_db = AccountSessionLocal()
    try:
        from app.storage.service import storage_service
        _, backend = storage_service.get_default_backend(account_db)
        return backend
    except Exception:
        from app.workspace.models import Workspace
        from app.workspace.storage_resolver import resolve_workspace_storage
        from app.storage.azure_backend import AzureStorageBackend
        from app.storage.s3_backend import S3StorageBackend
        from app.storage.minio_backend import MinIOStorageBackend

        workspace = account_db.query(Workspace).filter(Workspace.status == "active").first()
        if workspace:
            provider, config = resolve_workspace_storage(workspace)
            if provider == "azure":
                return AzureStorageBackend(
                    account_name=config.get("account_name"),
                    container=config.get("container"),
                    base_path=config.get("prefix") or "compassx/",
                    account_key=config.get("account_key"),
                )
            elif provider == "s3":
                return S3StorageBackend(
                    bucket=config.get("bucket"),
                    base_path=config.get("prefix") or "compassx/",
                    region=config.get("region") or "us-east-1",
                    access_key=config.get("access_key"),
                    secret_key=config.get("secret_key"),
                )
            elif provider == "minio":
                return MinIOStorageBackend(
                    bucket=config.get("bucket"),
                    base_path=config.get("prefix") or "compassx/",
                    endpoint_url=config.get("endpoint"),
                    access_key=config.get("access_key"),
                    secret_key=config.get("secret_key"),
                )
        raise RuntimeError("No storage backend configured in system or workspace")
    finally:
        account_db.close()


def get_source_control_backend(
    db: Session,
    workspace_id: Optional[uuid.UUID] = None,
    repo_base_path: str = "/git-repos",
) -> SourceControlBackend:
    """Resolve and return the appropriate source control backend.

    Resolution order:
      1. git_config WHERE scope='workspace' AND workspace_id=<workspace_id>
      2. git_config WHERE scope='platform'
      3. NativeSourceControlBackend (content-addressable, no external git required)
    """
    blob = get_blob_backend(db)

    # 1. Workspace-scoped git config
    if workspace_id is not None:
        ws_config: Optional[GitConfig] = (
            db.query(GitConfig)
            .filter(GitConfig.scope == "workspace", GitConfig.workspace_id == workspace_id)
            .one_or_none()
        )
        if ws_config is not None:
            return GitSourceControlBackend(db=db, git_config=ws_config, repo_base_path=repo_base_path)

    # 2. Platform-level git config
    platform_config: Optional[GitConfig] = (
        db.query(GitConfig)
        .filter(GitConfig.scope == "platform")
        .one_or_none()
    )
    if platform_config is not None:
        return GitSourceControlBackend(db=db, git_config=platform_config, repo_base_path=repo_base_path)

    # 3. Native fallback
    return NativeSourceControlBackend(db=db, blob=blob)
