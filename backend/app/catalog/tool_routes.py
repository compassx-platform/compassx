"""API routes for Catalog Tools and Tool Promotion."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_account_db as get_db
from app.dependencies import get_current_user
from app.catalog.tool_schemas import ToolPromoteRequest, ToolResponse, ToolVersionResponse
from app.catalog import tool_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Catalog Tools"])


def _to_response(tool) -> ToolResponse:
    versions = [
        ToolVersionResponse(
            id=v.id,
            tool_id=v.tool_id,
            version=v.version,
            source_notebook_object_id=getattr(v, "source_notebook_object_id", None) or tool.source_notebook_object_id,
            source_code=v.source_code,
            param_schema=v.param_schema or {},
            connection_dependencies=v.connection_dependencies or [],
            promoted_by=v.promoted_by,
            promoted_at=v.promoted_at,
        )
        for v in (tool.versions or [])
    ]
    return ToolResponse(
        id=tool.id,
        catalog=tool.catalog_name,
        schema_name=tool.schema_name,
        name=tool.name,
        full_name=tool.full_name,
        description=tool.description,
        param_schema=tool.param_schema or {},
        connection_dependencies=tool.connection_dependencies or [],
        source_notebook_object_id=tool.source_notebook_object_id,
        source_code=tool.source_code,
        owner=tool.owner,
        current_version=tool.current_version,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
        versions=versions,
    )


@router.post(
    "/api/v1/catalog/tools/promote",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/catalog/tools/promote",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def promote_tool(
    payload: ToolPromoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    user_id = getattr(current_user, "id", "default_user")
    if hasattr(user_id, "__str__"):
        user_id = str(user_id)

    try:
        tool = svc.promote_tool(db=db, payload=payload, user_id=user_id)
        return _to_response(tool)
    except Exception as exc:
        logger.exception("Failed to promote tool: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/api/v1/catalog/tools/{tool_id}",
    response_model=ToolResponse,
)
@router.get(
    "/catalog/tools/{tool_id}",
    response_model=ToolResponse,
    include_in_schema=False,
)
def get_tool(
    tool_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    tool = svc.get_tool_by_id(db, tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool '{tool_id}' not found.")
    return _to_response(tool)


@router.get(
    "/api/v1/catalog/tools",
    response_model=List[ToolResponse],
)
@router.get(
    "/catalog/tools",
    response_model=List[ToolResponse],
    include_in_schema=False,
)
def list_tools(
    catalog: Optional[str] = Query(None),
    schema: Optional[str] = Query(None),
    schema_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    target_schema = schema or schema_name
    tools = svc.list_tools(db, catalog=catalog, schema=target_schema)
    return [_to_response(t) for t in tools]
