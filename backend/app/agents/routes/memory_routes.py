"""Routes for agent memory management and session lifecycle."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user, get_memory_orchestrator
from app.memory.orchestrator import MemoryOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Memory"])


@router.get("/api/v1/agents/memory")
def get_user_memories(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all active semantic memory entries recorded for the current user."""
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    try:
        where_clause = "user_id = :user_id AND is_active = TRUE"
        params = {"user_id": user_id}
        if workspace_id:
            where_clause += " AND workspace_id = :workspace_id"
            params["workspace_id"] = workspace_id
        else:
            where_clause += " AND workspace_id IS NULL"

        query = text(f"""
            SELECT id, fact, fact_type, tags, confidence, tier, source, created_at, last_reinforced_at
            FROM ai.agent_memory
            WHERE {where_clause}
            ORDER BY last_reinforced_at DESC
        """)
        rows = db.execute(query, params).fetchall()
        return [
            {
                "id": str(r[0]),
                "fact": r[1],
                "fact_type": r[2],
                "tags": r[3] or [],
                "confidence": r[4],
                "tier": r[5],
                "source": r[6],
                "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else r[7],
                "last_reinforced_at": r[8].isoformat() if hasattr(r[8], "isoformat") else r[8],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Error retrieving user memories: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve memory entries.")


@router.delete("/api/v1/agents/memory/{memory_id}", status_code=204)
def delete_user_memory(
    request: Request,
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Soft delete/deactivate a memory entry belonging to the current user."""
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    try:
        where_clause = "id = :memory_id AND user_id = :user_id"
        params = {"memory_id": memory_id, "user_id": user_id}
        if workspace_id:
            where_clause += " AND workspace_id = :workspace_id"
            params["workspace_id"] = workspace_id
        else:
            where_clause += " AND workspace_id IS NULL"

        query = text(f"""
            UPDATE ai.agent_memory
            SET is_active = FALSE
            WHERE {where_clause}
        """)
        db.execute(query, params)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error deleting user memory: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete memory entry.")


@router.post("/api/v1/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    memory_orch: MemoryOrchestrator = Depends(get_memory_orchestrator),
    current_user: dict = Depends(get_current_user),
):
    """Explicitly closes a chat session and triggers background fact extraction.

    Frontend call instructions:
    - Invoke on chat panel close / component unmount
    - Invoke on clicking the 'New Conversation' button
    - Invoke on browser 'beforeunload' event (best effort)
    """
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    workspace_id = current_user.get("org_id") or "default"

    await memory_orch.on_activity(session_id, user_id, workspace_id)
    await memory_orch.on_explicit_close(session_id)

    return {"status": "ok"}


@router.get("/api/v1/agents/memory/logs")
def get_memory_logs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all memory extraction logs recorded for the current user."""
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    try:
        where_clause = "user_id = :user_id"
        params = {"user_id": user_id}
        if workspace_id:
            where_clause += " AND workspace_id = :workspace_id"
            params["workspace_id"] = workspace_id
        else:
            where_clause += " AND workspace_id IS NULL"

        query = text(f"""
            SELECT id, session_id, trigger, turns_processed, facts_extracted, facts_created, facts_merged, status, error, started_at, completed_at
            FROM ai.memory_extraction_log
            WHERE {where_clause}
            ORDER BY started_at DESC
            LIMIT 50
        """)
        rows = db.execute(query, params).fetchall()
        return [
            {
                "id": str(r[0]),
                "session_id": r[1],
                "trigger": r[2],
                "turns_processed": r[3],
                "facts_extracted": r[4],
                "facts_created": r[5],
                "facts_merged": r[6],
                "status": r[7],
                "error": r[8],
                "started_at": r[9].isoformat() if r[9] else None,
                "completed_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("Error retrieving memory logs: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve memory extraction logs.")
