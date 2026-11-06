"""Git Connection CRUD routes + connection test."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_connection, visible_connections

from app.database import get_account_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

from app.models.agents import GitConnection

from app.schemas.agents import GitConnectionCreate, GitConnectionResponse, GitConnectionUpdate, PingResponse

from app.services.encryption import decrypt_field, encrypt_field

def _to_response(conn: GitConnection) -> GitConnectionResponse:
    return GitConnectionResponse(
        id=conn.id,
        name=conn.name,
        provider=conn.provider,
        base_url=conn.base_url,
        organization=conn.organization,
        default_project=conn.default_project,
        pat_configured=bool(conn.pat_enc),
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )

def _get_or_404(db: Session, connection_id: int, guard: Guard, privilege: Privilege) -> GitConnection:
    """Load a git connection the caller holds ``privilege`` on.

    Workspace comes from the guard. The previous version fell back to
    ``workspace_id == None`` when none was resolved, so an unscoped request
    reached the workspace-less connections rather than being refused.
    """
    return authorized_connection(db, guard, GitConnection, connection_id, privilege)

def _test_github(pat: str, base_url: str | None) -> tuple[bool, str]:
    try:
        from github import Github
        g = Github(pat, base_url=base_url) if base_url else Github(pat)
        user = g.get_user()
        return True, f"Connected as {user.login}"
    except ImportError:
        return False, "PyGithub not installed. Run: pip install PyGithub"
    except Exception as exc:
        return False, str(exc)

def _test_azure_devops(pat: str, organization: str | None, base_url: str | None) -> tuple[bool, str]:
    try:
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication

        if not organization:
            return False, "Organization is required for Azure DevOps connections."

        org_url = base_url or f"https://dev.azure.com/{organization}"
        creds = BasicAuthentication("", pat)
        connection = Connection(base_url=org_url, creds=creds)
        projects = connection.clients.get_core_client().get_projects()
        count = len(list(projects)) if projects else 0
        return True, f"Connected to {organization} - {count} project(s) accessible."
    except ImportError:
        return False, "azure-devops package not installed. Run: pip install azure-devops>=7.1.0b4"
    except Exception as exc:
        return False, str(exc)
