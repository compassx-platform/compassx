"""Workspace middleware: slug → workspace_id resolution + WorkspaceContext injection.

Per spec section 8.
"""
from __future__ import annotations

import logging
import re
import hashlib
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import AccountSessionLocal

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^(?:/api)?/w/([^/]+)")


@dataclass
class WorkspaceContext:
    workspace_id: str
    workspace_slug: str
    workspace_name: str
    principal_id: str
    principal_role: str  # role in this workspace
    is_account_admin: bool


def extract_slug_from_path(path: str) -> str | None:
    m = _SLUG_RE.match(path)
    return m.group(1) if m else None


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    token = request.query_params.get("token")
    if token:
        return token.strip()
    return None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class WorkspaceAuthError(Exception):
    """Workspace context could not be established.

    Carries the status a request should be refused with, so that HTTP callers
    and the WebSocket proxy can both report the same reason in their own
    protocol.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def resolve_workspace_context(
    slug: str, token: str | None
) -> WorkspaceContext:
    """Authenticate ``token`` and place it in the workspace named by ``slug``.

    This is the whole of the workspace gate: it identifies the caller, checks
    the workspace exists and is active, and confirms the caller is a member.

    It lives outside the middleware because the middleware is a
    ``BaseHTTPMiddleware``, which Starlette runs for HTTP scopes only. A
    WebSocket route therefore never gets a context from it and has to build
    one itself — and must do so with exactly these rules, or the socket
    becomes the way around the gate that the HTTP routes enforce.
    """
    if AccountSessionLocal is None:
        raise WorkspaceAuthError(503, "system database not available")

    db = AccountSessionLocal()
    try:
        from app.workspace.models import Workspace, WorkspaceMembership
        from app.workspace.data_models import WpSession

        is_uuid = False
        try:
            UUID(slug)
            is_uuid = True
        except ValueError:
            pass

        if is_uuid:
            workspace = db.query(Workspace).filter(
                (Workspace.slug == slug) | (Workspace.id == slug)
            ).first()
        else:
            workspace = db.query(Workspace).filter(Workspace.slug == slug).first()
        if workspace is None:
            raise WorkspaceAuthError(404, "workspace not found")
        if workspace.status != "active":
            raise WorkspaceAuthError(403, "workspace unavailable")

        if not token:
            raise WorkspaceAuthError(401, "missing auth token")

        user_id = None
        is_account_admin = False

        # 1. Try decoding User Manager v1 JWT token
        try:
            from app.user_manager.auth_utils import decode_access_token
            from app.user_manager.models.account_models import UmUser
            from app.user_manager.dependencies import get_effective_account_role

            payload = decode_access_token(token)
            jwt_sub = payload.get("sub")
            if jwt_sub:
                um_user = db.query(UmUser).filter(UmUser.id == jwt_sub).first()
                if um_user and um_user.status == "active":
                    user_id = um_user.id
                    role = get_effective_account_role(um_user.id, um_user.account_id, db)
                    is_account_admin = (role == "account_admin")
        except Exception:
            pass

        # 2. Fallback to legacy WpSession
        if user_id is None:
            h = _token_hash(token)
            now = datetime.now(timezone.utc)
            from app.database import SystemSessionLocal
            if SystemSessionLocal:
                data_db = SystemSessionLocal()
                try:
                    session = (
                        data_db.query(WpSession)
                        .filter(WpSession.token_hash == h, WpSession.expires_at > now)
                        .first()
                    )
                    if session:
                        user_id = session.principal_id
                finally:
                    data_db.close()

        if user_id is None:
            raise WorkspaceAuthError(401, "invalid or expired token")

        # Check workspace access
        principal_role = "workspace_admin" if is_account_admin else None
        if not is_account_admin:
            # WorkspaceMembership in account_db uses UUID type for workspace_id
            membership = (
                db.query(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.principal_id == user_id,
                )
                .first()
            )
            if membership:
                principal_role = membership.role
            else:
                # UmWorkspaceRoleAssignment query using workspace.id (valid UUID)
                from app.database import SystemSessionLocal
                if SystemSessionLocal:
                    s_db = SystemSessionLocal()
                    try:
                        from app.user_manager.models.system_models import UmWorkspaceRoleAssignment
                        ass = s_db.query(UmWorkspaceRoleAssignment).filter(
                            UmWorkspaceRoleAssignment.workspace_id == workspace.id,
                            UmWorkspaceRoleAssignment.principal_id == user_id,
                        ).first()
                        if ass:
                            principal_role = ass.role_id
                    finally:
                        s_db.close()

            if not principal_role:
                raise WorkspaceAuthError(403, "not a member of this workspace")

        return WorkspaceContext(
            workspace_id=workspace.id,
            workspace_slug=workspace.slug,
            workspace_name=workspace.name,
            principal_id=user_id,
            principal_role=principal_role or "workspace_admin",
            is_account_admin=is_account_admin,
        )
    finally:
        db.close()


class WorkspaceMiddleware(BaseHTTPMiddleware):
    """Resolves /w/<slug>/* and /api/w/<slug>/* requests, injects WorkspaceContext into request.state."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        slug = extract_slug_from_path(request.url.path)
        if slug is None:
            slug = request.headers.get("x-workspace-slug")
        if slug is None:
            slug = request.query_params.get("workspace")
        if slug is None:
            slug = request.query_params.get("workspace_id")

        if slug is None:
            return await call_next(request)

        try:
            request.state.workspace = resolve_workspace_context(
                slug, _extract_token(request)
            )
        except WorkspaceAuthError as exc:
            return JSONResponse({"error": exc.message}, status_code=exc.status_code)

        return await call_next(request)
