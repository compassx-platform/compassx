from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session, selectinload

from app.models.agents import Agent, AgentDBConnection, Skill, DataSourceProfile
from app.jobs.models.job import Job
from app.dashboards.models.dashboard import Dashboard
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.services.db_introspector import build_engine

logger = logging.getLogger(__name__)


def _get_adc_and_engine(agent: Agent, db: Session, db_connection_id: int | None = None):
    agent_db_conns = (
        db.query(AgentDBConnection)
        .filter(AgentDBConnection.agent_id == agent.id)
        .all()
    )
    if not agent_db_conns:
        raise ValueError("Agent has no database connections configured")

    if db_connection_id:
        adc = next((c for c in agent_db_conns if c.db_connection_id == db_connection_id), None)
        if not adc:
            raise ValueError(f"DB connection {db_connection_id} is not assigned to this agent")
    else:
        adc = agent_db_conns[0]

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
    return adc, engine


def _check_table_allowed(adc: AgentDBConnection, table_name: str) -> None:
    if not adc.allowed_tables:
        raise ValueError(
            f"Access Denied: Table '{table_name}' is not in the allowed scope (scope is empty)."
        )
    
    # Normalize comparison: lowercase, and check both with and without schema prefix.
    allowed_set = {t.lower() for t in adc.allowed_tables}
    table_lower = table_name.lower()
    
    # E.g. if table_name is 'public.users', check both 'public.users' and 'users'
    bare_name = table_lower.split('.')[-1] if '.' in table_lower else table_lower
    
    if table_lower in allowed_set or bare_name in allowed_set:
        return
        
    raise ValueError(
        f"Access Denied: Table '{table_name}' is not in the allowed scope. "
        f"Allowed tables: {adc.allowed_tables}"
    )


class ListTablesTool(BaseTool):
    key = "list_tables"
    name = "List Tables"
    description = "List all allowed tables and views in the database connection."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "db_connection_id": {
                "type": "integer",
                "description": "Optional DB Connection ID. Defaults to the agent's first connection.",
            }
        }
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
            return ToolResult(ok=True, result=adc.allowed_tables or [])
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class GetTableSchemaTool(BaseTool):
    key = "get_table_schema"
    name = "Get Table Schema"
    description = "Get column details, data types, nullability, primary keys, and foreign keys for a specific table."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "The name of the table to introspect."},
            "db_connection_id": {"type": "integer", "description": "Optional DB Connection ID."}
        },
        "required": ["table_name"]
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_name = args["table_name"]
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
            _check_table_allowed(adc, table_name)

            inspector = inspect(engine)
            schema_name = None
            actual_table_name = table_name
            if "." in table_name:
                parts = table_name.split(".")
                schema_name = parts[0]
                actual_table_name = parts[1]
            
            # Get columns
            columns_info = inspector.get_columns(actual_table_name, schema=schema_name)
            columns = []
            for col in columns_info:
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"]
                })
            
            # Primary keys
            pk_constraint = inspector.get_pk_constraint(actual_table_name, schema=schema_name)
            pk_info = pk_constraint.get("constrained_columns") or []
            
            # Foreign keys
            fk_info = inspector.get_foreign_keys(actual_table_name, schema=schema_name)
            foreign_keys = []
            for fk in fk_info:
                foreign_keys.append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })

            result = {
                "table_name": table_name,
                "columns": columns,
                "primary_keys": pk_info,
                "foreign_keys": foreign_keys
            }
            return ToolResult(ok=True, result=result)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class GetColumnStatsTool(BaseTool):
    key = "get_column_stats"
    name = "Get Column Stats"
    description = "Get row count, null rate, distinct count, min/max, and top frequent values for a column."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "column_name": {"type": "string"},
            "db_connection_id": {"type": "integer"}
        },
        "required": ["table_name", "column_name"]
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_name = args["table_name"]
            column_name = args["column_name"]
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
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
                        if isinstance(min_val, (datetime, bytes)):
                            min_val = str(min_val)
                        if isinstance(max_val, (datetime, bytes)):
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

                # Top values (most frequent)
                try:
                    res = conn.execute(text(
                        f"SELECT {q_col}, COUNT(*) as frequency "
                        f"FROM {q_table} "
                        f"GROUP BY {q_col} "
                        f"ORDER BY frequency DESC LIMIT 5"
                    ))
                    top_values = []
                    for val, freq in res.fetchall():
                        if isinstance(val, (datetime, bytes)):
                            val = str(val)
                        top_values.append({"value": val, "frequency": freq})
                    stats["top_values"] = top_values
                except Exception as e:
                    stats["top_values"] = []
                    stats["top_values_error"] = str(e)

            return ToolResult(ok=True, result=stats)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class CheckValueOverlapTool(BaseTool):
    key = "check_value_overlap"
    name = "Check Value Overlap"
    description = "Check value overlap (cardinality ratio) between two columns in different tables."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_a": {"type": "string"},
            "column_a": {"type": "string"},
            "table_b": {"type": "string"},
            "column_b": {"type": "string"},
            "db_connection_id": {"type": "integer"}
        },
        "required": ["table_a", "column_a", "table_b", "column_b"]
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_a = args["table_a"]
            column_a = args["column_a"]
            table_b = args["table_b"]
            column_b = args["column_b"]
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
            
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
                    return ToolResult(ok=True, result={
                        "distinct_a": 0,
                        "overlap_count": 0,
                        "overlap_ratio": 0.0
                    })

                res_overlap = conn.execute(text(
                    f"SELECT COUNT(DISTINCT a.{q_col_a}) "
                    f"FROM {q_table_a} a "
                    f"WHERE EXISTS ("
                    f"  SELECT 1 FROM {q_table_b} b WHERE b.{q_col_b} = a.{q_col_a}"
                    f")"
                ))
                overlap_count = res_overlap.scalar()

                ratio = overlap_count / distinct_a

            return ToolResult(ok=True, result={
                "distinct_a": distinct_a,
                "overlap_count": overlap_count,
                "overlap_ratio": ratio
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class SearchWorkspaceTool(BaseTool):
    key = "search_workspace"
    name = "Search Workspace"
    description = "Search notebooks, dashboards, and skills for references to database tables or concepts."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The table name or concept to search for."}
        },
        "required": ["query"]
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            query = args["query"]
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

            return ToolResult(ok=True, result=results)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class GetDataProfileTool(BaseTool):
    key = "get_data_profile"
    name = "Get Data Profile"
    description = "Retrieve compiled Layer 1 data profiling findings. If table_name is omitted, returns all available profiled tables without requiring an attached database connection."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": ["string", "null"]},
            "db_connection_id": {"type": ["integer", "null"]}
        }
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_name = args.get("table_name")
            connection_id = args.get("db_connection_id")

            query = db.query(DataSourceProfile)
            if table_name:
                query = query.filter(DataSourceProfile.table_name == table_name)
            if connection_id is not None:
                query = query.filter(DataSourceProfile.connection_id == connection_id)

            query = query.order_by(DataSourceProfile.last_profiled_at.desc(), DataSourceProfile.id.desc())

            if table_name:
                profile = query.first()
                if not profile:
                    return ToolResult(ok=True, result={"table_name": table_name, "message": "No profile found for this table."})

                return ToolResult(ok=True, result={
                    "table_name": profile.table_name,
                    "db_connection_id": profile.connection_id,
                    "row_count": profile.row_count,
                    "last_profiled_at": str(profile.last_profiled_at) if profile.last_profiled_at else None,
                    "profiled_by_agent_run_id": profile.profiled_by_agent_run_id,
                    "columns": profile.columns or [],
                    "candidate_relationships": profile.candidate_relationships or [],
                    "detected_layer": profile.detected_layer,
                    "prior_art_references": profile.prior_art_references or [],
                    "unresolved_ambiguities": profile.unresolved_ambiguities or [],
                })

            profiles = query.all()
            return ToolResult(ok=True, result={
                "profiles": [
                    {
                        "table_name": profile.table_name,
                        "db_connection_id": profile.connection_id,
                        "row_count": profile.row_count,
                        "last_profiled_at": str(profile.last_profiled_at) if profile.last_profiled_at else None,
                        "profiled_by_agent_run_id": profile.profiled_by_agent_run_id,
                        "columns": profile.columns or [],
                        "candidate_relationships": profile.candidate_relationships or [],
                        "detected_layer": profile.detected_layer,
                        "prior_art_references": profile.prior_art_references or [],
                        "unresolved_ambiguities": profile.unresolved_ambiguities or [],
                    }
                    for profile in profiles
                ]
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class SaveDataProfileTool(BaseTool):
    key = "save_data_profile"
    name = "Save Data Profile"
    description = "Save the compiled data profile for a table."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "db_connection_id": {"type": "integer"},
            "row_count": {"type": "integer"},
            "columns": {"type": "array", "items": {"type": "object"}},
            "candidate_relationships": {"type": "array", "items": {"type": "object"}},
            "detected_layer": {"type": "string"},
            "prior_art_references": {"type": "array", "items": {"type": "object"}},
            "unresolved_ambiguities": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["table_name"]
    }

    def __init__(self, session_id: int | None = None):
        self.session_id = session_id

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_name = args["table_name"]
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
            _check_table_allowed(adc, table_name)

            connection_id = adc.db_connection_id

            profile = db.query(DataSourceProfile).filter(
                DataSourceProfile.connection_id == connection_id,
                DataSourceProfile.table_name == table_name
            ).first()

            if not profile:
                profile = DataSourceProfile(
                    connection_id=connection_id,
                    table_name=table_name,
                )
                db.add(profile)

            profile.row_count = args.get("row_count")
            profile.columns = args.get("columns", [])
            profile.candidate_relationships = args.get("candidate_relationships", [])
            profile.detected_layer = args.get("detected_layer")
            profile.prior_art_references = args.get("prior_art_references", [])
            profile.unresolved_ambiguities = args.get("unresolved_ambiguities", [])
            profile.last_profiled_at = datetime.now(timezone.utc)
            profile.profiled_by_agent_run_id = self.session_id

            db.commit()
            return ToolResult(ok=True, result={"success": True})
        except Exception as e:
            return ToolResult(ok=False, error=str(e))


class GetExistingProfileTool(BaseTool):
    key = "get_existing_profile"
    name = "Get Existing Profile"
    description = "Retrieve the saved profile for a table."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "db_connection_id": {"type": "integer"}
        },
        "required": ["table_name"]
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        try:
            table_name = args["table_name"]
            adc, engine = _get_adc_and_engine(agent, db, args.get("db_connection_id"))
            _check_table_allowed(adc, table_name)

            connection_id = adc.db_connection_id

            profile = db.query(DataSourceProfile).filter(
                DataSourceProfile.connection_id == connection_id,
                DataSourceProfile.table_name == table_name
            ).first()

            if not profile:
                return ToolResult(ok=True, result=None)

            return ToolResult(ok=True, result={
                "table_name": profile.table_name,
                "row_count": profile.row_count,
                "last_profiled_at": str(profile.last_profiled_at),
                "profiled_by_agent_run_id": profile.profiled_by_agent_run_id,
                "columns": profile.columns,
                "candidate_relationships": profile.candidate_relationships,
                "detected_layer": profile.detected_layer,
                "prior_art_references": profile.prior_art_references,
                "unresolved_ambiguities": profile.unresolved_ambiguities
            })
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
