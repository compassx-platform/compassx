"""Change Capture Service — SOLID-compliant change capture, diffing, acceptance, and rollback service."""

from __future__ import annotations

import difflib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.services.agent.change_capture.registry import get_change_handler_registry

logger = logging.getLogger(__name__)


def _normalize_text(text: str | None) -> str:
    """Normalize line endings to standard Unix newline LF."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _compute_diff_counts(before: str | None, after: str | None) -> tuple[int, int]:
    """Return (additions, deletions) line counts between before and after."""
    norm_before = _normalize_text(before)
    norm_after = _normalize_text(after)
    before_lines = norm_before.splitlines()
    after_lines = norm_after.splitlines()
    diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
    additions = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return additions, deletions


def capture_change(
    db: Session,
    session_id: int,
    full_name: str,
    object_type: str,
    before: str | None,
    after: str,
    step_id: int | None = None,
    plan_id: str | None = None,
) -> Any:
    """
    Record a before/after change for any asset edit or creation.
    Persists a ChangeRecord to the database.
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        logger.warning("ChangeRecord model not available — skipping capture")
        return None

    norm_before = _normalize_text(before) if before is not None else None
    norm_after = _normalize_text(after)

    if norm_before is None:
        try:
            prev_rec = (
                db.query(ChangeRecord)
                .filter(ChangeRecord.session_id == session_id, ChangeRecord.full_name == full_name)
                .order_by(ChangeRecord.captured_at.desc())
                .first()
            )
            if prev_rec and prev_rec.after_content is not None:
                norm_before = _normalize_text(prev_rec.after_content)
        except Exception as prev_err:
            logger.debug("Failed to query previous change record: %s", prev_err)

    additions, deletions = _compute_diff_counts(norm_before, norm_after)
    record = ChangeRecord(
        change_id=str(uuid.uuid4()),
        session_id=session_id,
        full_name=full_name,
        object_type=object_type,
        before_content=norm_before,
        after_content=norm_after,
        additions=additions,
        deletions=deletions,
        status="pending_review",
        step_id=step_id,
        plan_id=plan_id,
        captured_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "Captured change %s for %s (%s): +%d -%d",
        record.change_id, full_name, object_type, additions, deletions,
    )
    return record


def capture_tool_change(
    db: Session,
    session_id: int,
    tool_name: str,
    arguments: dict[str, Any],
    result_payload: dict[str, Any],
    step_id: int | None = None,
    plan_id: str | None = None,
    goal: str | None = None,
    context: dict[str, Any] | None = None,
) -> Optional[dict[str, Any]]:
    """
    Modular tool change capture dispatcher (DIP & OCP).

    Finds the appropriate handler for the executed tool, checks mutation,
    resolves canonical full_name, serializes the current state, and records the change.
    """
    registry = get_change_handler_registry()
    pld = arguments.get("payload") if isinstance(arguments.get("payload"), dict) else arguments
    op = arguments.get("operation") or pld.get("operation")

    handler = registry.find_handler_for_tool(tool_name, operation=op, payload=pld)
    if not handler:
        return None

    if not handler.is_mutating(tool_name, operation=op, payload=pld):
        return None

    fn = handler.resolve_full_name(
        tool_name=tool_name,
        operation=op,
        payload=pld,
        result=result_payload,
        context=context,
        goal=goal,
    )
    if not fn:
        return None

    after = handler.serialize_current_state(
        full_name=fn,
        tool_name=tool_name,
        operation=op,
        payload=pld,
        result=result_payload,
        context=context,
    )
    if not after:
        # Fallback to direct code / source in arguments or result
        after = (
            result_payload.get("after_content")
            or result_payload.get("content")
            or result_payload.get("code")
            or pld.get("code")
            or pld.get("content")
        )
    if not after or not isinstance(after, str):
        return None

    # Before content from previous record or arguments
    before = result_payload.get("before_content") or pld.get("before_content")

    rec = capture_change(
        db=db,
        session_id=session_id,
        full_name=fn,
        object_type=handler.object_type,
        before=before,
        after=after,
        step_id=step_id,
        plan_id=plan_id,
    )
    if not rec:
        return None

    return {
        "change_id": rec.change_id,
        "full_name": rec.full_name,
        "object_type": rec.object_type,
        "additions": rec.additions,
        "deletions": rec.deletions,
        "status": rec.status,
    }


def accept_change(db: Session, change_id: str) -> dict[str, Any]:
    """Accept a pending change — confirms status as 'accepted' and invokes handler hook."""
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    record = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not record:
        return {"error": f"Change {change_id} not found", "ok": False}

    registry = get_change_handler_registry()
    handler = registry.get_handler_for_type(record.object_type)
    if handler:
        try:
            handler.accept(record.full_name, record.after_content)
        except Exception as exc:
            logger.warning("Handler accept hook failed for %s: %s", record.full_name, exc)

    record.status = "accepted"
    db.commit()
    return {"change_id": change_id, "status": "accepted", "ok": True}


def reject_change(
    db: Session,
    change_id: str,
    session_id: int,
) -> dict[str, Any]:
    """
    Reject a change — reverts the underlying asset using its registered handler,
    marks original record as 'rejected', and logs a linked revert ChangeRecord.
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    record = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not record:
        return {"error": f"Change {change_id} not found", "ok": False}

    # Revert via handler
    registry = get_change_handler_registry()
    handler = registry.get_handler_for_type(record.object_type)
    revert_ok = False
    if handler:
        try:
            revert_ok = handler.revert(record.full_name, record.before_content)
        except Exception as exc:
            logger.exception("Handler revert failed for %s: %s", record.full_name, exc)

    if not revert_ok:
        logger.warning("Revert handler reported False for %s", record.full_name)

    # Capture the revert as a new change record
    additions, deletions = _compute_diff_counts(record.after_content, record.before_content)
    revert_record = ChangeRecord(
        change_id=str(uuid.uuid4()),
        session_id=session_id,
        full_name=record.full_name,
        object_type=record.object_type,
        before_content=record.after_content,
        after_content=record.before_content,
        additions=additions,
        deletions=deletions,
        status="accepted",
        step_id=record.step_id,
        plan_id=record.plan_id,
        reverted_by_change_id=change_id,
        captured_at=datetime.now(timezone.utc),
    )
    db.add(revert_record)

    # Mark original as rejected
    record.status = "rejected"
    record.reverted_by_change_id = revert_record.change_id
    db.commit()

    return {
        "original_change_id": change_id,
        "revert_change_id": revert_record.change_id,
        "full_name": record.full_name,
        "status": "rejected",
        "revert_status": "accepted",
        "note": "Revert applied and recorded with before-content.",
        "ok": True,
    }


def bulk_review_changes(
    db: Session,
    session_id: int,
    action: str,  # "accept_all" | "reject_all"
) -> dict[str, Any]:
    """Approve or reject all pending changes for a session."""
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    pending_records = (
        db.query(ChangeRecord)
        .filter(ChangeRecord.session_id == session_id, ChangeRecord.status == "pending_review")
        .all()
    )

    results = []
    for r in pending_records:
        if action == "accept_all":
            res = accept_change(db, r.change_id)
        else:
            res = reject_change(db, r.change_id, session_id)
        results.append(res)

    return {
        "ok": True,
        "action": action,
        "session_id": session_id,
        "count": len(results),
        "results": results,
    }


def get_change_record(db: Session, change_id: str) -> Optional[dict[str, Any]]:
    """Retrieve full change record detail including before and after content."""
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return None

    r = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not r:
        return None
    return {
        "change_id": r.change_id,
        "session_id": r.session_id,
        "full_name": r.full_name,
        "object_type": r.object_type,
        "before_content": r.before_content,
        "after_content": r.after_content,
        "additions": r.additions,
        "deletions": r.deletions,
        "status": r.status,
        "step_id": r.step_id,
        "plan_id": r.plan_id,
        "reverted_by_change_id": r.reverted_by_change_id,
        "captured_at": r.captured_at.isoformat() if r.captured_at else None,
    }


def get_changes_for_session(
    db: Session,
    session_id: int,
    step_id: int | None = None,
    include_content: bool = True,
) -> list[dict[str, Any]]:
    """List all change records for a session, optionally filtered by step."""
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return []

    q = db.query(ChangeRecord).filter(ChangeRecord.session_id == session_id)
    if step_id is not None:
        q = q.filter(ChangeRecord.step_id == step_id)
    records = q.order_by(ChangeRecord.captured_at.asc()).all()
    return [
        {
            "change_id": r.change_id,
            "session_id": r.session_id,
            "full_name": r.full_name,
            "object_type": r.object_type,
            "before_content": r.before_content if include_content else None,
            "after_content": r.after_content if include_content else None,
            "additions": r.additions,
            "deletions": r.deletions,
            "status": r.status,
            "step_id": r.step_id,
            "plan_id": r.plan_id,
            "reverted_by_change_id": r.reverted_by_change_id,
            "captured_at": r.captured_at.isoformat() if r.captured_at else None,
        }
        for r in records
    ]
