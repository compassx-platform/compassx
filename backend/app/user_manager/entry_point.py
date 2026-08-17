"""User Manager — post-login landing resolution (§4).

Pure function: resolve_entry_point(user_id, account_db, system_db, deep_link_workspace_id?)
→ { workspace_id, section, route }

Cached per (user_id,) with a 60-second TTL using a simple in-process LRU cache.
Cache is invalidated externally by calling invalidate_entry_point_cache(user_id).
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache
from threading import Lock
from typing import Optional

from sqlalchemy.orm import Session

from app.user_manager.models.system_models import (
    UmWorkspaceRoleAssignment,
    UmLandingRule,
)
from app.user_manager.dependencies import WORKSPACE_ROLE_RANK

logger = logging.getLogger(__name__)

# ── Simple TTL cache (thread-safe dict) ──────────────────────────────────────
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = Lock()
_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> dict | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
            return entry[1]
        if entry:
            del _cache[key]
        return None


def _cache_set(key: str, value: dict) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)


def invalidate_entry_point_cache(user_id: str | None = None) -> None:
    with _cache_lock:
        if user_id is None:
            _cache.clear()
        else:
            keys_to_del = [k for k in _cache.keys() if k == user_id or k.startswith(f"{user_id}:")]
            for k in keys_to_del:
                del _cache[k]


# ── Workspace membership resolution (direct + via group) ──────────────────────

def _get_user_workspace_ids(user_id: str, system_db: Session, account_db: Session) -> list[tuple[str, str]]:
    """Return [(workspace_id, role_id), ...] for all workspaces the user can access."""
    from app.user_manager.models.account_models import UmGroupMember, UmUser
    from app.user_manager.dependencies import get_effective_account_role
    from app.workspace.models import Workspace as LegacyWs

    user = account_db.query(UmUser).filter(UmUser.id == user_id).first()
    is_account_admin = False
    if user:
        role = get_effective_account_role(user.id, user.account_id, account_db)
        if role == "account_admin":
            is_account_admin = True

    # Direct memberships
    direct = (
        system_db.query(UmWorkspaceRoleAssignment)
        .filter(
            UmWorkspaceRoleAssignment.principal_id == user_id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        )
        .all()
    )

    # Via group
    group_ids = [
        gm.group_id
        for gm in account_db.query(UmGroupMember).filter(UmGroupMember.user_id == user_id).all()
    ]
    group_rows = []
    if group_ids:
        group_rows = (
            system_db.query(UmWorkspaceRoleAssignment)
            .filter(
                UmWorkspaceRoleAssignment.principal_id.in_(group_ids),
                UmWorkspaceRoleAssignment.principal_type == "group",
            )
            .all()
        )

    # Merge: per workspace, keep highest-rank role
    by_ws: dict[str, str] = {}
    for row in direct + group_rows:
        is_uuid = False
        try:
            from uuid import UUID
            UUID(str(row.workspace_id))
            is_uuid = True
        except (ValueError, TypeError):
            pass
        ws = account_db.query(LegacyWs).filter(
            LegacyWs.id == row.workspace_id if is_uuid else LegacyWs.slug == row.workspace_id
        ).first()
        ws_key = ws.id if ws else row.workspace_id

        existing_rank = WORKSPACE_ROLE_RANK.get(by_ws.get(ws_key, ""), 0)
        this_rank = WORKSPACE_ROLE_RANK.get(row.role_id, 0)
        if this_rank > existing_rank:
            by_ws[ws_key] = row.role_id

    # Account admins automatically have access to all workspaces in their account (or system)
    if is_account_admin and user:
        all_workspaces = (
            account_db.query(LegacyWs)
            .filter(
                (LegacyWs.account_id == user.account_id) | (LegacyWs.account_id.is_(None)),
                LegacyWs.status == "active"
            )
            .all()
        )
        if not all_workspaces:
            all_workspaces = (
                account_db.query(LegacyWs)
                .filter(LegacyWs.status == "active")
                .all()
            )
        for ws in all_workspaces:
            if ws.id not in by_ws and ws.slug not in by_ws:
                by_ws[ws.id] = "workspace_admin"

    return list(by_ws.items())


def _normalize_landing_route(route: str) -> str:
    if not route:
        return "/platform/notebooks"
    if route.startswith("/business-center"):
        route = "/business_center" + route[16:]
    if route.endswith("/") and len(route) > 1:
        route = route[:-1]
    if not route.startswith("/"):
        route = "/" + route
    return route


def _resolve_route(workspace_id: str, role_id: str, system_db: Session) -> str:
    """Step 2 of §4 — resolve route inside a workspace for a given role."""
    # Workspace-specific rule
    ws_rule = (
        system_db.query(UmLandingRule)
        .filter(
            UmLandingRule.scope_type == "workspace",
            UmLandingRule.scope_id == workspace_id,
            UmLandingRule.role_id == role_id,
        )
        .order_by(UmLandingRule.priority.desc())
        .first()
    )
    if ws_rule:
        return _normalize_landing_route(ws_rule.target_route)

    # Global rule
    global_rule = (
        system_db.query(UmLandingRule)
        .filter(
            UmLandingRule.scope_type == "global",
            UmLandingRule.role_id == role_id,
        )
        .order_by(UmLandingRule.priority.desc())
        .first()
    )
    if global_rule:
        return _normalize_landing_route(global_rule.target_route)

    # Hard fallback
    return "/platform/notebooks"


# ── Main resolution function ───────────────────────────────────────────────────

def resolve_entry_point(
    user_id: str,
    account_db: Session,
    system_db: Session,
    deep_link_workspace_id: Optional[str] = None,
) -> dict:
    """Resolve post-login landing for user_id.

    Returns: { workspace_id: str|None, section: str, route: str }
    Cached 60s per user_id; call invalidate_entry_point_cache() on membership change.
    """
    cache_key = f"{user_id}:{deep_link_workspace_id or ''}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    memberships = _get_user_workspace_ids(user_id, system_db, account_db)

    # Step 1 — resolve workspace
    workspace_id: str | None = None
    resolved_role: str | None = None

    if deep_link_workspace_id:
        # 1a. Deep link
        match = next((r for ws_id, r in memberships if ws_id == deep_link_workspace_id), None)
        if match:
            workspace_id = deep_link_workspace_id
            resolved_role = match

    if workspace_id is None:
        # 1b. Default workspace (is_default=true, user direct assignment)
        default_row = (
            system_db.query(UmWorkspaceRoleAssignment)
            .filter(
                UmWorkspaceRoleAssignment.principal_id == user_id,
                UmWorkspaceRoleAssignment.principal_type == "user",
                UmWorkspaceRoleAssignment.is_default == True,
            )
            .first()
        )
        if default_row:
            workspace_id = default_row.workspace_id
            resolved_role = next(
                (r for ws_id, r in memberships if ws_id == workspace_id), default_row.role_id
            )

    if workspace_id is None and len(memberships) == 1:
        # 1c. Single membership
        workspace_id, resolved_role = memberships[0]

    if workspace_id is None:
        if len(memberships) > 1:
            # 1d. Multiple memberships, no default
            result = {"workspace_id": None, "section": "picker", "route": "/workspace-picker"}
        else:
            # 1e. Zero memberships
            result = {"workspace_id": None, "section": "none", "route": "/no-workspace-access"}
        _cache_set(cache_key, result)
        return result

    # Step 2 — resolve route inside the workspace
    from uuid import UUID
    from app.workspace.models import Workspace as LegacyWs

    is_uuid = False
    try:
        UUID(str(workspace_id))
        is_uuid = True
    except (ValueError, TypeError):
        pass

    if is_uuid:
        ws = account_db.query(LegacyWs).filter(LegacyWs.id == workspace_id).first()
    else:
        ws = account_db.query(LegacyWs).filter(LegacyWs.slug == workspace_id).first()
    slug = ws.slug if ws else workspace_id
    canonical_ws_id = ws.id if ws else workspace_id

    route_suffix = _resolve_route(canonical_ws_id, resolved_role or "business_viewer", system_db)
    full_route = f"/w/{slug}{route_suffix}"
    result = {"workspace_id": canonical_ws_id, "section": "app", "route": full_route}
    _cache_set(cache_key, result)
    return result
