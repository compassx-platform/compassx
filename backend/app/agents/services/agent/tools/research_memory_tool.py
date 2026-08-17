"""Research Memory tools for the Research Engine."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.memory.research_store import RESEARCH_FACT_TYPES, ResearchMemoryStore
from app.models.agents import Agent

logger = logging.getLogger(__name__)


class FetchResearchMemoryTool(BaseTool):
    key = "fetch_research_memory"
    name = "Fetch Research Memory"
    description = (
        "Fetch active Tier 2 Research Memory facts for this workspace. "
        "Use this first when assembling Research Engine context. Returns only valid active facts."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "fact_type": {
                "type": ["string", "null"],
                "enum": sorted(RESEARCH_FACT_TYPES) + [None],
                "description": "Optional research memory fact type filter.",
            },
            "scope": {
                "type": ["string", "null"],
                "description": "Optional scope filter, usually workspace, data_source_id, site_id, or asset_id.",
            },
            "tags": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Optional tag filters. Returned facts must contain at least one tag.",
            },
            "limit": {"type": "integer", "default": 50},
        },
    }

    def __init__(self, workspace_id: str | None = None) -> None:
        self._workspace_id = workspace_id

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        workspace_id = self._workspace_id or "default"
        try:
            store = ResearchMemoryStore(lambda: db, close_sessions=False)
            facts = store.fetch(
                workspace_id=workspace_id,
                fact_type=args.get("fact_type"),
                scope=args.get("scope"),
                tags=args.get("tags"),
                limit=args.get("limit") or 50,
            )
            return ToolResult(ok=True, result={"facts": facts}, duration_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            logger.error("fetch_research_memory failed: %s", e)
            return ToolResult(ok=False, error=str(e), duration_ms=int((time.monotonic() - start) * 1000))


class SaveResearchMemoryTool(BaseTool):
    key = "save_research_memory"
    name = "Save Research Memory"
    description = (
        "Save a high-confidence deployment-specific fact directly to Tier 2 Research Memory. "
        "Use during Research Engine proposal conversations when the user states a durable priority, constraint, convention, rejection reason, strategic decision, or data trust signal."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "required": ["fact", "fact_type", "confidence", "scope", "tags"],
        "properties": {
            "fact": {"type": "string"},
            "fact_type": {"type": "string", "enum": sorted(RESEARCH_FACT_TYPES)},
            "confidence": {"type": "number", "minimum": 0.8, "maximum": 1.0},
            "scope": {"type": "string", "description": "workspace, data_source_id, site_id, or asset_id."},
            "tags": {"type": "array", "items": {"type": "string"}},
            "source_type": {
                "type": "string",
                "enum": ["notebook", "data_profiler", "research_engine", "query", "dashboard"],
                "default": "research_engine",
            },
        },
    }

    def __init__(self, session_id: int | None = None, workspace_id: str | None = None) -> None:
        self._session_id = session_id
        self._workspace_id = workspace_id

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        workspace_id = self._workspace_id or "default"
        try:
            store = ResearchMemoryStore(lambda: db, close_sessions=False)
            result = store.save(
                workspace_id=workspace_id,
                fact=args["fact"],
                fact_type=args["fact_type"],
                confidence=float(args["confidence"]),
                source_agent=agent.name,
                source_session_id=str(self._session_id) if self._session_id is not None else None,
                source_type=args.get("source_type") or "research_engine",
                promoted_via="user_stated_in_engine",
                scope=args.get("scope") or "workspace",
                tags=args.get("tags") or [],
            )
            return ToolResult(ok=True, result=result, duration_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            logger.error("save_research_memory failed: %s", e)
            return ToolResult(ok=False, error=str(e), duration_ms=int((time.monotonic() - start) * 1000))

