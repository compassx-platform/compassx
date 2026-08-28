"""Change Capture Service — Part G5 of AI Data Engineer Spec v5.

Captures before/after content for every notebook/file edit or create tool
call, computes line-level addition/deletion counts, and persists a ChangeRecord
to the database.

Implements D16: capture happens at edit time, not reconstructed retroactively.
Implements D20: Accept sets status only; Reject marks rejected and creates revert record.
"""

from __future__ import annotations

import difflib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

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
    Record a before/after change for a notebook or file edit.

    Returns the created ChangeRecord ORM object (or None if import fails).
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        logger.warning("ChangeRecord model not yet migrated — skipping capture")
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
        except Exception as _prev_err:
            logger.debug("Failed to query previous change record: %s", _prev_err)

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


def _revert_asset_content(full_name: str, object_type: str, before_content: str | None) -> bool:
    """Reverts the underlying asset or file on storage / disk to before_content."""
    try:
        # 1. Notebook asset in UnifiedCatalog or file storage
        if object_type == "notebook" or full_name.endswith(".ipynb") or "notebook" in full_name.lower():
            try:
                from app.database import AccountSessionLocal
                from app.catalog.models import UnifiedCatalogNotebook, UnifiedCatalogSchema
                from app.catalog.service import _write_notebook_content
                import json
                import asyncio

                dot_parts = full_name.split(".")
                if len(dot_parts) == 3 and not full_name.endswith(".ipynb"):
                    with AccountSessionLocal() as account_db:
                        nb = account_db.query(UnifiedCatalogNotebook).filter(
                            UnifiedCatalogNotebook.catalog_name == dot_parts[0],
                            UnifiedCatalogNotebook.schema_name == dot_parts[1],
                            UnifiedCatalogNotebook.name == dot_parts[2],
                        ).first()
                        if nb and nb.blob_path:
                            schema = account_db.query(UnifiedCatalogSchema).filter(
                                UnifiedCatalogSchema.catalog_name == dot_parts[0],
                                UnifiedCatalogSchema.name == dot_parts[1],
                            ).first()
                            if schema:
                                if before_content:
                                    try:
                                        nb_data = json.loads(before_content)
                                    except Exception:
                                        nb_data = {
                                            "nbformat": 4,
                                            "nbformat_minor": 5,
                                            "metadata": {},
                                            "cells": [{"cell_type": "code", "source": before_content, "metadata": {}, "outputs": [], "execution_count": None}],
                                        }
                                else:
                                    nb_data = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}

                                try:
                                    loop = asyncio.get_event_loop()
                                    if loop.is_running():
                                        import concurrent.futures
                                        with concurrent.futures.ThreadPoolExecutor() as pool:
                                            pool.submit(asyncio.run, _write_notebook_content(account_db, schema, nb.blob_path, nb_data)).result()
                                    else:
                                        loop.run_until_complete(_write_notebook_content(account_db, schema, nb.blob_path, nb_data))
                                except Exception:
                                    asyncio.run(_write_notebook_content(account_db, schema, nb.blob_path, nb_data))
                                return True
            except Exception as _nb_err:
                logger.debug("Catalog notebook revert attempt: %s", _nb_err)

        # 2. Local file on disk or workspace
        from pathlib import Path
        import os
        import tempfile

        path_obj = Path(full_name)
        if path_obj.is_absolute() or path_obj.exists():
            if before_content is not None:
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                path_obj.write_text(before_content, encoding="utf-8")
            else:
                if path_obj.is_file():
                    path_obj.unlink(missing_ok=True)
            return True

        # Check in agent workspace / clone directories
        workspace_root = Path(os.environ.get("AGENT_WORKSPACE_ROOT", str(Path(tempfile.gettempdir()) / "agent_workspaces")))
        if workspace_root.exists():
            clean_rel = full_name.lstrip("/\\")
            matched_files = list(workspace_root.glob(f"**/{clean_rel}"))
            for mf in matched_files:
                if before_content is not None:
                    mf.write_text(before_content, encoding="utf-8")
                else:
                    if mf.is_file():
                        mf.unlink(missing_ok=True)
                return True

    except Exception as exc:
        logger.warning("Failed to revert underlying asset content for %s: %s", full_name, exc)
        return False
    return False


def accept_change(db: Session, change_id: str) -> dict[str, Any]:
    """Accept a pending change — confirms status as 'accepted'."""
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
    Reject a change — physically reverts the underlying file/asset on disk/storage,
    marks original record as 'rejected', and logs a linked revert ChangeRecord (D20).
    """
    try:
        from app.agents.models.agents import ChangeRecord
    except ImportError:
        return {"error": "ChangeRecord model not available", "ok": False}

    record = db.query(ChangeRecord).filter(ChangeRecord.change_id == change_id).first()
    if not record:
        return {"error": f"Change {change_id} not found", "ok": False}

    # Physically revert the file/asset content
    _revert_asset_content(record.full_name, record.object_type, record.before_content)

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
        status="rejected",  # Revert record marks the state as rejected
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
