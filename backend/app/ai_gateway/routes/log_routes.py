"""AI Gateway Telemetry and Inference Log Routes."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.ai_gateway.models.inference_log import AIGatewayInferenceLog, AIGatewayToolLog
from app.ai_gateway.schemas.inference_log import InferenceLogResponse, ToolLogResponse
from app.database import SystemSessionLocal

router = APIRouter(prefix="/api/v1/ai-gateway/logs", tags=["AI Gateway - Observability & Logs"])
logger = logging.getLogger(__name__)


def _get_workspace_id(request: Request) -> str | None:
    ctx = getattr(request.state, "workspace", None)
    if ctx and hasattr(ctx, "workspace_id"):
        try:
            import uuid
            uuid.UUID(str(ctx.workspace_id))
            return str(ctx.workspace_id)
        except Exception:
            return None
    ws_header = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")
    if ws_header:
        try:
            import uuid
            uuid.UUID(str(ws_header))
            return str(ws_header)
        except Exception:
            return None
    return None


def get_system_db():
    db = SystemSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/inferences", response_model=list[InferenceLogResponse])
def get_inference_logs(
    request: Request,
    endpoint_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_system_db),
):
    """Retrieve recent AI Gateway inference logs."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIGatewayInferenceLog)
    if ws_id:
        query = query.filter((AIGatewayInferenceLog.workspace_id == ws_id) | (AIGatewayInferenceLog.workspace_id.is_(None)))
    if endpoint_name:
        query = query.filter(AIGatewayInferenceLog.endpoint_name == endpoint_name)

    logs = query.order_by(AIGatewayInferenceLog.created_at.desc()).limit(limit).all()
    return logs


@router.get("/tools", response_model=list[ToolLogResponse])
def get_tool_logs(
    request: Request,
    tool_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_system_db),
):
    """Retrieve recent AI Gateway tool execution audit logs."""
    ws_id = _get_workspace_id(request)
    query = db.query(AIGatewayToolLog)
    if ws_id:
        query = query.filter((AIGatewayToolLog.workspace_id == ws_id) | (AIGatewayToolLog.workspace_id.is_(None)))
    if tool_name:
        query = query.filter(AIGatewayToolLog.tool_name == tool_name)

    logs = query.order_by(AIGatewayToolLog.created_at.desc()).limit(limit).all()
    return logs
