"""OpenAI-Compatible Ingress Proxy Routes for AI Gateway."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_gateway.models.provider import AIModelEndpoint
from app.ai_gateway.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelItem,
    ModelListResponse,
)
from app.ai_gateway.services.gateway_service import GatewayService
from app.database import get_account_db

router = APIRouter(prefix="/api/v1/ai-gateway/v1", tags=["AI Gateway - OpenAI-Compatible Ingress"])
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


async def _sse_chunk_generator(stream_iter: AsyncIterator[ChatCompletionChunk]) -> AsyncIterator[str]:
    """Format ChatCompletionChunk objects into standard SSE data chunks."""
    try:
        async for chunk in stream_iter:
            chunk_json = chunk.model_dump_json(exclude_none=True)
            yield f"data: {chunk_json}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error("Error during streaming SSE generation: %s", e)
        err_payload = json.dumps({"error": {"message": str(e), "type": "gateway_error"}})
        yield f"data: {err_payload}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible Chat Completions endpoint with streaming and failover."""
    workspace_id = _get_workspace_id(request)
    user_id = request.headers.get("X-User-Id") or None

    if body.stream:
        stream_iter = GatewayService.chat_stream(
            db=db,
            request=body,
            workspace_id=workspace_id,
            user_id=user_id,
            caller_type="direct_api",
            caller_id=body.user,
        )
        return StreamingResponse(
            _sse_chunk_generator(stream_iter),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            return await GatewayService.chat_complete(
                db=db,
                request=body,
                workspace_id=workspace_id,
                user_id=user_id,
                caller_type="direct_api",
                caller_id=body.user,
            )
        except ValueError as val_err:
            raise HTTPException(status_code=404, detail=str(val_err))
        except Exception as exc:
            logger.error("Chat completion error: %s", exc)
            raise HTTPException(status_code=502, detail=str(exc))


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    body: EmbeddingRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible vector embeddings endpoint."""
    texts = [body.input] if isinstance(body.input, str) else body.input
    workspace_id = _get_workspace_id(request)

    try:
        raw_embeddings = await GatewayService.embed(
            db=db,
            texts=texts,
            model_name_or_id=body.model,
            workspace_id=workspace_id,
        )
        data_items = [
            EmbeddingData(object="embedding", index=i, embedding=emb)
            for i, emb in enumerate(raw_embeddings)
        ]
        return EmbeddingResponse(
            data=data_items,
            model=body.model,
        )
    except Exception as exc:
        logger.error("Embedding generation error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/models", response_model=ModelListResponse)
def list_models(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """OpenAI-compatible list models endpoint."""
    workspace_id = _get_workspace_id(request)
    query = db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)  # noqa: E712
    if workspace_id:
        query = query.filter((AIModelEndpoint.workspace_id == workspace_id) | (AIModelEndpoint.workspace_id.is_(None)))
    endpoints = query.all()

    model_items = [
        ModelItem(
            id=ep.name,
            provider_type=getattr(ep.provider.provider_type, "value", ep.provider.provider_type) if ep.provider else "unknown",
            is_default=ep.is_default,
            use_for_embedding=ep.use_for_embedding,
        )
        for ep in endpoints
    ]
    return ModelListResponse(data=model_items)
