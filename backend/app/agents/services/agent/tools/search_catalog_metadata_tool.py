"""search_catalog_metadata agent tool — direct SQL metadata search for catalogs and schemas.

Queries the catalog metadata tables catalog_v2_catalogs and catalog_v2_schemas directly
instead of using the vector embeddings index.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema

logger = logging.getLogger(__name__)


class SearchCatalogMetadataTool(BaseTool):
    """Search catalogs and schemas directly from catalog database metadata tables."""

    key = "search_catalog_metadata"
    name = "Search Catalog Metadata"
    description = (
        "Search catalogs and schemas directly from the catalog database metadata tables "
        "(catalog_v2_catalogs and catalog_v2_schemas) instead of the vector embeddings index. "
        "Allows case-insensitive partial match search by name or description."
    )
    is_async = False

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search term to match against catalog/schema name or description. If omitted, lists all.",
            },
            "object_type": {
                "type": "string",
                "enum": ["all", "catalog", "schema"],
                "default": "all",
                "description": "Filter results by object type ('catalog', 'schema', or 'all').",
            },
            "catalog_name": {
                "type": "string",
                "description": "Optional catalog name filter. Only relevant when searching for schemas.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 20,
                "description": "Maximum number of results to return.",
            },
        },
        "additionalProperties": False,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        query_str = args.get("query", "").strip()
        object_type = args.get("object_type", "all")
        catalog_filter = args.get("catalog_name", "").strip()
        limit = min(int(args.get("limit") or 20), 100)

        results = []

        from app.database import AccountSessionLocal
        account_db = AccountSessionLocal()
        try:
            # 1. Search Catalogs
            if object_type in ("all", "catalog"):
                q_catalogs = account_db.query(UnifiedCatalog)
                if query_str:
                    q_catalogs = q_catalogs.filter(
                        (UnifiedCatalog.name.ilike(f"%{query_str}%")) |
                        (UnifiedCatalog.description.ilike(f"%{query_str}%"))
                    )
                catalogs = q_catalogs.order_by(UnifiedCatalog.name).limit(limit).all()
                for cat in catalogs:
                    results.append({
                        "object_type": "catalog",
                        "name": cat.name,
                        "description": cat.description,
                        "catalog_type": cat.catalog_type,
                        "database_name": cat.database_name,
                        "created_by": cat.created_by,
                        "created_at": cat.created_at.isoformat() if cat.created_at else None,
                    })

            # 2. Search Schemas
            if object_type in ("all", "schema"):
                q_schemas = account_db.query(UnifiedCatalogSchema).join(UnifiedCatalog)
                if catalog_filter:
                    q_schemas = q_schemas.filter(UnifiedCatalog.name.ilike(f"%{catalog_filter}%"))
                if query_str:
                    q_schemas = q_schemas.filter(
                        (UnifiedCatalogSchema.name.ilike(f"%{query_str}%")) |
                        (UnifiedCatalogSchema.description.ilike(f"%{query_str}%"))
                    )
                schemas = q_schemas.order_by(UnifiedCatalogSchema.name).limit(limit).all()
                for sch in schemas:
                    results.append({
                        "object_type": "schema",
                        "name": sch.name,
                        "catalog_name": sch.catalog.name,
                        "description": sch.description,
                        "created_by": sch.created_by,
                        "created_at": sch.created_at.isoformat() if sch.created_at else None,
                    })

            # Sort combined results by name
            results.sort(key=lambda x: x["name"])
            # Trim to limit if both types were fetched
            if object_type == "all":
                results = results[:limit]

            return ToolResult(
                ok=True,
                result={
                    "query": query_str,
                    "object_type": object_type,
                    "catalog_name_filter": catalog_filter or None,
                    "count": len(results),
                    "results": results,
                },
            )
        except Exception as exc:
            logger.error("search_catalog_metadata tool failed: %s", exc, exc_info=True)
            return ToolResult(ok=False, error=str(exc))
        finally:
            account_db.close()
