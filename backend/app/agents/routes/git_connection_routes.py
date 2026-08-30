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

router = APIRouter(prefix="/api/v1/git-connections", tags=["Git Connections"])


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


@router.get("", response_model=list[GitConnectionResponse])
def list_git_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the git connections the caller may see.

    ``pat_configured`` is a boolean — the token itself is encrypted at rest and
    only decrypted when a call to the provider is made.
    """
    rows = (
        db.query(GitConnection)
        .filter(GitConnection.workspace_id == guard.workspace_id)
        .order_by(GitConnection.name)
        .all()
    )
    return [_to_response(r) for r in visible_connections(guard, rows)]


@router.post("", response_model=GitConnectionResponse, status_code=201)
def create_git_connection(
    request: Request,
    body: GitConnectionCreate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a git provider.

    Admin: the stored PAT carries whatever repository access it was issued
    with, and anyone later granted USE_COMPUTE acts with it.
    """
    guard.require_workspace_admin("Creating a git connection")
    workspace_id = guard.workspace_id
    conn = GitConnection(
        workspace_id=workspace_id,
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        organization=body.organization,
        default_project=body.default_project,
        pat_enc=encrypt_field(body.pat) if body.pat else None,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)


@router.get("/{connection_id}", response_model=GitConnectionResponse)
def get_git_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    return _to_response(_get_or_404(db, connection_id, guard, Privilege.BROWSE))


@router.put("/{connection_id}", response_model=GitConnectionResponse)
def update_git_connection(
    request: Request,
    connection_id: int,
    body: GitConnectionUpdate,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a git connection.

    EDIT: it can repoint the connection at a different organization or swap
    the PAT, which every existing grantee then acts with.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    if "pat" in data:
        pat = data.pop("pat")
        conn.pat_enc = encrypt_field(pat) if pat else None
    for field, value in data.items():
        setattr(conn, field, value)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


@router.delete("/{connection_id}", status_code=204)
def delete_git_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a git connection.

    MANAGE: it revokes access for everyone granted on it and discards the PAT.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.MANAGE)
    db.delete(conn)
    db.commit()


@router.post("/{connection_id}/test", response_model=PingResponse)
def test_git_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Call the provider with the stored PAT and report the result.

    USE_COMPUTE: this decrypts the token and makes a real authenticated call.
    The response names the account the token belongs to and how many projects
    it can reach, which is a description of the credential itself.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    if not conn.pat_enc:
        return PingResponse(success=False, message="No PAT configured for this connection.")

    pat = decrypt_field(conn.pat_enc)

    if conn.provider == "github":
        success, message = _test_github(pat, conn.base_url)
    elif conn.provider == "azure_devops":
        success, message = _test_azure_devops(pat, conn.organization, conn.base_url)
    else:
        success, message = False, f"Unknown provider: {conn.provider}"

    return PingResponse(success=success, message=message)


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
