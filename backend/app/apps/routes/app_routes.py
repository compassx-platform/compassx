"""App registration routes — POST /api/v1/apps, GET /api/v1/apps/{app_id}"""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.apps.models.apps import App
from app.apps.schemas.apps import AppCreate, AppRead
from app.apps.services.credential_service import CredentialService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps"])

DbDep = Annotated[Session, Depends(get_system_db)]


@router.post("", response_model=AppRead, status_code=201)
async def create_app(payload: AppCreate, db: DbDep):
    """Register a new CompassX App as a catalog asset.

    Also creates the per-app credential grant in the same transaction.
    """
    app = App(
        catalog_fqn=payload.catalog_fqn,
        workspace_id=payload.workspace_id,
        owner_id=payload.workspace_id,   # TODO: replace with current user from auth context
        name=payload.name,
        versioning_backend=payload.versioning_backend,
        terminal_enabled_prod=payload.terminal_enabled_prod,
        max_concurrent_branches=payload.max_concurrent_branches,
    )
    db.add(app)
    db.flush()

    # Create credential grant
    cred_svc = CredentialService(db)
    cred_svc.upsert_grant(
        app_id=app.app_id,
        catalog_grants=payload.catalog_grants,
        volume_grants=payload.volume_grants,
    )

    db.commit()
    db.refresh(app)
    logger.info("App created: %s (%s)", app.name, app.app_id)
    return app


@router.get("/{app_id}", response_model=AppRead)
async def get_app(app_id: uuid.UUID, db: DbDep):
    """Fetch a single app by ID."""
    app = db.query(App).filter(App.app_id == app_id).one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} not found")
    return app


@router.get("", response_model=list[AppRead])
async def list_apps(workspace_id: uuid.UUID, db: DbDep):
    """List all apps in a workspace."""
    return db.query(App).filter(App.workspace_id == workspace_id).all()
