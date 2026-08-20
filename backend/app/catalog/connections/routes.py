"""FastAPI routes for First-Class Catalog Connections."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.dependencies import get_current_user
from app.catalog.connections.registry import registry
from app.catalog.connections.service import connection_service
from app.catalog.connections.schemas import (
    CatalogConnectionCreate,
    CatalogConnectionResponse,
    CatalogConnectionUpdate,
    ConnectionFieldSchema,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ProviderMetadataResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Catalog Connections"])


def _to_response(conn) -> CatalogConnectionResponse:
    return CatalogConnectionResponse(
        id=conn.id,
        catalog=conn.catalog_name,
        schema_name=conn.schema_name,
        name=conn.name,
        full_name=conn.full_name,
        category=conn.category,
        connector_type=conn.connector_type,
        description=conn.description,
        config=conn.config or {},
        status=conn.status,
        owner=conn.owner,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# ── 1. Provider Catalog ───────────────────────────────────────────────────────

@router.get("/catalog/connections/providers", response_model=List[ProviderMetadataResponse])
@router.get("/connections/providers", response_model=List[ProviderMetadataResponse])
@router.get("/api/v1/connections/providers", response_model=List[ProviderMetadataResponse])
def get_connection_providers(category: Optional[str] = None):
    """List available connection providers with dynamic configuration and authentication schemas."""
    providers = registry.list_by_category(category) if category else registry.list_all()
    result = []
    for p in providers:
        result.append(
            ProviderMetadataResponse(
                type_id=p.type_id,
                name=p.name,
                category=p.category,
                description=p.description,
                is_popular=p.is_popular,
                logo=p.logo,
                default_port=p.default_port,
                config_fields=[
                    ConnectionFieldSchema(
                        name=f.name,
                        label=f.label,
                        type=f.type,
                        required=f.required,
                        default=f.default,
                        placeholder=f.placeholder,
                        help_text=f.help_text,
                        options=f.options,
                    )
                    for f in p.config_fields
                ],
                auth_fields=[
                    ConnectionFieldSchema(
                        name=f.name,
                        label=f.label,
                        type=f.type,
                        required=f.required,
                        default=f.default,
                        placeholder=f.placeholder,
                        help_text=f.help_text,
                        options=f.options,
                    )
                    for f in p.auth_fields
                ],
            )
        )
    return result


# ── 2. Live Connection Testing ────────────────────────────────────────────────

@router.post("/catalog/connections/test", response_model=ConnectionTestResponse)
@router.post("/connections/test", response_model=ConnectionTestResponse)
@router.post("/api/v1/connections/test", response_model=ConnectionTestResponse)
def test_connection_endpoint(
    body: ConnectionTestRequest,
    db: Session = Depends(get_account_db),
):
    """Test connectivity for an in-flight configuration or an existing connection."""
    res = connection_service.test_connection(db, body)
    return ConnectionTestResponse(
        success=res.success,
        message=res.message,
        latency_ms=res.latency_ms,
        details=res.details,
    )


# ── 3. Connection CRUD ────────────────────────────────────────────────────────

@router.post("/catalog/connections", response_model=CatalogConnectionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/connections", response_model=CatalogConnectionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/connections", response_model=CatalogConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    body: CatalogConnectionCreate,
    db: Session = Depends(get_account_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new connection as a first-class citizen of the Unified Catalog."""
    user_id = str(current_user.get("email") or current_user.get("id") or "default_user")
    try:
        conn = connection_service.create_connection(db, body, user_id=user_id)
        return _to_response(conn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to create connection: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create connection")


@router.get("/catalog/connections", response_model=List[CatalogConnectionResponse])
@router.get("/connections", response_model=List[CatalogConnectionResponse])
@router.get("/api/v1/connections", response_model=List[CatalogConnectionResponse])
def list_connections(
    catalog: Optional[str] = Query(None, description="Filter by catalog name"),
    schema_name: Optional[str] = Query(None, alias="schema", description="Filter by schema name"),
    category: Optional[str] = Query(None, description="database | api | observability | custom"),
    connector_type: Optional[str] = Query(None, description="postgres | rest_api | loki etc."),
    status_filter: Optional[str] = Query(None, alias="status", description="active | disabled"),
    search: Optional[str] = Query(None, description="Search query"),
    db: Session = Depends(get_account_db),
):
    """List connections across catalogs and schemas."""
    conns = connection_service.list_connections(
        db,
        catalog_name=catalog,
        schema_name=schema_name,
        category=category,
        connector_type=connector_type,
        status=status_filter,
        search_query=search,
    )
    return [_to_response(c) for c in conns]


@router.get("/catalog/connections/{connection_id}", response_model=CatalogConnectionResponse)
@router.get("/connections/{connection_id}", response_model=CatalogConnectionResponse)
@router.get("/api/v1/connections/{connection_id}", response_model=CatalogConnectionResponse)
def get_connection(
    connection_id: str,
    db: Session = Depends(get_account_db),
):
    """Fetch connection details by ID or FQN."""
    conn = connection_service.get_connection(db, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return _to_response(conn)


@router.put("/catalog/connections/{connection_id}", response_model=CatalogConnectionResponse)
@router.put("/connections/{connection_id}", response_model=CatalogConnectionResponse)
@router.put("/api/v1/connections/{connection_id}", response_model=CatalogConnectionResponse)
def update_connection(
    connection_id: str,
    body: CatalogConnectionUpdate,
    db: Session = Depends(get_account_db),
    current_user: dict = Depends(get_current_user),
):
    """Update connection config or credentials."""
    user_id = str(current_user.get("email") or current_user.get("id") or "default_user")
    conn = connection_service.update_connection(db, connection_id, body, user_id=user_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return _to_response(conn)


@router.post("/catalog/connections/{connection_id}/toggle-status", response_model=CatalogConnectionResponse)
@router.post("/connections/{connection_id}/toggle-status", response_model=CatalogConnectionResponse)
@router.post("/api/v1/connections/{connection_id}/toggle-status", response_model=CatalogConnectionResponse)
def toggle_connection_status(
    connection_id: str,
    db: Session = Depends(get_account_db),
):
    """Toggle connection active / disabled status."""
    conn = connection_service.toggle_status(db, connection_id)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return _to_response(conn)


@router.delete("/catalog/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/api/v1/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: str,
    db: Session = Depends(get_account_db),
):
    """Delete a connection from the catalog."""
    deleted = connection_service.delete_connection(db, connection_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return None
