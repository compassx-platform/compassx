from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.platform.sql_warehouse.operations import (
    SQL_WAREHOUSE_OPERATIONS,
    execute_sql_warehouse_operation,
)


class SqlWarehouseTool(BaseTool):
    key = "sql_warehouse"
    name = "SQL Warehouse"
    description = (
        "Execute SQL queries against CompassX SQL Warehouses (DuckDB, ClickHouse, Postgres, Iceberg catalog tables), "
        "inspect warehouse availability, get execution plans, and check query history. "
        "All queries are executed and tracked in the SQL Warehouse audit log. "
        "You can execute a query directly by passing 'sql' parameter or choose an operation with a payload."
    )
    is_async = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": SQL_WAREHOUSE_OPERATIONS,
                "description": (
                    "The SQL Warehouse operation to execute. "
                    "Options: 'execute_query' (default), 'list_warehouses', 'get_warehouse', "
                    "'explain_query', 'get_query_history', 'get_query_result'."
                ),
            },
            "sql": {
                "type": "string",
                "description": "SQL statement to execute (can be supplied directly or in payload).",
            },
            "warehouse_id": {
                "type": "string",
                "description": "Optional ID or name of the SQL Warehouse. Defaults to the active running warehouse in the workspace.",
            },
            "catalog": {
                "type": "string",
                "description": "Optional catalog name context (e.g. 'test_default' or 'main').",
            },
            "schema_name": {
                "type": "string",
                "description": "Optional schema name context (e.g. 'default' or 'dgr_synthetic').",
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum number of rows to return (default: 1000, max: 10000).",
                "default": 1000,
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific payload. "
                    "For execute_query: {sql, warehouse_id, catalog, schema_name, max_rows}; "
                    "For list_warehouses: {}; "
                    "For get_warehouse: {warehouse_id}; "
                    "For explain_query: {sql, warehouse_id}; "
                    "For get_query_history: {warehouse_id, limit, offset, status}; "
                    "For get_query_result: {query_id}."
                ),
                "additionalProperties": True,
            },
            "context": {
                "type": "object",
                "description": "Optional runtime context (workspace_id, user, etc.).",
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        # Determine operation and build normalized payload
        operation = str(args.get("operation") or "").strip()
        payload = args.get("payload")
        context = args.get("context") or {}

        if not isinstance(context, dict):
            context = {}

        if not isinstance(payload, dict):
            payload = {}

        # If flat parameters are provided at root level, merge them into payload
        for key in ("sql", "query", "warehouse_id", "warehouse", "catalog", "catalog_name", "schema_name", "schema", "max_rows", "query_id", "limit", "offset", "status"):
            if key in args and key not in payload:
                payload[key] = args[key]

        # Default to execute_query if SQL text is present or operation not specified
        if not operation:
            if "sql" in payload or "query" in payload:
                operation = "execute_query"
            elif "query_id" in payload:
                operation = "get_query_result"
            else:
                operation = "execute_query"

        # Inject agent workspace if available
        if agent and getattr(agent, "workspace_id", None):
            context.setdefault("workspace_id", str(agent.workspace_id))
        if agent and getattr(agent, "created_by", None):
            context.setdefault("user", str(agent.created_by))

        try:
            result = execute_sql_warehouse_operation(
                operation=operation,
                payload=payload,
                context=context,
                agent=agent,
                db=db,
            )
            return ToolResult(
                ok=result.get("ok", False),
                result=result,
                error=result.get("error"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
                result={
                    "ok": False,
                    "operation": operation,
                    "resource_type": "sql_warehouse",
                    "resource_id": payload.get("warehouse_id"),
                    "data": None,
                    "message": None,
                    "error": str(exc),
                },
            )
