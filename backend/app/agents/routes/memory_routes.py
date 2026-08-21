"""Routes for session lifecycle."""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Session"])


@router.post("/api/v1/sessions/{session_id}/close")
async def close_session(session_id: str):
    """Acknowledge session close."""
    return {"status": "ok"}
