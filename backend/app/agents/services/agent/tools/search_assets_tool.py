"""search_assets agent tool — semantic search across catalog objects.

Implements the search_assets tool spec from architecture/agents/semantic_search.md §7.
Embeds the query using Voyage AI, runs a cosine-similarity nearest-neighbour
# Embeds the query and runs a cosine-similarity nearest-neighbour
# query against vector_db.assets, and returns ranked results.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.catalog.embedding_service import get_embedding

logger = logging.getLogger(__name__)

_VALID_OBJECT_TYPES = frozenset(
    ["all", "table", "notebook", "dashboard", "query", "volume", "model", "foreign_table"]
)

_SEARCH_SQL = """
SELECT
    catalog_name || '.' || schema_name || '.' || object_name AS full_name,
    object_type,
    description,
    is_foreign,
    1 - (embedding <=> :query_vec ::vector) AS similarity_score
FROM vector_db.assets
WHERE embedding IS NOT NULL
  AND (:object_type_filter ::text IS NULL OR object_type = :object_type_filter)
ORDER BY embedding <=> :query_vec ::vector
LIMIT :limit
"""


class SearchAssetsTool(BaseTool):
    """Semantic search across all catalog objects in the current workspace.

    Uses embeddings stored in vector_db.assets to find the
    most relevant tables, notebooks, dashboards, queries, volumes, and models
    based on a natural-language query.
    """

    key = "search_assets"
    name = "Search Catalog Assets"
    description = (
        "Semantic search across all catalog objects (tables, notebooks, dashboards, "
        "queries, volumes, models) in the current workspace. Returns objects ranked "
        "by relevance to the query."
    )
    is_async = False

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language description of what you're looking for.",
            },
            "object_type": {
                "type": "string",
                "enum": list(_VALID_OBJECT_TYPES),
                "description": "Optional filter to restrict results to one object type.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 10, max 25).",
                "default": 10,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, args: dict[str, Any], agent: Any, db: Session) -> ToolResult:
        query_text: str = args.get("query", "").strip()
        if not query_text:
            return ToolResult(ok=False, error="query must be a non-empty string")

        object_type: str | None = args.get("object_type")
        if object_type == "all":
            object_type = None
        elif object_type and object_type not in _VALID_OBJECT_TYPES:
            return ToolResult(
                ok=False,
                error=f"Invalid object_type '{object_type}'. "
                f"Must be one of: {sorted(_VALID_OBJECT_TYPES)}",
            )

        limit = min(int(args.get("limit") or 10), 25)
        if limit < 1:
            limit = 1

        # 1. Embed the query (or fallback to keyword search if embedding model is not configured)
        query_vec = get_embedding(query_text)
        from app.database import account_engine

        if query_vec is not None:
            # 2. Run cosine-similarity search against vector_db.assets
            try:
                vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"

                with account_engine.connect() as conn:
                    rows = conn.execute(
                        text(_SEARCH_SQL),
                        {
                            "query_vec": vec_literal,
                            "object_type_filter": object_type,
                            "limit": limit,
                        },
                    ).fetchall()
                results = [
                    {
                        "full_name": row.full_name,
                        "object_type": row.object_type,
                        "description": row.description,
                        "is_foreign": row.is_foreign,
                        "similarity_score": round(float(row.similarity_score), 4),
                    }
                    for row in rows
                ]
                return ToolResult(
                    ok=True,
                    result={
                        "query": query_text,
                        "results": results,
                        "count": len(results),
                    },
                )
            except Exception as exc:
                logger.error("search_assets vector query failed: %s", exc, exc_info=True)

        # Fallback to Text / Keyword ILIKE search
        logger.info("Semantic embedding not available for %r; falling back to keyword search", query_text)
        kw_sql = """
        SELECT
            catalog_name || '.' || schema_name || '.' || object_name AS full_name,
            object_type,
            description,
            is_foreign,
            1.0 AS similarity_score
        FROM vector_db.assets
        WHERE (object_name ILIKE :kw OR description ILIKE :kw OR schema_name ILIKE :kw)
        AND (:object_type_filter IS NULL OR object_type = :object_type_filter)
        LIMIT :limit
        """
        try:
            with account_engine.connect() as conn:
                rows = conn.execute(
                    text(kw_sql),
                    {
                        "kw": f"%{query_text}%",
                        "object_type_filter": object_type,
                        "limit": limit,
                    },
                ).fetchall()
            results = [
                {
                    "full_name": row.full_name,
                    "object_type": row.object_type,
                    "description": row.description,
                    "is_foreign": row.is_foreign,
                    "similarity_score": 1.0,
                }
                for row in rows
            ]
            return ToolResult(
                ok=True,
                result={
                    "query": query_text,
                    "results": results,
                    "count": len(results),
                },
            )
        except Exception as exc:
            logger.error("search_assets keyword fallback failed: %s", exc, exc_info=True)
            return ToolResult(
                ok=True,
                result={
                    "query": query_text,
                    "results": [],
                    "count": 0,
                },
            )

        return ToolResult(
            ok=True,
            result={
                "query": query_text,
                "results": results,
                "count": len(results),
            },
        )
