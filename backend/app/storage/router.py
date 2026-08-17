"""FastAPI router for storage backend management (/api/v1/storage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_account_db as get_db
from app.dependencies import get_current_user
from .models import StorageBackendCreate, StorageBackendRead
from .service import storage_service

router = APIRouter(prefix="/api/v1/storage", tags=["Storage"])


@router.post("/backends", response_model=StorageBackendRead, status_code=201)
def register_backend(
    data: StorageBackendCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Register or update a storage backend."""
    try:
        return storage_service.register_backend(db, data, registered_by=user.get("email", user.get("id", "unknown")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/backends", response_model=list[StorageBackendRead])
def list_backends(db: Session = Depends(get_db)):
    """List all registered storage backends."""
    return storage_service.list_backends(db)


@router.delete("/backends/{name}", status_code=204)
def delete_backend(
    name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a storage backend registration."""
    try:
        storage_service.delete_backend(db, name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/backends/{name}/test")
async def test_backend(name: str, db: Session = Depends(get_db)):
    """Test connectivity to a registered storage backend."""
    return await storage_service.test_connection(db, name)
