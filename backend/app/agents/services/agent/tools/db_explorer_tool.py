from __future__ import annotations

import logging
import re
from datetime import datetime, date, timezone
import uuid
from typing import Any

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentDBConnection, DataSourceProfile, Skill
from app.jobs.models.job import Job
from app.dashboards.models.dashboard import Dashboard
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.profiling_tools import (
    _get_adc_and_engine,
    _check_table_allowed,
)

logger = logging.getLogger(__name__)


class DatabaseExplorerTool(BaseTool):
    key = "db_explorer"
    name = "Database Explorer"
    description = (
        "Explore database metadata and query datasets. Contains atomic operations: "
        "list_tables, get_table_schema, list_table_relationships, get_data_profile, "
        "get_column_stats, get_row_count, check_value_overlap, sample_rows, run_query, "
        "search_workspace, and save_data_profile."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "list_tables",
                    "get_table_schema",
                    "list_table_relationships",
                    "get_data_profile",
                    "get_column_stats",
                    "get_row_count",
                    "check_value_overlap",
                    "sample_rows",
                    "run_query",
                    "search_workspace",
                    "save_data_profile",
                ],
                "description": "The atomic database exploration operation to run.",
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific arguments. Keys and types needed for each operation:\n"
                    "- list_tables: {} (no arguments needed).\n"
                    "- get_table_schema: {'table_name': string} (required).\n"
                    "- list_table_relationships: {'table_name': string} (required).\n"
                    "- get_data_profile: {'target_type': string (optional, defaults to 'table'), 'catalog_name': string (optional), 'schema_name': string (optional), 'table_name': string (required if target_type is table)}.\n"
                    "- get_column_stats: {'table_name': string, 'column_name': string (must be a specific column, not '*')} (required).\n"
                    "- get_row_count: {'table_name': string (required), 'filters': string (optional SQL WHERE clause)}.\n"
                    "- check_value_overlap: {'table_a': string, 'column_a': string, 'table_b': string, 'column_b': string} (all required).\n"
                    "- sample_rows: {'table_name': string (required), 'limit': integer (optional, default 10, max 100), 'filters': string (optional WHERE clause)}.\n"
                    "- run_query: {'sql': string} (required SELECT statement).\n"
                    "- search_workspace: {'query': string} (required table name or concept keyword).\n"
                    "- save_data_profile: {'target_type': string (defaults to 'table', can be 'table', 'schema', or 'catalog'), 'catalog_name': string (optional), 'schema_name': string (optional), 'table_name': string (required if target_type is table), 'row_count': integer, 'columns': array of objects, 'candidate_relationships': array of objects, 'detected_layer': string, 'prior_art_references': array of objects, 'unresolved_ambiguities': array of strings, 'domain_inference': object, 'timeseries_profile': object}."
                ),
                "additionalProperties": True,
            },
            "db_connection_id": {
                "type": "integer",
                "description": "Optional DB Connection ID. Defaults to the agent's first connection.",
            },
        },
        "required": ["operation", "payload"],
        "additionalProperties": False,
    }

    def __init__(self, session_id: int | None = None):
        self.session_id = session_id

    def _resolve_profile_connection_id(
        self,
        agent: Agent,
        db: Session,
        db_connection_id: int | None,
        target_type: str = "table",
        catalog_name: str | None = None,
        schema_name: str | None = None,
        table_name: str | None = None,
    ) -> int:
        if db_connection_id is not None:
            return db_connection_id

        agent_db_conn = (
            db.query(AgentDBConnection)
            .filter(AgentDBConnection.agent_id == agent.id)
            .first()
        )
        if agent_db_conn is not None:
            return agent_db_conn.db_connection_id

        query = db.query(DataSourceProfile).filter(DataSourceProfile.target_type == target_type)
        if catalog_name:
            query = query.filter(DataSourceProfile.catalog_name == catalog_name)
        if schema_name:
            query = query.filter(DataSourceProfile.schema_name == schema_name)
        if table_name:
            query = query.filter(DataSourceProfile.table_name == table_name)
            
        profile = query.order_by(DataSourceProfile.last_profiled_at.desc(), DataSourceProfile.id.desc()).first()
        if profile is not None:
            return profile.connection_id

        raise ValueError(
            "Agent has no database connections configured and no matching saved data profile was found"
        )

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        operation = args["operation"]
        payload = args["payload"]
        db_connection_id = args.get("db_connection_id")

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="payload must be an object")

        if operation == "get_data_profile":
            try:
                result = self._get_data_profile(payload, agent, db, db_connection_id)
                return ToolResult(ok=True, result=result)
            except Exception as e:
                return ToolResult(ok=False, error=str(e))

        try:
            adc, engine = _get_adc_and_engine(agent, db, db_connection_id)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

        try:
            if operation == "list_tables":
                result = self._list_tables(payload, adc, engine, db)
            elif operation == "get_table_schema":
                result = self._get_table_schema(payload, adc, engine, db)
            elif operation == "list_table_relationships":
                result = self._list_table_relationships(payload, adc, engine, db)
            elif operation == "get_data_profile":
                result = self._get_data_profile(payload, adc, engine, db)
            elif operation == "get_column_stats":
                result = self._get_column_stats(payload, adc, engine, db)
            elif operation == "get_row_count":
                result = self._get_row_count(payload, adc, engine, db)
            elif operation == "check_value_overlap":
                result = self._check_value_overlap(payload, adc, engine, db)
            elif operation == "sample_rows":
                result = self._sample_rows(payload, adc, engine, db)
            elif operation == "run_query":
                result = self._run_query(payload, adc, engine, db)
            elif operation == "search_workspace":
                result = self._search_workspace(payload, adc, engine, db)
            elif operation == "save_data_profile":
                result = self._save_data_profile(payload, adc, engine, db)
            else:
                return ToolResult(ok=False, error=f"Unknown operation: {operation}")

            return ToolResult(ok=True, result=result)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))

    def _list_tables(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        return adc.allowed_tables or []

    def _get_table_schema(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_name = payload.get("table_name")
        if not table_name:
            raise ValueError("table_name is required in payload")
        _check_table_allowed(adc, table_name)

        inspector = inspect(engine)
        schema_name = None
        actual_table = table_name
        if "." in table_name:
            schema_name, actual_table = table_name.split(".", 1)

        columns_info = inspector.get_columns(actual_table, schema=schema_name)
        columns = []
        for col in columns_info:
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"]
            })

        pk_constraint = inspector.get_pk_constraint(actual_table, schema=schema_name)
        pk_info = pk_constraint.get("constrained_columns") or []
        fk_info = inspector.get_foreign_keys(actual_table, schema=schema_name)
        foreign_keys = []
        for fk in fk_info:
            foreign_keys.append({
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"]
            })

        return {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": pk_info,
            "foreign_keys": foreign_keys
        }

    def _list_table_relationships(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_name = payload.get("table_name")
        if not table_name:
            raise ValueError("table_name is required in payload")
        _check_table_allowed(adc, table_name)

        inspector = inspect(engine)
        schema_name = None
        actual_table = table_name
        if "." in table_name:
            schema_name, actual_table = table_name.split(".", 1)

        fk_info = inspector.get_foreign_keys(actual_table, schema=schema_name)
        relationships = []
        for fk in fk_info:
            relationships.append({
                "from_col": fk["constrained_columns"][0] if fk["constrained_columns"] else None,
                "to_table": fk["referred_table"],
                "to_col": fk["referred_columns"][0] if fk["referred_columns"] else None,
                "type": "declared_fk"
            })

        # Fetch candidate relationships from DataSourceProfile
        profile = db.query(DataSourceProfile).filter(
            DataSourceProfile.connection_id == adc.db_connection_id,
            DataSourceProfile.table_name == table_name
        ).first()

        if profile and profile.candidate_relationships:
            for rel in profile.candidate_relationships:
                relationships.append({
                    "from_col": rel.get("from_col"),
                    "to_table": rel.get("to_table"),
                    "to_col": rel.get("to_col"),
                    "overlap_ratio": rel.get("overlap_ratio"),
                    "type": "candidate_profiled"
                })

        return {
            "table_name": table_name,
            "relationships": relationships
        }

    def _get_data_profile(
        self,
        payload: dict[str, Any],
        agent: Agent,
        db: Session,
        db_connection_id: int | None,
    ) -> Any:
        target_type = payload.get("target_type", "table")
        catalog_name = payload.get("catalog_name")
        schema_name = payload.get("schema_name")
        table_name = payload.get("table_name")

        if target_type == "table" and not table_name:
            raise ValueError("table_name is required in payload when target_type is table")

        connection_id = self._resolve_profile_connection_id(
            agent, db, db_connection_id, target_type, catalog_name, schema_name, table_name
        )

        query = db.query(DataSourceProfile).filter(
            DataSourceProfile.connection_id == connection_id,
            DataSourceProfile.target_type == target_type,
        )
        if catalog_name:
            query = query.filter(DataSourceProfile.catalog_name == catalog_name)
        if schema_name:
            query = query.filter(DataSourceProfile.schema_name == schema_name)
        if table_name:
            query = query.filter(DataSourceProfile.table_name == table_name)
            
        profile = query.first()

        if not profile:
            return {"target_type": target_type, "table_name": table_name, "message": "No profile found for this target."}

        return {
            "target_type": profile.target_type,
            "catalog_name": profile.catalog_name,
            "schema_name": profile.schema_name,
            "table_name": profile.table_name,
            "row_count": profile.row_count,
            "detected_layer": profile.detected_layer,
            "unresolved_ambiguities": profile.unresolved_ambiguities,
            "prior_art_references": profile.prior_art_references,
            "domain_inference": profile.domain_inference,
            "timeseries_profile": profile.timeseries_profile,
            "last_profiled_at": str(profile.last_profiled_at) if profile.last_profiled_at else None,
        }

    def _get_column_stats(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_name = payload.get("table_name")
        column_name = payload.get("column_name")
        if not table_name or not column_name:
            raise ValueError("table_name and column_name are required in payload")
        if column_name == "*":
            raise ValueError("column_name must be a specific column, not '*'. To get table row count, use the get_row_count operation.")
        _check_table_allowed(adc, table_name)

        def quote(identifier):
            return f'"{identifier}"'
        
        q_table = ".".join(quote(part) for part in table_name.split("."))
        q_col = quote(column_name)

        stats = {}
        with engine.connect() as conn:
            # Row Count
            try:
                res = conn.execute(text(f"SELECT COUNT(*) FROM {q_table}"))
                stats["row_count"] = res.scalar()
            except Exception as e:
                stats["row_count"] = None
                stats["row_count_error"] = str(e)

            # Null Count
            try:
                res = conn.execute(text(f"SELECT COUNT(*) FROM {q_table} WHERE {q_col} IS NULL"))
                null_count = res.scalar()
                stats["null_count"] = null_count
                if stats.get("row_count"):
                    stats["null_rate"] = null_count / stats["row_count"]
                else:
                    stats["null_rate"] = 0.0
            except Exception as e:
                stats["null_count"] = None
                stats["null_rate"] = None
                stats["null_error"] = str(e)

            # Distinct Count
            try:
                res = conn.execute(text(f"SELECT COUNT(DISTINCT {q_col}) FROM {q_table}"))
                stats["distinct_count"] = res.scalar()
            except Exception as e:
                stats["distinct_count"] = None
                stats["distinct_error"] = str(e)

            # Min/Max
            try:
                res = conn.execute(text(f"SELECT MIN({q_col}), MAX({q_col}) FROM {q_table}"))
                row = res.fetchone()
                if row:
                    min_val, max_val = row[0], row[1]
                    if isinstance(min_val, (datetime, date, bytes)):
                        min_val = str(min_val)
                    if isinstance(max_val, (datetime, date, bytes)):
                        max_val = str(max_val)
                    stats["min"] = min_val
                    stats["max"] = max_val
                else:
                    stats["min"] = None
                    stats["max"] = None
            except Exception as e:
                stats["min"] = None
                stats["max"] = None
                stats["min_max_error"] = str(e)

            # Top values
            try:
                res = conn.execute(text(
                    f"SELECT {q_col}, COUNT(*) as frequency "
                    f"FROM {q_table} "
                    f"GROUP BY {q_col} "
                    f"ORDER BY frequency DESC LIMIT 5"
                ))
                top_values = []
                for val, freq in res.fetchall():
                    if isinstance(val, (datetime, date, bytes)):
                        val = str(val)
                    top_values.append({"value": val, "frequency": freq})
                stats["top_values"] = top_values
            except Exception as e:
                stats["top_values"] = []
                stats["top_values_error"] = str(e)

        return stats

    def _get_row_count(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_name = payload.get("table_name")
        filters = payload.get("filters")
        if not table_name:
            raise ValueError("table_name is required in payload")
        _check_table_allowed(adc, table_name)

        def quote(identifier):
            return f'"{identifier}"'
        
        q_table = ".".join(quote(part) for part in table_name.split("."))
        sql = f"SELECT COUNT(*) FROM {q_table}"
        
        if filters:
            filters_upper = filters.upper()
            if ";" in filters or "--" in filters or "/*" in filters:
                raise ValueError("Invalid characters in filters parameter.")
            forbidden = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"}
            tokens = set(re.findall(r'\b[A-Z]+\b', filters_upper))
            forbidden_found = tokens.intersection(forbidden)
            if forbidden_found:
                raise ValueError(f"Forbidden terms in filters: {forbidden_found}")
            sql += f" WHERE {filters}"

        with engine.connect() as conn:
            res = conn.execute(text(sql))
            count = res.scalar()

        return {"table_name": table_name, "row_count": count}

    def _check_value_overlap(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_a = payload.get("table_a")
        column_a = payload.get("column_a")
        table_b = payload.get("table_b")
        column_b = payload.get("column_b")

        if not table_a or not column_a or not table_b or not column_b:
            raise ValueError("table_a, column_a, table_b, and column_b are required in payload")

        _check_table_allowed(adc, table_a)
        _check_table_allowed(adc, table_b)

        def quote(identifier):
            return f'"{identifier}"'
        
        q_table_a = ".".join(quote(part) for part in table_a.split("."))
        q_table_b = ".".join(quote(part) for part in table_b.split("."))
        q_col_a = quote(column_a)
        q_col_b = quote(column_b)

        with engine.connect() as conn:
            res_a = conn.execute(text(f"SELECT COUNT(DISTINCT {q_col_a}) FROM {q_table_a}"))
            distinct_a = res_a.scalar()

            if not distinct_a or distinct_a == 0:
                return {
                    "distinct_a": 0,
                    "overlap_count": 0,
                    "overlap_ratio": 0.0
                }

            res_overlap = conn.execute(text(
                f"SELECT COUNT(DISTINCT a.{q_col_a}) "
                f"FROM {q_table_a} a "
                f"WHERE EXISTS ("
                f"  SELECT 1 FROM {q_table_b} b WHERE b.{q_col_b} = a.{q_col_a}"
                f")"
            ))
            overlap_count = res_overlap.scalar()
            ratio = overlap_count / distinct_a

        return {
            "distinct_a": distinct_a,
            "overlap_count": overlap_count,
            "overlap_ratio": ratio
        }

    def _sample_rows(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        table_name = payload.get("table_name")
        limit = payload.get("limit")
        filters = payload.get("filters")
        if not table_name:
            raise ValueError("table_name is required in payload")
        _check_table_allowed(adc, table_name)

        limit = min(limit or 10, 100)
        if limit < 1:
            limit = 1

        def quote(identifier):
            return f'"{identifier}"'
        
        q_table = ".".join(quote(part) for part in table_name.split("."))
        sql = f"SELECT * FROM {q_table}"

        if filters:
            filters_upper = filters.upper()
            if ";" in filters or "--" in filters or "/*" in filters:
                raise ValueError("Invalid characters in filters parameter.")
            forbidden = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"}
            tokens = set(re.findall(r'\b[A-Z]+\b', filters_upper))
            forbidden_found = tokens.intersection(forbidden)
            if forbidden_found:
                raise ValueError(f"Forbidden terms in filters: {forbidden_found}")
            sql += f" WHERE {filters}"

        sql += f" LIMIT {limit}"

        with engine.connect() as conn:
            res = conn.execute(text(sql))
            rows = []
            for r in res.fetchall():
                row_dict = {}
                for key, val in r._mapping.items():
                    if val is None:
                        row_dict[key] = None
                    elif isinstance(val, (datetime, date, uuid.UUID)):
                        row_dict[key] = str(val)
                    elif isinstance(val, bytes):
                        row_dict[key] = val.decode("utf-8", errors="replace")
                    elif type(val).__name__ == "Decimal":
                        row_dict[key] = float(val)
                    elif not isinstance(val, (int, float, str, bool)):
                        row_dict[key] = str(val)
                    else:
                        row_dict[key] = val
                rows.append(row_dict)

        return {
            "table_name": table_name,
            "rows": rows,
            "count": len(rows)
        }

    def _run_query(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        sql = payload.get("sql")
        if not sql:
            raise ValueError("sql is required in payload")

        sql_clean = sql.strip().upper()
        # 1. Enforce SELECT or WITH
        allowed_starts = ("SELECT", "WITH", "EXPLAIN")
        if not any(sql_clean.startswith(start) for start in allowed_starts):
            raise ValueError("Only SELECT queries are allowed.")

        # 2. Prevent DML/DDL keywords
        forbidden = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "INTO", "MERGE"}
        tokens = set(re.findall(r'\b[A-Z]+\b', sql_clean))
        forbidden_found = tokens.intersection(forbidden)
        if forbidden_found:
            raise ValueError(f"DML/DDL operations are forbidden: found {forbidden_found}")

        # 3. Table Scoping Validation
        # Extract tables following FROM or JOIN
        tokens_list = re.split(r'\s+', sql)
        extracted_tables = set()
        for i, token in enumerate(tokens_list):
            upper_tok = token.upper()
            if upper_tok in ("FROM", "JOIN") and i + 1 < len(tokens_list):
                next_tok = tokens_list[i + 1].strip("(),;\"'`")
                if next_tok.upper() not in ("SELECT", "WITH", ""):
                    extracted_tables.add(next_tok)

        for table in extracted_tables:
            _check_table_allowed(adc, table)

        # 4. Connection-level Read-Only setting / Query Timeout / Result Size Cap (1000 rows)
        with engine.connect() as conn:
            # Set query timeouts if dialect is supported
            if engine.dialect.name == "postgresql":
                conn.execute(text("SET statement_timeout = 15000"))  # 15 seconds
            elif engine.dialect.name == "mysql":
                conn.execute(text("SET max_execution_time = 15000"))  # 15 seconds

            # Execute with statement timeout in SQLAlchemy options as well
            conn = conn.execution_options(timeout=15)
            res = conn.execute(text(sql))
            
            rows_raw = res.fetchmany(1001)
            exceeded_cap = len(rows_raw) > 1000
            
            rows = []
            for r in rows_raw[:1000]:
                row_dict = {}
                for key, val in r._mapping.items():
                    if val is None:
                        row_dict[key] = None
                    elif isinstance(val, (datetime, date, uuid.UUID)):
                        row_dict[key] = str(val)
                    elif isinstance(val, bytes):
                        row_dict[key] = val.decode("utf-8", errors="replace")
                    elif type(val).__name__ == "Decimal":
                        row_dict[key] = float(val)
                    elif not isinstance(val, (int, float, str, bool)):
                        row_dict[key] = str(val)
                    else:
                        row_dict[key] = val
                rows.append(row_dict)

        return {
            "rows": rows,
            "count": len(rows),
            "exceeded_cap": exceeded_cap,
            "warning": "Result truncated to 1000 rows." if exceeded_cap else None
        }

    def _search_workspace(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        query = payload.get("query")
        if not query:
            raise ValueError("query is required in payload")

        results = []

        # 1. Search canonical Jobs (including notebook-backed jobs).
        jobs = db.query(Job).filter(
            Job.name.ilike(f"%{query}%") |
            Job.description.ilike(f"%{query}%")
        ).all()
        for job in jobs:
            results.append({
                "source_type": "job",
                "source_name": job.name,
                "excerpt": job.description or f"Job ID: {job.job_id}",
                "relevance_note": "Matches job name or description."
            })

        # 2. Search Dashboards
        dashboards = db.query(Dashboard).filter(
            Dashboard.name.ilike(f"%{query}%")
        ).all()
        for dbd in dashboards:
            results.append({
                "source_type": "dashboard",
                "source_name": dbd.name,
                "excerpt": f"Dashboard ID: {dbd.id}",
                "relevance_note": "Matches dashboard name."
            })

        # 3. Search Skills
        skills = db.query(Skill).filter(
            Skill.name.ilike(f"%{query}%") |
            Skill.description.ilike(f"%{query}%") |
            Skill.body.ilike(f"%{query}%")
        ).all()
        for sk in skills:
            results.append({
                "source_type": "skill",
                "source_name": sk.name,
                "excerpt": sk.description[:200],
                "relevance_note": "Matches skill name, description, or code body."
            })

        return results

    def _save_data_profile(self, payload: dict[str, Any], adc: AgentDBConnection, engine: Any, db: Session) -> Any:
        target_type = payload.get("target_type", "table")
        catalog_name = payload.get("catalog_name")
        schema_name = payload.get("schema_name")
        table_name = payload.get("table_name")

        if target_type == "table":
            if not table_name:
                raise ValueError("table_name is required in payload when target_type is table")
            _check_table_allowed(adc, table_name)

        connection_id = adc.db_connection_id

        query = db.query(DataSourceProfile).filter(
            DataSourceProfile.connection_id == connection_id,
            DataSourceProfile.target_type == target_type,
        )
        if catalog_name:
            query = query.filter(DataSourceProfile.catalog_name == catalog_name)
        else:
            query = query.filter(DataSourceProfile.catalog_name.is_(None))
            
        if schema_name:
            query = query.filter(DataSourceProfile.schema_name == schema_name)
        else:
            query = query.filter(DataSourceProfile.schema_name.is_(None))
            
        if table_name:
            query = query.filter(DataSourceProfile.table_name == table_name)
        else:
            query = query.filter(DataSourceProfile.table_name.is_(None))
            
        profile = query.first()

        if not profile:
            profile = DataSourceProfile(
                connection_id=connection_id,
                target_type=target_type,
                catalog_name=catalog_name,
                schema_name=schema_name,
                table_name=table_name,
            )
            db.add(profile)

        if "row_count" in payload:
            profile.row_count = payload.get("row_count")
        if "columns" in payload:
            profile.columns = payload.get("columns", [])
        if "candidate_relationships" in payload:
            profile.candidate_relationships = payload.get("candidate_relationships", [])
        if "detected_layer" in payload:
            profile.detected_layer = payload.get("detected_layer")
        if "prior_art_references" in payload:
            profile.prior_art_references = payload.get("prior_art_references", [])
        if "unresolved_ambiguities" in payload:
            profile.unresolved_ambiguities = payload.get("unresolved_ambiguities", [])
        if "timeseries_profile" in payload:
            profile.timeseries_profile = payload.get("timeseries_profile", {})
        if "domain_inference" in payload:
            profile.domain_inference = payload.get("domain_inference", {})

        profile.last_profiled_at = datetime.now(timezone.utc)
        profile.profiled_by_agent_run_id = self.session_id

        db.commit()
        return {"success": True}

