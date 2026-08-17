"""Publish routes — POST /api/v1/apps/{app_id}/publish, GET production status."""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.apps.models.apps import App
from app.apps.schemas.apps import PublishRequest, PublishResponse, ProductionStatus
from app.apps.services.publish_service import PublishService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/apps", tags=["apps-publish"])

DbDep = Annotated[Session, Depends(get_system_db)]


@router.post("/{app_id}/publish", response_model=PublishResponse)
async def publish_app(app_id: uuid.UUID, payload: PublishRequest, db: DbDep):
    """Publish a specific commit to production.

    Provisions a dedicated production pod, materializes the commit,
    waits for health check, then atomically switches the production pointer.
    """
    app = db.query(App).filter(App.app_id == app_id).one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} not found")

    svc = PublishService(db)
    try:
        pod = await svc.publish(
            app_id=app_id,
            commit_id=payload.commit_id,
            source_branch_id=payload.source_branch_id,
            switched_by=app.owner_id,   # TODO: replace with auth context user
        )
        db.commit()
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))

    return PublishResponse(
        app_id=app_id,
        commit_id=payload.commit_id,
        production_pod_id=pod.pod_id,
        preview_url=pod.preview_url,
        status=pod.status,
    )


@router.get("/{app_id}/production", response_model=ProductionStatus)
async def get_production_status(app_id: uuid.UUID, db: DbDep):
    """Return the current production pointer and pod status."""
    app = db.query(App).filter(App.app_id == app_id).one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} not found")

    svc = PublishService(db)
    status = await svc.get_production_status(app_id=app_id)
    return ProductionStatus(**status)
