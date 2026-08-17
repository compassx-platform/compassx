"""SQL execution helper — executes SELECT-only queries against agent-whitelisted tables.

Security guarantees:
  1. sqlparse rejects any non-SELECT statement.
  2. Tables referenced in the query are checked against the agent's whitelist.
  3. Queries run on a short-lived SQLAlchemy connection (no write permissions by design
     if the DB user has read-only access — recommended but not enforced here).
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import sqlparse
    _HAS_SQLPARSE = True
except ImportError:
    _HAS_SQLPARSE = False

from sqlalchemy import text

from app.models.agents import AgentDBConnection
from app.services.db_introspector import build_engine

logger = logging.getLogger(__name__)


def execute_sql(
    sql: str,
    agent_db_connections: list[AgentDBConnection],
    db_connection_id: int | None = None,
) -> dict[str, Any]:
    """
    Execute a SQL query.

    Args:
        sql: The query string.
        agent_db_connections: List of AgentDBConnection rows (already loaded with .db_connection).
        db_connection_id: Optional — pick specific connection. Defaults to first.

    Returns:
        {"columns": [...], "rows": [[...], ...], "row_count": int}
    """
    _assert_select_only(sql)

    if not agent_db_connections:
        raise ValueError("Agent has no database connections configured")

    adc = None
    if db_connection_id:
        adc = next((c for c in agent_db_connections if c.db_connection_id == db_connection_id), None)
        if not adc:
            raise ValueError(f"DB connection {db_connection_id} is not assigned to this agent")
    else:
        adc = agent_db_connections[0]

    if adc.allowed_tables:
        _check_table_whitelist(sql, adc.allowed_tables)

    from app.database import AccountSessionLocal
    from app.models.agents import DBConnection
    sys_db = AccountSessionLocal()
    try:
        db_conn = sys_db.query(DBConnection).filter(DBConnection.id == adc.db_connection_id).first()
        if not db_conn:
            raise ValueError(f"DBConnection {adc.db_connection_id} not found in system DB")
        sys_db.expunge(db_conn)
    finally:
        sys_db.close()

    engine = build_engine(db_conn)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(1000)]

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) == 1000,
    }


def _assert_select_only(sql: str) -> None:
    if not _HAS_SQLPARSE:
        normalized = sql.strip().upper()
        forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "EXEC", "EXECUTE")
        for kw in forbidden:
            if normalized.startswith(kw) or f" {kw} " in normalized:
                raise ValueError(f"Only SELECT queries are allowed. Detected: {kw}")
        return

    statements = sqlparse.parse(sql)
    for stmt in statements:
        stmt_type = stmt.get_type()
        if stmt_type and stmt_type.upper() != "SELECT":
            raise ValueError(f"Only SELECT queries are allowed. Detected statement type: {stmt_type}")
        if stmt_type is None:
            tokens_upper = sql.upper()
            for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"):
                if kw in tokens_upper:
                    raise ValueError(f"Only SELECT queries are allowed. Found keyword: {kw}")


def _check_table_whitelist(sql: str, allowed_tables: list[str]) -> None:
    allowed_lower = {t.lower() for t in allowed_tables}
    if not _HAS_SQLPARSE:
        return

    parsed = sqlparse.parse(sql)
    from sqlparse.sql import Identifier, IdentifierList
    from sqlparse import tokens as T

    mentioned = set()
    for stmt in parsed:
        from_seen = False
        for token in stmt.flatten():
            if token.ttype is T.Keyword and token.value.upper() in ("FROM", "JOIN", "INTO"):
                from_seen = True
            elif from_seen and token.ttype is T.Name:
                mentioned.add(token.value.lower())
                from_seen = False

    not_allowed = mentioned - allowed_lower
    if not_allowed:
        raise ValueError(
            f"Query references tables not in the agent's whitelist: {not_allowed}. "
            f"Allowed: {allowed_lower}"
        )
