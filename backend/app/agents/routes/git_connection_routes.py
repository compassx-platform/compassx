"""Git Connection CRUD routes + connection test."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_account_db
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


def _get_or_404(db: Session, connection_id: int, workspace_id: str | None = None) -> GitConnection:
    query = db.query(GitConnection).filter(GitConnection.id == connection_id)
    if workspace_id:
        query = query.filter(GitConnection.workspace_id == workspace_id)
    else:
        query = query.filter(GitConnection.workspace_id == None)
    conn = query.first()
    if not conn:
        raise HTTPException(404, "Git connection not found")
    return conn


@router.get("", response_model=list[GitConnectionResponse])
def list_git_connections(request: Request, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(GitConnection)
    if workspace_id:
        query = query.filter(GitConnection.workspace_id == workspace_id)
    else:
        query = query.filter(GitConnection.workspace_id == None)
    return [_to_response(r) for r in query.order_by(GitConnection.name).all()]


@router.post("", response_model=GitConnectionResponse, status_code=201)
def create_git_connection(request: Request, body: GitConnectionCreate, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
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
    return _to_response(conn)


@router.get("/{connection_id}", response_model=GitConnectionResponse)
def get_git_connection(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return _to_response(_get_or_404(db, connection_id, workspace_id))


@router.put("/{connection_id}", response_model=GitConnectionResponse)
def update_git_connection(request: Request, connection_id: int, body: GitConnectionUpdate, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(db, connection_id, workspace_id)
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
def delete_git_connection(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(db, connection_id, workspace_id)
    db.delete(conn)
    db.commit()


@router.post("/{connection_id}/test", response_model=PingResponse)
def test_git_connection(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(db, connection_id, workspace_id)
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
