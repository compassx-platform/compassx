from __future__ import annotations

import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.models.agents import Agent
from app.catalog.models import (
    UnifiedCatalog,
    UnifiedCatalogTable,
    UnifiedCatalogSchema,
    UnifiedCatalogNotebook,
    UnifiedCatalogVolume,
    UnifiedCatalogDashboard,
)
from app.catalog.search_models import CatalogSearchAsset
from app.catalog.embedding_service import get_embedding

logger = logging.getLogger(__name__)


def _get_allowed_catalogs(workspace_id: str | None, db: Session) -> list[str] | None:
    if not workspace_id:
        return None
    from app.catalog.models import UnifiedCatalog, CatalogWorkspaceBinding
    rows = (
        db.query(UnifiedCatalog.name)
        .outerjoin(CatalogWorkspaceBinding)
        .filter(
            (UnifiedCatalog.all_workspaces == True) |
            (CatalogWorkspaceBinding.workspace_id == workspace_id)
        )
        .all()
    )
    return [r[0] for r in rows]


def _is_catalog_allowed(workspace_id: str | None, catalog_name: str, db: Session) -> bool:
    if not workspace_id:
        return True
    from app.catalog.models import UnifiedCatalog, CatalogWorkspaceBinding
    exists = (
        db.query(UnifiedCatalog)
        .outerjoin(CatalogWorkspaceBinding)
        .filter(
            UnifiedCatalog.name == catalog_name,
            (UnifiedCatalog.all_workspaces == True) |
            (CatalogWorkspaceBinding.workspace_id == workspace_id)
        )
        .first()
    )
    return exists is not None


CATALOG_OPERATIONS = [
    "search_catalog",
    "get_asset_schema",
    "get_asset_details",
    "check_data_coverage",
    "resolve_entity",
    "list_related_assets",
    "sync_foreign_catalog",
]


class CatalogTool(BaseTool):
    key = "catalog"
    name = "Catalog Manager"
    description = (
        "Discover and inspect data assets — tables, notebooks, dashboards, queries, volumes, and models — "
        "registered in the CompassX catalog. Choose one operation and pass its arguments in payload."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": CATALOG_OPERATIONS,
                "description": "The Catalog operation to execute.",
            },
            "payload": {
                "type": "object",
                "description": "Operation-specific parameters.",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (used for 'search_catalog').",
                    },
                    "object_type": {
                        "type": "string",
                        "enum": [
                            "all",
                            "table",
                            "notebook",
                            "dashboard",
                            "query",
                            "volume",
                            "model",
                            "foreign_table",
                        ],
                        "description": "Filter by object type (used for 'search_catalog' and 'get_asset_details').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (used for 'search_catalog').",
                    },
                    "full_name": {
                        "type": "string",
                        "description": "FQN format: catalog.schema.table (used for 'get_asset_schema', 'get_asset_details', 'check_data_coverage', 'list_related_assets').",
                    },
                    "filters": {
                        "type": "object",
                        "description": "Key-value filter pairs, e.g. {'asset_id': 123} (used for 'check_data_coverage').",
                    },
                    "entity_name": {
                        "type": "string",
                        "description": "Turbine tag, site name, label, etc. (used for 'resolve_entity').",
                    },
                    "candidate_table": {
                        "type": "string",
                        "description": "Optional table to search within (used for 'resolve_entity').",
                    },
                    "candidate_column": {
                        "type": "string",
                        "description": "Optional column to search within (used for 'resolve_entity').",
                    },
                    "connection_id": {
                        "type": "integer",
                        "description": "ID of the external connection (used for 'sync_foreign_catalog').",
                    },
                    "foreign_catalog_name": {
                        "type": "string",
                        "description": "Name for the foreign catalog (used for 'sync_foreign_catalog').",
                    },
                },
                "additionalProperties": False,
            },
        },
        "required": ["operation", "payload"],
        "additionalProperties": False,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        operation = str(args.get("operation") or "")
        payload = args.get("payload") or {}

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="payload must be an object")

        from app.database import AccountSessionLocal
        account_db = AccountSessionLocal()
        try:
            if operation == "search_catalog":
                res = self._search_catalog(db, payload, agent, account_db)
            elif operation == "get_asset_schema":
                res = self._get_asset_schema(account_db, payload, agent)
            elif operation == "get_asset_details":
                res = self._get_asset_details(account_db, payload, agent)
            elif operation == "check_data_coverage":
                res = self._check_data_coverage(account_db, payload, agent)
            elif operation == "resolve_entity":
                res = self._resolve_entity(account_db, payload, agent)
            elif operation == "list_related_assets":
                res = self._list_related_assets(account_db, payload, agent)
            elif operation == "sync_foreign_catalog":
                res = self._sync_foreign_catalog(account_db, payload, agent)
            else:
                return ToolResult(
                    ok=False,
                    error=f"Unsupported catalog operation: {operation}",
                    result={
                        "error": True,
                        "message": f"Unsupported catalog operation: {operation}",
                        "tool": operation,
                    },
                )

            return ToolResult(ok=True, result=res)
        except Exception as exc:
            logger.exception("Catalog operation %s failed: %s", operation, exc)
            return ToolResult(
                ok=False,
                error=str(exc),
                result={
                    "error": True,
                    "message": str(exc),
                    "tool": operation,
                },
            )
        finally:
            account_db.close()

    # 3.1 search_catalog
    def _search_catalog(self, db: Session, payload: dict[str, Any], agent: Agent, account_db: Session) -> dict[str, Any]:
        query_text = str(payload.get("query") or "").strip()
        if not query_text:
            raise ValueError("query must be a non-empty string")

        object_type = payload.get("object_type")
        if object_type == "all":
            object_type = None
        limit = min(int(payload.get("limit") or 10), 25)
        if limit < 1:
            limit = 1

        query_vec = get_embedding(query_text)
        if query_vec is None:
            raise ValueError("Could not generate query embeddings. Ensure LLM embedding model is configured.")

        allowed_catalogs = _get_allowed_catalogs(agent.workspace_id, account_db)
        if allowed_catalogs is not None and not allowed_catalogs:
            return {"query": query_text, "results": [], "count": 0}

        # Cosine similarity SQL
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
        from app.database import account_engine

        conditions = ["embedding IS NOT NULL"]
        bind_params: dict[str, Any] = {
            "query_vec": vec_literal,
            "object_type_filter": object_type,
            "limit": limit,
        }

        if object_type is not None:
            conditions.append("object_type = :object_type_filter")

        if allowed_catalogs is not None:
            conditions.append("catalog_name IN :allowed_catalogs")
            bind_params["allowed_catalogs"] = tuple(allowed_catalogs)

        sql = f"""
        SELECT
            catalog_name || '.' || schema_name || '.' || object_name AS full_name,
            object_type,
            description,
            is_foreign,
            1 - (embedding <=> :query_vec ::vector) AS similarity_score
        FROM vector_db.assets
        WHERE {" AND ".join(conditions)}
        ORDER BY embedding <=> :query_vec ::vector
        LIMIT :limit
        """

        with account_engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                bind_params,
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
        return {"query": query_text, "results": results, "count": len(results)}

    # 3.2 get_asset_schema
    def _get_asset_schema(self, db: Session, payload: dict[str, Any], agent: Agent) -> dict[str, Any]:
        full_name = str(payload.get("full_name") or "")
        if not full_name:
            raise ValueError("full_name is required")

        parts = full_name.split(".")
        if len(parts) != 3:
            raise ValueError("full_name must be in catalog.schema.table format")
        catalog_name = parts[0]
        if not _is_catalog_allowed(agent.workspace_id, catalog_name, db):
            raise ValueError(f"Access denied to catalog '{catalog_name}' in this workspace")

        from app.catalog.service import get_table
        table_read = get_table(db, full_name)
        columns = [
            {
                "column_name": col.name,
                "data_type": col.data_type,
                "description": col.description,
                "is_nullable": col.nullable,
                "ordinal_position": col.ordinal,
            }
            for col in table_read.columns
        ]
        return {
            "full_name": full_name,
            "description": table_read.description,
            "columns": columns,
            "row_count_estimate": table_read.properties.get("row_estimate") or 0,
        }

    # 3.3 get_asset_details
    def _get_asset_details(self, db: Session, payload: dict[str, Any], agent: Agent) -> dict[str, Any]:
        full_name = str(payload.get("full_name") or "")
        object_type = str(payload.get("object_type") or "")
        if not full_name or not object_type:
            raise ValueError("full_name and object_type are required")

        parts = full_name.split(".")
        if len(parts) != 3:
            raise ValueError("full_name must be in catalog.schema.name format")
        catalog_name, schema_name, object_name = parts

        if not _is_catalog_allowed(agent.workspace_id, catalog_name, db):
            raise ValueError(f"Access denied to catalog '{catalog_name}' in this workspace")

        asset = db.query(CatalogSearchAsset).filter(
            CatalogSearchAsset.catalog_name == catalog_name,
            CatalogSearchAsset.schema_name == schema_name,
            CatalogSearchAsset.object_name == object_name,
            CatalogSearchAsset.object_type == object_type
        ).first()

        def _dt(v):
            return v.isoformat() if v is not None else None

        metadata = {
            "id": asset.id if asset else None,
            "catalog": catalog_name,
            "schema_name": schema_name,
            "name": object_name,
            "object_type": object_type,
            "description": asset.description if asset else None,
            "created_at": _dt(asset.created_at) if asset else None,
            "updated_at": _dt(asset.updated_at) if asset else None,
        }

        if object_type == "table":
            table = db.query(UnifiedCatalogTable).join(UnifiedCatalogSchema).join(UnifiedCatalog).filter(
                UnifiedCatalog.name == catalog_name,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogTable.name == object_name
            ).first()
            if table:
                metadata.update({
                    "table_type": table.table_type.value if hasattr(table.table_type, "value") else table.table_type,
                    "owner": table.owner,
                    "properties": table.properties,
                    "storage_location": table.storage_location,
                    "metadata_location": table.metadata_location,
                    "is_foreign": asset.is_foreign if asset else False,
                    "last_synced_at": _dt(asset.last_synced_at) if asset else None,
                })
        elif object_type == "notebook":
            notebook = db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == catalog_name,
                UnifiedCatalogNotebook.schema_name == schema_name,
                UnifiedCatalogNotebook.name == object_name
            ).first()
            if notebook:
                metadata.update({
                    "owner": notebook.owner,
                    "blob_path": notebook.blob_path,
                    "comment": notebook.comment,
                })
        elif object_type == "dashboard":
            dashboard = db.query(UnifiedCatalogDashboard).filter(
                UnifiedCatalogDashboard.catalog_name == catalog_name,
                UnifiedCatalogDashboard.schema_name == schema_name,
                UnifiedCatalogDashboard.name == object_name
            ).first()
            if dashboard:
                metadata.update({
                    "owner": dashboard.owner,
                    "dashboard_id": dashboard.dashboard_id,
                    "comment": dashboard.comment,
                })
        elif object_type == "volume":
            volume = db.query(UnifiedCatalogVolume).join(UnifiedCatalogSchema).join(UnifiedCatalog).filter(
                UnifiedCatalog.name == catalog_name,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogVolume.name == object_name
            ).first()
            if volume:
                metadata.update({
                    "owner": volume.owner,
                    "storage_location": volume.storage_location,
                })
        return metadata

    # 3.4 check_data_coverage
    def _check_data_coverage(self, db: Session, payload: dict[str, Any], agent: Agent) -> dict[str, Any]:
        full_name = str(payload.get("full_name") or "")
        filters = payload.get("filters") or {}
        if not full_name:
            raise ValueError("full_name is required")

        parts = full_name.split(".")
        if len(parts) != 3:
            raise ValueError("full_name must be in catalog.schema.table format")

        catalog_name = parts[0]
        if not _is_catalog_allowed(agent.workspace_id, catalog_name, db):
            raise ValueError(f"Access denied to catalog '{catalog_name}' in this workspace")

        # Get table columns to determine the date range column
        from app.catalog.service import get_table
        try:
            table_read = get_table(db, full_name)
            columns = table_read.columns
        except Exception:
            columns = []

        where_parts = []
        params = []

        for k, v in filters.items():
            if k == "date_range":
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    # Resolve date column
                    date_col = None
                    for col in columns:
                        dt_lower = col.data_type.lower()
                        col_lower = col.name.lower()
                        if dt_lower in ("timestamp", "timestamptz", "datetime", "date") or col_lower in ("timestamp", "time", "date", "created_at", "dt"):
                            date_col = col.name
                            break
                    if not date_col:
                        date_col = "timestamp"
                    
                    where_parts.append(f"{date_col} >= ? AND {date_col} <= ?")
                    params.append(v[0])
                    params.append(v[1])
            else:
                col_name = k
                where_parts.append(f"{col_name} = ?")
                params.append(v)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        import duckdb
        from app.sql_warehouse.catalog.duckdb_resolver import build_duckdb_catalog_plan

        plan = build_duckdb_catalog_plan(db)
        conn = duckdb.connect(":memory:")
        try:
            for stmt in plan.setup_sql:
                conn.execute(stmt)

            # Query exists
            exists_sql = f"SELECT EXISTS(SELECT 1 FROM {full_name} WHERE {where_clause} LIMIT 1)"
            exists_res = conn.execute(exists_sql, params).fetchone()
            exists = bool(exists_res[0]) if exists_res else False

            # Query sample row count
            sample_sql = f"SELECT * FROM {full_name} WHERE {where_clause} LIMIT 5"
            sample_rows = conn.execute(sample_sql, params).fetchall()
            sample_row_count = len(sample_rows)

            return {"exists": exists, "sample_row_count": sample_row_count}
        finally:
            conn.close()

    # 3.5 resolve_entity
    def _resolve_entity(self, db: Session, payload: dict[str, Any], agent: Agent) -> dict[str, Any]:
        entity_name = str(payload.get("entity_name") or "")
        candidate_table = payload.get("candidate_table")
        candidate_column = payload.get("candidate_column")

        if not entity_name:
            raise ValueError("entity_name is required")

        import duckdb
        from app.sql_warehouse.catalog.duckdb_resolver import build_duckdb_catalog_plan
        plan = build_duckdb_catalog_plan(db)

        if candidate_table and candidate_column:
            parts = candidate_table.split(".")
            if len(parts) == 3:
                catalog_name = parts[0]
                if not _is_catalog_allowed(agent.workspace_id, catalog_name, db):
                    raise ValueError(f"Access denied to catalog '{catalog_name}' in this workspace")

            conn = duckdb.connect(":memory:")
            try:
                for stmt in plan.setup_sql:
                    conn.execute(stmt)
                sql = f"SELECT * FROM {candidate_table} WHERE LOWER({candidate_column}) = LOWER(?) LIMIT 1"
                row = conn.execute(sql, [entity_name]).fetchone()
                if row:
                    desc = conn.execute(f"SELECT * FROM {candidate_table} LIMIT 0").description
                    cols = [d[0] for d in desc]
                    row_dict = dict(zip(cols, row))
                    # Find id or key column, else default to candidate_column value
                    resolved_id = None
                    for c in ["id", "uuid", "key", "name"]:
                        if c in row_dict:
                            resolved_id = row_dict[c]
                            break
                    if resolved_id is None:
                        resolved_id = row_dict.get(candidate_column)
                    return {
                        "resolved_id": resolved_id,
                        "matched_column": candidate_column,
                        "table": candidate_table
                    }
            finally:
                conn.close()
            return {}

        # Best effort search: query all tables and check common columns
        # Get tables registered in search index
        allowed_catalogs = _get_allowed_catalogs(agent.workspace_id, db)
        if allowed_catalogs is not None and not allowed_catalogs:
            return {}

        query = db.query(CatalogSearchAsset).filter(CatalogSearchAsset.object_type == "table")
        if allowed_catalogs is not None:
            query = query.filter(CatalogSearchAsset.catalog_name.in_(allowed_catalogs))
        assets = query.all()
        candidate_cols = ["name", "tag", "asset_name", "code", "label", "title", "id", "uuid"]

        conn = duckdb.connect(":memory:")
        try:
            for stmt in plan.setup_sql:
                conn.execute(stmt)

            for asset in assets:
                tbl_fqn = f"{asset.catalog_name}.{asset.schema_name}.{asset.object_name}"
                # Get table columns
                try:
                    desc = conn.execute(f"SELECT * FROM {tbl_fqn} LIMIT 0").description
                    cols = [d[0].lower() for d in desc]
                except Exception:
                    continue

                for col in candidate_cols:
                    if col in cols:
                        try:
                            sql = f"SELECT * FROM {tbl_fqn} WHERE LOWER({col}) = LOWER(?) LIMIT 1"
                            row = conn.execute(sql, [entity_name]).fetchone()
                            if row:
                                row_dict = dict(zip([d[0] for d in desc], row))
                                resolved_id = None
                                for id_col in ["id", "uuid", "key"]:
                                    if id_col in row_dict:
                                        resolved_id = row_dict[id_col]
                                        break
                                if resolved_id is None:
                                    resolved_id = row_dict.get(col)
                                return {
                                    "resolved_id": resolved_id,
                                    "matched_column": col,
                                    "table": tbl_fqn
                                }
                        except Exception:
                            continue
        finally:
            conn.close()

        return {}

    # 3.6 list_related_assets
    def _list_related_assets(self, db: Session, payload: dict[str, Any], agent: Agent) -> list[dict[str, Any]]:
        full_name = str(payload.get("full_name") or "")
        if not full_name:
            raise ValueError("full_name is required")

        parts = full_name.split(".")
        if len(parts) != 3:
            raise ValueError("full_name must be in catalog.schema.table format")

        catalog_name, schema_name, table_name = parts
        if not _is_catalog_allowed(agent.workspace_id, catalog_name, db):
            raise ValueError(f"Access denied to catalog '{catalog_name}' in this workspace")

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog or catalog.catalog_type != "postgres" or not catalog.connection_id:
            return []

        from app.models.agents import DBConnection
        from app.agents.services.db_introspector import build_engine
        from sqlalchemy import inspect

        db_conn = db.query(DBConnection).filter(DBConnection.id == catalog.connection_id).first()
        if not db_conn:
            return []
        db.expunge(db_conn)

        try:
            engine = build_engine(db_conn)
            inspector = inspect(engine)
            fk_info = inspector.get_foreign_keys(table_name, schema=schema_name)
            related = []
            for fk in fk_info:
                referred_table = fk.get("referred_table")
                referred_schema = fk.get("referred_schema") or schema_name
                constrained_cols = fk.get("constrained_columns", [])
                join_col = constrained_cols[0] if constrained_cols else None
                related.append({
                    "related_table": f"{catalog_name}.{referred_schema}.{referred_table}",
                    "relationship_type": "foreign_key",
                    "join_column": join_col
                })
            return related
        except Exception as exc:
            logger.warning("Failed to introspect foreign keys for %s: %s", full_name, exc)
            return []

    # 3.7 sync_foreign_catalog
    def _sync_foreign_catalog(self, db: Session, payload: dict[str, Any], agent: Agent) -> dict[str, Any]:
        connection_id_raw = payload.get("connection_id")
        foreign_catalog_name = payload.get("foreign_catalog_name")

        if connection_id_raw is None or not foreign_catalog_name:
            raise ValueError("connection_id and foreign_catalog_name are required")

        if not _is_catalog_allowed(agent.workspace_id, foreign_catalog_name, db):
            raise ValueError(f"Access denied to catalog '{foreign_catalog_name}' in this workspace")

        connection_id = int(connection_id_raw)

        from app.catalog.foreign_sync import sync_foreign_catalog
        user_id = str(agent.id)  # Using agent id as the triggering entity for logging

        res = sync_foreign_catalog(
            db,
            connection_id=connection_id,
            foreign_catalog_name=foreign_catalog_name,
            triggered_by_user_id=user_id,
        )
        return res


# Register tool dynamically to avoid circular imports
try:
    from app.agents.services.agent.tools.registry import TOOL_REGISTRY, TOOL_MAP
    _instance = CatalogTool()
    if _instance.key not in TOOL_MAP:
        TOOL_REGISTRY.append(_instance)
        TOOL_MAP[_instance.key] = _instance
except Exception as e:
    logger.error("Failed to register CatalogTool dynamically: %s", e)

