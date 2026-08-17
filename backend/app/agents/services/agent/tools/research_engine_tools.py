"""Research Engine context assembly tools."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.memory.research_store import ResearchMemoryStore
from app.models.agents import Agent, DataSourceProfile


class HarvestResearchMemoryTool(BaseTool):
    key = "harvest_research_memory"
    name = "Harvest Research Memory"
    description = "Scan recent Tier 1 agent memory for qualifying Tier 2 Research Memory facts before a Research Engine run."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "default": 30},
            "limit": {"type": "integer", "default": 200},
        },
    }

    def __init__(self, workspace_id: str | None = None) -> None:
        self._workspace_id = workspace_id

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        store = ResearchMemoryStore(lambda: db, close_sessions=False)
        stats = store.harvest_recent_agent_memory(
            workspace_id=self._workspace_id or "default",
            days=args.get("days") or 30,
            limit=args.get("limit") or 200,
        )
        return ToolResult(ok=True, result=stats, duration_ms=int((time.monotonic() - start) * 1000))


class FetchLayer1ProfilesTool(BaseTool):
    key = "fetch_layer1_profiles"
    name = "Fetch Layer 1 Profiles"
    description = "Fetch confirmed Layer 1 data source profiles for the current workspace context package."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "connection_id": {"type": ["integer", "null"], "description": "Optional DB connection id filter."},
        },
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        query = db.query(DataSourceProfile)
        if args.get("connection_id"):
            query = query.filter(DataSourceProfile.connection_id == args["connection_id"])
        profiles = query.order_by(DataSourceProfile.connection_id, DataSourceProfile.table_name).all()
        result = [
            {
                "id": p.id,
                "connection_id": p.connection_id,
                "target_type": p.target_type,
                "catalog_name": p.catalog_name,
                "schema_name": p.schema_name,
                "table_name": p.table_name,
                "row_count": p.row_count,
                "last_profiled_at": p.last_profiled_at.isoformat() if p.last_profiled_at else None,
                "profiled_by_agent_run_id": p.profiled_by_agent_run_id,
                "columns": p.columns or [],
                "candidate_relationships": p.candidate_relationships or [],
                "detected_layer": p.detected_layer,
                "prior_art_references": p.prior_art_references or [],
                "unresolved_ambiguities": p.unresolved_ambiguities or [],
                "domain_inference": p.domain_inference,
                "timeseries_profile": p.timeseries_profile,
            }
            for p in profiles
        ]
        return ToolResult(ok=True, result={"profiles": result}, duration_ms=int((time.monotonic() - start) * 1000))


class ScanPlatformMaturityTool(BaseTool):
    key = "scan_platform_maturity"
    name = "Scan Platform Maturity"
    description = "Live scan of existing KPIs, dashboards, alerts, ML/notebook work, and skills for Research Engine maturity assessment."
    is_async = False
    input_schema = {"type": "object", "properties": {}}

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        dashboards = db.execute(text("""
            SELECT id, name, updated_at
            FROM dashboards
            ORDER BY updated_at DESC
            LIMIT 100
        """)).fetchall()
        skills = db.execute(text("""
            SELECT id, name, description, version, updated_at
            FROM skills
            WHERE is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 100
        """)).fetchall()
        notebooks = db.execute(text("""
            SELECT j.job_id, j.name, task->>'target_ref' AS notebook_path, j.updated_at
            FROM jobs.jobs AS j
            JOIN jobs.job_versions AS v
              ON v.job_id = j.job_id AND v.version_number = j.current_version
            CROSS JOIN LATERAL jsonb_array_elements(v.task_definitions) AS task
            WHERE task->>'task_type' = 'notebook'
            ORDER BY j.updated_at DESC
            LIMIT 100
        """)).fetchall()
        profiles_count = db.execute(text("SELECT COUNT(*) FROM data_source_profiles")).scalar() or 0

        maturity = {
            "gold_layer_kpis": [],
            "dashboards": [
                {"id": str(r[0]), "name": r[1], "updated_at": r[2].isoformat() if r[2] else None}
                for r in dashboards
            ],
            "alerts": [],
            "ml_models_or_notebooks": [
                {"id": r[0], "name": r[1], "path": r[2], "updated_at": r[3].isoformat() if r[3] else None}
                for r in notebooks
            ],
            "skills": [
                {"id": r[0], "name": r[1], "description": r[2], "version": r[3], "updated_at": r[4].isoformat() if r[4] else None}
                for r in skills
            ],
            "profiled_table_count": profiles_count,
        }
        return ToolResult(ok=True, result=maturity, duration_ms=int((time.monotonic() - start) * 1000))


class FetchResearchProposalHistoryTool(BaseTool):
    key = "fetch_research_proposal_history"
    name = "Fetch Research Proposal History"
    description = "Fetch prior Research Engine proposals and conversation history for the workspace."
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "status": {"type": ["string", "null"]},
            "limit": {"type": "integer", "default": 50},
        },
    }

    def __init__(self, workspace_id: str | None = None) -> None:
        self._workspace_id = workspace_id

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        start = time.monotonic()
        conditions = ["workspace_id = :workspace_id"]
        params: dict[str, Any] = {"workspace_id": self._workspace_id or "default", "limit": args.get("limit") or 50}
        if args.get("status"):
            conditions.append("status = :status")
            params["status"] = args["status"]
        rows = db.execute(text(f"""
            SELECT id, engine_run_id, status, problem_statement, why_it_matters,
                   maturity_level, priority_rank, priority_rationale, rejection_reason,
                   created_at, updated_at
            FROM research_proposals
            WHERE {" AND ".join(conditions)}
            ORDER BY created_at DESC
            LIMIT :limit
        """), params).fetchall()
        proposals = [
            {
                "id": str(r[0]),
                "engine_run_id": str(r[1]) if r[1] else None,
                "status": r[2],
                "problem_statement": r[3],
                "why_it_matters": r[4],
                "maturity_level": r[5],
                "priority_rank": r[6],
                "priority_rationale": r[7],
                "rejection_reason": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
                "updated_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]
        return ToolResult(ok=True, result={"proposals": proposals}, duration_ms=int((time.monotonic() - start) * 1000))

