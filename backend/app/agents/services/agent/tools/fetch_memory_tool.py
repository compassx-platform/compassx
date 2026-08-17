"""SQL-based Fetch Memory tool — retrieves persistent facts about the current user."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class FetchMemoryTool(BaseTool):
    """Retrieve relevant semantic memory entries (facts about the user) recorded from past conversations."""

    key = "fetch_memory"
    name = "Fetch Memory"
    description = (
        "Retrieve relevant semantic memory entries (facts about the user) recorded from past conversations. "
        "Use this to fetch user preferences, technical setups, domain knowledge, or past goals."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "fact_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["asset", "schema", "preference", "skill", "goal", "convention", "domain"],
                },
                "description": "Optional list of fact types to filter by.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tags to filter by. Retrieved facts must contain at least one of these tags.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of memory entries to return (default is 10).",
                "default": 10,
            },
        },
    }

    def __init__(
        self,
        session_id: int | None = None,
        db: Session | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        self._session_id = session_id
        self._db = db
        self._user_id = user_id
        self._workspace_id = workspace_id

    @property
    def _is_sentinel(self) -> bool:
        return self._session_id is None

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        if self._is_sentinel:
            raise RuntimeError(
                "FetchMemoryTool sentinel cannot be executed directly. "
                "A live instance with runtime context must be used."
            )

        _db = self._db or db

        user_id = self._user_id or "default_user"
        workspace_id = self._workspace_id or "default"

        # Fall back to session tracker if not explicitly provided
        if (not self._user_id or not self._workspace_id) and self._session_id is not None:
            try:
                from app.memory import memory_orchestrator
                if memory_orchestrator and memory_orchestrator.session_tracker:
                    session_info = memory_orchestrator.session_tracker._sessions.get(str(self._session_id))
                    if session_info:
                        if not self._user_id:
                            user_id = session_info.get("user_id", "default_user")
                        if not self._workspace_id:
                            workspace_id = session_info.get("workspace_id", "default")
            except Exception as e:
                logger.error("Error retrieving user_id/workspace_id from session tracker: %s", e)

        # Build SQL query dynamically based on parameters
        conditions = ["user_id = :user_id", "workspace_id = :workspace_id", "is_active = TRUE"]
        params: dict[str, Any] = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "limit": args.get("limit", 10) or 10,
        }

        fact_types = args.get("fact_types")
        if fact_types:
            conditions.append("fact_type = ANY(:fact_types)")
            params["fact_types"] = fact_types

        tags = args.get("tags")
        if tags:
            conditions.append("tags && :tags")
            params["tags"] = [t.lower() for t in tags]

        query_str = f"""
            SELECT id, fact, fact_type, tags, confidence, tier, created_at, last_reinforced_at
            FROM ai.agent_memory
            WHERE {" AND ".join(conditions)}
            ORDER BY last_reinforced_at DESC
            LIMIT :limit
        """

        start_time = time.monotonic()
        returned_facts = []
        try:
            rows = _db.execute(text(query_str), params).fetchall()
            for r in rows:
                returned_facts.append({
                    "id": str(r[0]),
                    "fact": r[1],
                    "fact_type": r[2],
                    "tags": r[3] or [],
                    "confidence": r[4],
                    "tier": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                    "last_reinforced_at": r[7].isoformat() if r[7] else None,
                })
        except Exception as e:
            logger.error("Error executing fetch_memory query: %s", e)
            return ToolResult(ok=False, error=f"Database query failed: {e}")

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Log retrieval to memory_retrieval_log
        if self._session_id is not None:
            try:
                log_query = text("""
                    INSERT INTO ai.memory_retrieval_log (
                        session_id, user_id, agent_id, fact_types, tags_queried, facts_returned, triggered_by, latency_ms
                    ) VALUES (
                        :session_id, :user_id, :agent_id, :fact_types, :tags_queried, :facts_returned, :triggered_by, :latency_ms
                    )
                """)
                facts_uuids = []
                for f in returned_facts:
                    try:
                        facts_uuids.append(uuid.UUID(f["id"]))
                    except ValueError:
                        pass

                _db.execute(log_query, {
                    "session_id": str(self._session_id),
                    "user_id": user_id,
                    "agent_id": str(agent.id),
                    "fact_types": fact_types or None,
                    "tags_queried": [t.lower() for t in tags] if tags else None,
                    "facts_returned": facts_uuids if facts_uuids else None,
                    "triggered_by": "tool_call",
                    "latency_ms": duration_ms,
                })
                _db.commit()
            except Exception as e:
                logger.error("Error logging memory retrieval: %s", e)

        return ToolResult(ok=True, result={"facts": returned_facts})
