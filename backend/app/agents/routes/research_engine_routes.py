"""Research Engine routes for memory, runs, proposals, and proposal conversations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db
from app.dependencies import get_current_user
from app.models.agents import ChatSession

router = APIRouter(prefix="/api/v1/research-engine", tags=["Research Engine"])


class ResearchEngineRunCreate(BaseModel):
    trigger_type: str = "on_demand"
    agent_id: int | None = None


class ResearchEngineTriggerRequest(BaseModel):
    agent_id: int
    title: str | None = None
    prompt: str | None = None


class ProposalCreate(BaseModel):
    engine_run_id: str | None = None
    problem_statement: str
    why_it_matters: str | None = None
    maturity_level: str
    priority_rank: int
    priority_rationale: str | None = None
    data_evidence: list[dict[str, Any]] = []
    proposed_deliverables: list[Any] = []
    implementation_sequence: list[Any] = []
    dependencies: list[Any] = []
    open_questions: list[Any] = []
    domain_gotchas: list[Any] = []


class ProposalStatusUpdate(BaseModel):
    status: str
    rejection_reason: str | None = None


class ProposalMessageCreate(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = {}


def _workspace_id(current_user: dict) -> str:
    return current_user.get("org_id") or "default"


def _user_id(current_user: dict) -> str:
    return current_user.get("id") or current_user.get("sub") or "default_user"


@router.post("/trigger", status_code=201)
def trigger_research_engine_run(
    body: ResearchEngineTriggerRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = _workspace_id(current_user)

    agent_row = db.execute(text("""
        SELECT id, name
        FROM ai.agents
        WHERE id = :agent_id
    """), {"agent_id": body.agent_id}).fetchone()
    if not agent_row:
        raise HTTPException(404, "Research engine agent not found")

    run_id = db.execute(text("""
        INSERT INTO ai.research_engine_runs (workspace_id, agent_id, trigger_type, status)
        VALUES (:workspace_id, :agent_id, 'manual', 'pending')
        RETURNING id
    """), {"workspace_id": workspace_id, "agent_id": body.agent_id}).scalar()

    session_title = body.title or f"Research Run {str(run_id)[:8]}"
    session = ChatSession(agent_id=body.agent_id, title=session_title)
    db.add(session)
    db.flush()
    session_id = session.id

    db.execute(text("""
        UPDATE ai.research_engine_runs
        SET status = 'session_created',
            context_package = jsonb_build_object('chat_session_id', :session_id)
        WHERE id = :run_id
    """), {"run_id": run_id, "session_id": session_id})
    db.commit()

    return {
        "run_id": str(run_id),
        "agent_id": body.agent_id,
        "session_id": session_id,
        "session_title": session_title,
        "initial_prompt": body.prompt or (
            "You are running a Research Engine cycle for this workspace. "
            "First assess current platform maturity and produce a focused set of proposals based on connected context. "
            "\n\n"
            "Output rules:\n"
            "- Distinguish confirmed facts from assumptions and open questions.\n"
            "- Default to 3-5 prioritized proposals, not an exhaustive backlog.\n"
            "- Surface any open questions that must be answered before implementation."
        ),
    }


@router.get("/runs")
def list_runs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT id, agent_id, trigger_type, status, context_package, changes_since_last_run,
               maturity_assessment, started_at, completed_at, error
        FROM ai.research_engine_runs
        WHERE workspace_id = :workspace_id
        ORDER BY started_at DESC
        LIMIT 100
    """), {"workspace_id": _workspace_id(current_user)}).fetchall()
    return [
        {
            "id": str(r[0]),
            "agent_id": r[1],
            "trigger_type": r[2],
            "status": r[3],
            "context_package": r[4] or {},
            "changes_since_last_run": r[5] or [],
            "maturity_assessment": r[6] or {},
            "started_at": r[7].isoformat() if r[7] else None,
            "completed_at": r[8].isoformat() if r[8] else None,
            "error": r[9],
        }
        for r in rows
    ]


@router.post("/runs", status_code=201)
def create_run_record(
    body: ResearchEngineRunCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = db.execute(text("""
        INSERT INTO ai.research_engine_runs (workspace_id, agent_id, trigger_type, status)
        VALUES (:workspace_id, :agent_id, :trigger_type, 'pending')
        RETURNING id
    """), {"workspace_id": _workspace_id(current_user), "agent_id": body.agent_id, "trigger_type": body.trigger_type}).scalar()
    db.commit()
    return {"id": str(row), "status": "pending"}


@router.get("/proposals")
def list_proposals(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    conditions = ["workspace_id = :workspace_id"]
    params: dict[str, Any] = {"workspace_id": _workspace_id(current_user)}
    if status:
        conditions.append("status = :status")
        params["status"] = status
    rows = db.execute(text(f"""
        SELECT id, engine_run_id, status, problem_statement, why_it_matters,
               maturity_level, priority_rank, priority_rationale,
               data_evidence, proposed_deliverables, implementation_sequence,
               dependencies, open_questions, domain_gotchas, approved_at,
               approved_by, implementation_agent_run_id, implemented_at,
               rejection_reason, created_at, updated_at
        FROM ai.research_proposals
        WHERE {" AND ".join(conditions)}
        ORDER BY priority_rank ASC, created_at DESC
    """), params).fetchall()
    return [_proposal_row(r) for r in rows]


@router.post("/proposals", status_code=201)
def create_proposal(
    body: ProposalCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = db.execute(text("""
        INSERT INTO ai.research_proposals (
            workspace_id, engine_run_id, problem_statement, why_it_matters,
            maturity_level, priority_rank, priority_rationale, data_evidence,
            proposed_deliverables, implementation_sequence, dependencies,
            open_questions, domain_gotchas
        ) VALUES (
            :workspace_id, :engine_run_id, :problem_statement, :why_it_matters,
            :maturity_level, :priority_rank, :priority_rationale, :data_evidence,
            :proposed_deliverables, :implementation_sequence, :dependencies,
            :open_questions, :domain_gotchas
        ) RETURNING id
    """), {
        "workspace_id": _workspace_id(current_user),
        "engine_run_id": body.engine_run_id,
        "problem_statement": body.problem_statement,
        "why_it_matters": body.why_it_matters,
        "maturity_level": body.maturity_level,
        "priority_rank": body.priority_rank,
        "priority_rationale": body.priority_rationale,
        "data_evidence": body.data_evidence,
        "proposed_deliverables": body.proposed_deliverables,
        "implementation_sequence": body.implementation_sequence,
        "dependencies": body.dependencies,
        "open_questions": body.open_questions,
        "domain_gotchas": body.domain_gotchas,
    }).scalar()
    db.commit()
    return {"id": str(row)}


@router.patch("/proposals/{proposal_id}/status")
def update_proposal_status(
    proposal_id: str,
    body: ProposalStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    allowed = {"proposed", "stage1_approved", "stage2_approved", "rejected", "implemented", "superseded"}
    if body.status not in allowed:
        raise HTTPException(400, "Unsupported proposal status")
    approved_at = datetime.now(timezone.utc) if body.status in {"stage1_approved", "stage2_approved"} else None
    implemented_at = datetime.now(timezone.utc) if body.status == "implemented" else None
    db.execute(text("""
        UPDATE ai.research_proposals
        SET status = :status,
            rejection_reason = COALESCE(:rejection_reason, rejection_reason),
            approved_at = COALESCE(:approved_at, approved_at),
            approved_by = COALESCE(:approved_by, approved_by),
            implemented_at = COALESCE(:implemented_at, implemented_at),
            updated_at = NOW()
        WHERE id = :proposal_id AND workspace_id = :workspace_id
    """), {
        "proposal_id": proposal_id,
        "workspace_id": _workspace_id(current_user),
        "status": body.status,
        "rejection_reason": body.rejection_reason,
        "approved_at": approved_at,
        "approved_by": _user_id(current_user) if approved_at else None,
        "implemented_at": implemented_at,
    })
    db.commit()
    return {"id": proposal_id, "status": body.status}


@router.get("/proposals/{proposal_id}/messages")
def list_proposal_messages(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT id, role, content, metadata, created_at
        FROM ai.research_proposal_messages
        WHERE proposal_id = :proposal_id
          AND EXISTS (
              SELECT 1 FROM ai.research_proposals rp
              WHERE rp.id = :proposal_id AND rp.workspace_id = :workspace_id
          )
        ORDER BY created_at ASC
    """), {"proposal_id": proposal_id, "workspace_id": _workspace_id(current_user)}).fetchall()
    return [
        {
            "id": str(r[0]),
            "role": r[1],
            "content": r[2],
            "metadata": r[3] or {},
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


@router.post("/proposals/{proposal_id}/messages", status_code=201)
def create_proposal_message(
    proposal_id: str,
    body: ProposalMessageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    exists = db.execute(text("""
        SELECT 1
        FROM ai.research_proposals
        WHERE id = :proposal_id AND workspace_id = :workspace_id
    """), {"proposal_id": proposal_id, "workspace_id": _workspace_id(current_user)}).scalar()
    if not exists:
        raise HTTPException(404, "Proposal not found")
    row = db.execute(text("""
        INSERT INTO ai.research_proposal_messages (proposal_id, role, content, metadata)
        VALUES (:proposal_id, :role, :content, :metadata)
        RETURNING id
    """), {"proposal_id": proposal_id, "role": body.role, "content": body.content, "metadata": body.metadata}).scalar()
    db.commit()
    return {"id": str(row)}


def _proposal_row(r) -> dict[str, Any]:
    return {
        "id": str(r[0]),
        "engine_run_id": str(r[1]) if r[1] else None,
        "status": r[2],
        "problem_statement": r[3],
        "why_it_matters": r[4],
        "maturity_level": r[5],
        "priority_rank": r[6],
        "priority_rationale": r[7],
        "data_evidence": r[8] or [],
        "proposed_deliverables": r[9] or [],
        "implementation_sequence": r[10] or [],
        "dependencies": r[11] or [],
        "open_questions": r[12] or [],
        "domain_gotchas": r[13] or [],
        "approved_at": r[14].isoformat() if r[14] else None,
        "approved_by": r[15],
        "implementation_agent_run_id": r[16],
        "implemented_at": r[17].isoformat() if r[17] else None,
        "rejection_reason": r[18],
        "created_at": r[19].isoformat() if r[19] else None,
        "updated_at": r[20].isoformat() if r[20] else None,
    }
