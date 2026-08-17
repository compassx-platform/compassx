"""SQL Query tool — executes SELECT-only queries against agent-configured databases."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.agents import Agent, AgentDBConnection
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class SqlQueryTool(BaseTool):
    key = "sql_query"
    name = "SQL Query"
    description = (
        "Execute a SQL SELECT query against the agent's configured database connections. "
        "Returns rows as a JSON array. Only SELECT statements are allowed."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "A SELECT SQL statement to execute"},
            "db_connection_id": {
                "type": "integer",
                "description": "ID of the DB connection to query (defaults to first configured)",
            },
        },
        "required": ["sql"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        from app.agents.services.agent.tools._sql_executor import execute_sql

        agent_db_conns = (
            db.query(AgentDBConnection)
            
            .filter(AgentDBConnection.agent_id == agent.id)
            .all()
        )
        result = execute_sql(
            sql=args["sql"],
            agent_db_connections=agent_db_conns,
            db_connection_id=args.get("db_connection_id"),
        )
        return ToolResult(ok=True, result=result)
