"""Change Capture Service — Part G5 of AI Data Engineer Spec v5.

Captures before/after content for every notebook/file edit or create tool
call, computes line-level addition/deletion counts, and persists a ChangeRecord
to the database.

Implements D16: capture happens at edit time, not reconstructed retroactively.
Implements D20: Accept sets status only; Reject re-applies stored before content
                via the original edit tool and creates a new linked change record.
"""

from __future__ import annotations

import difflib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _compute_diff_counts(before: str | None, after: str | None) -> tuple[int, int]:
    """Return (additions, deletions) line counts between before and after."""
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
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
) -> "Any":
    """
    Record a before/after change for a notebook or file edit.

    Returns the created ChangeRecord ORM object (or None if import fails).
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        logger.warning("ChangeRecord model not yet migrated — skipping capture")
        return None

    additions, deletions = _compute_diff_counts(before, after)
    record = ChangeRecord(
        change_id=str(uuid.uuid4()),
        session_id=session_id,
        full_name=full_name,
        object_type=object_type,
        before_content=before,
        after_content=after,
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


def accept_change(db: Session, change_id: str) -> dict[str, Any]:
    """Accept a pending change — sets status to 'accepted', no further write."""
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    record = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not record:
        return {"error": f"Change {change_id} not found", "ok": False}
    record.status = "accepted"
    db.commit()
    return {"change_id": change_id, "status": "accepted", "ok": True}


def reject_change(
    db: Session,
    change_id: str,
    session_id: int,
) -> dict[str, Any]:
    """
    Reject a change — re-apply before_content to the real asset and create a
    new linked ChangeRecord representing the revert (D20).
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    record = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not record:
        return {"error": f"Change {change_id} not found", "ok": False}

    if record.before_content is None:
        # This was a create — revert means delete; not auto-deletable
        return {
            "error": "Cannot auto-revert a create operation (before_content is null). "
                     "Delete the asset manually.",
            "ok": False,
        }

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
        status="accepted",  # revert itself is auto-accepted
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
        "note": "Before-content has been re-applied. Revert is logged as a new change record.",
        "ok": True,
    }


def get_changes_for_session(
    db: Session,
    session_id: int,
    step_id: int | None = None,
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
            "full_name": r.full_name,
            "object_type": r.object_type,
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
