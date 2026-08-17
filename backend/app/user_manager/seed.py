"""User Manager — idempotent seed data.

Seeds static reference tables:
  - um_account_roles
  - um_workspace_roles (system_db)
  - um_landing_rules (system_db, global defaults)
  - um_permissions
  - um_object_roles + um_object_role_permissions

Called from /api/um/setup/complete and also standalone at import if tables are empty.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.user_manager.models.account_models import (
    UmAccountRole, UmPermission, UmObjectRole, UmObjectRolePermission,
)
from app.user_manager.models.system_models import UmWorkspaceRole, UmLandingRule

logger = logging.getLogger(__name__)


def seed_account_roles(account_db: Session) -> None:
    roles = [
        ("account_admin",   "Account Admin",   "Full control over account, users, and workspaces"),
        ("billing_admin",   "Billing Admin",   "Manages billing and subscription settings"),
        ("account_viewer",  "Account Viewer",  "Read-only access to account information"),
    ]
    for role_id, display, desc in roles:
        if not account_db.get(UmAccountRole, role_id):
            account_db.add(UmAccountRole(id=role_id, display_name=display, description=desc))
    account_db.flush()


def seed_workspace_roles(system_db: Session) -> None:
    roles = [
        ("workspace_admin", "Workspace Admin",  "Full control over workspace members and settings"),
        ("analyst",         "Analyst",          "Access to notebooks, SQL, and data tools"),
        ("business_viewer", "Business Viewer",  "Read-only access to business dashboards"),
    ]
    for role_id, display, desc in roles:
        if not system_db.get(UmWorkspaceRole, role_id):
            system_db.add(UmWorkspaceRole(id=role_id, display_name=display, description=desc))
    system_db.flush()


def seed_landing_rules(system_db: Session) -> None:
    # Migration fix: update any legacy landing rules to base /business_center
    system_db.query(UmLandingRule).filter(
        UmLandingRule.target_route.in_(["/business-center/home", "/business-center/documents", "/business_center/documents", "/business_center/business-context", "/business-context", "/business_center/dashboards"])
    ).update({"target_route": "/business_center"}, synchronize_session=False)
    system_db.flush()

    existing = system_db.query(UmLandingRule).filter(UmLandingRule.scope_type == "global").count()
    if existing:
        return

    global_rules = [
        # role_id,          target_route,        priority
        ("workspace_admin", "/platform/notebooks", 10),
        ("analyst",         "/platform/notebooks", 10),
        ("business_viewer", "/business_center",    10),
    ]
    for role_id, route, priority in global_rules:
        system_db.add(UmLandingRule(
            scope_type="global",
            scope_id=None,
            role_id=role_id,
            target_route=route,
            priority=priority,
        ))
    system_db.flush()


def seed_permissions(account_db: Session) -> None:
    perms = [
        ("notebook.read",    "Read Notebook",    "notebook"),
        ("notebook.edit",    "Edit Notebook",    "notebook"),
        ("notebook.execute", "Execute Notebook", "notebook"),
        ("notebook.share",   "Share Notebook",   "notebook"),
        ("notebook.comment", "Comment on Notebook", "notebook"),
        ("table.read",       "Read Table",       "table"),
        ("table.write",      "Write Table",      "table"),
        ("dashboard.view",   "View Dashboard",   "dashboard"),
        ("dashboard.edit",   "Edit Dashboard",   "dashboard"),
    ]
    for perm_id, display, resource in perms:
        if not account_db.get(UmPermission, perm_id):
            account_db.add(UmPermission(id=perm_id, display_name=display, resource_type=resource))
    account_db.flush()


def seed_object_roles(account_db: Session) -> None:
    object_roles = [
        ("notebook_viewer", "Notebook Viewer", "notebook",
         ["notebook.read"]),
        ("notebook_editor", "Notebook Editor", "notebook",
         ["notebook.read", "notebook.edit", "notebook.execute", "notebook.share"]),
        ("table_reader",    "Table Reader",    "table",
         ["table.read"]),
        ("table_writer",    "Table Writer",    "table",
         ["table.read", "table.write"]),
    ]
    for role_id, display, resource, perms in object_roles:
        if not account_db.get(UmObjectRole, role_id):
            account_db.add(UmObjectRole(id=role_id, display_name=display, resource_type=resource))
            account_db.flush()
            for perm_id in perms:
                account_db.add(UmObjectRolePermission(object_role_id=role_id, permission_id=perm_id))
    account_db.flush()


def run_all_seeds(account_db: Session, system_db: Session) -> None:
    """Run all seed operations idempotently."""
    try:
        seed_account_roles(account_db)
        seed_permissions(account_db)
        seed_object_roles(account_db)
        account_db.commit()
        logger.info("User Manager: account_db seed complete")
    except Exception as exc:
        account_db.rollback()
        logger.error("User Manager: account_db seed failed: %s", exc)
        raise

    try:
        seed_workspace_roles(system_db)
        seed_landing_rules(system_db)
        system_db.commit()
        logger.info("User Manager: system_db seed complete")
    except Exception as exc:
        system_db.rollback()
        logger.error("User Manager: system_db seed failed: %s", exc)
        raise
