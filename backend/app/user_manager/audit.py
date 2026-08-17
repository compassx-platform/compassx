"""User Manager — audit log helper."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.user_manager.models.account_models import UmAuditLog


def log_action(
    db: Session,
    account_id: str,
    action: str,
    target_type: str,
    actor_user_id: str | None = None,
    target_id: str | None = None,
    workspace_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write one row to um_audit_log. Fire-and-forget — caller commits."""
    db.add(UmAuditLog(
        account_id=account_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        workspace_id=workspace_id,
        metadata_=metadata,
    ))
