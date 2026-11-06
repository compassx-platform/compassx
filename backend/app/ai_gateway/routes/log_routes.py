"""AI Gateway Telemetry and Inference Log Routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from sqlalchemy.orm import Session

from app.ai_gateway.models.inference_log import AIGatewayInferenceLog, AIGatewayToolLog

from app.ai_gateway.schemas.inference_log import InferenceLogResponse, ToolLogResponse

from app.database import SystemSessionLocal

logger = logging.getLogger("app.ai_gateway.routes.log_routes")
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

import app.ai_gateway.http.logs.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.ai_gateway.http.logs.application.get_inference_logs import get_inference_logs as get_inference_logs_action
from app.ai_gateway.http.logs.application.get_tool_logs import get_tool_logs as get_tool_logs_action

logger = logging.getLogger("app.ai_gateway.routes.log_routes")

router = APIRouter(prefix="/api/v1/ai-gateway/logs", tags=["AI Gateway - Observability & Logs"])

@router.get("/inferences", response_model=list[InferenceLogResponse])
def get_inference_logs(
    request: Request,
    endpoint_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_system_db),
):
    """Retrieve recent AI Gateway inference logs."""
    return get_inference_logs_action(request=request, endpoint_name=endpoint_name, limit=limit, db=db)

@router.get("/tools", response_model=list[ToolLogResponse])
def get_tool_logs(
    request: Request,
    tool_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_system_db),
):
    """Retrieve recent AI Gateway tool execution audit logs."""
    return get_tool_logs_action(request=request, tool_name=tool_name, limit=limit, db=db)
