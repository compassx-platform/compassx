"""Task tracking routes for applications in the CompassX App module."""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.models.app_task import AppTask
from app.schemas.app_tasks import (
    AppTaskCreate,
    AppTaskUpdate,
    AppTaskStatusUpdate,
    AppTaskResponse,
    AppTaskReorderPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/apps/{app_id}/tasks", tags=["App Tasks"])


def _verify_app(app_id: str, db: Session, guard: Guard) -> App:
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Access to app tasks in another workspace is forbidden.")
    return app


@router.get("", response_model=List[AppTaskResponse])
def list_app_tasks(
    app_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all tasks associated with a given application."""
    _verify_app(app_id, db, guard)

    query = db.query(AppTask).filter(AppTask.app_id == app_id)

    if status_filter:
        query = query.filter(AppTask.status == status_filter)
    if priority_filter:
        query = query.filter(AppTask.priority == priority_filter)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (AppTask.title.ilike(pattern)) | (AppTask.description.ilike(pattern))
        )

    tasks = query.order_by(AppTask.order.asc(), AppTask.created_at.asc()).all()
    return tasks


@router.post("", response_model=AppTaskResponse, status_code=status.HTTP_201_CREATED)
def create_app_task(
    app_id: str,
    body: AppTaskCreate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new task within an application's task tracking board."""
    app = _verify_app(app_id, db, guard)

    target_status = body.status or "backlog"
    # Determine the next order index if not explicitly set
    order_val = body.order
    if order_val is None or order_val == 0:
        max_order = (
            db.query(func.max(AppTask.order))
            .filter(AppTask.app_id == app_id, AppTask.status == target_status)
            .scalar()
        )
        order_val = (max_order + 1) if max_order is not None else 0

    task_id = f"task_{uuid.uuid4().hex[:16]}"
    user_id = str(guard.principal.id) if guard.principal else None

    task = AppTask(
        id=task_id,
        app_id=app.id,
        workspace_id=app.workspace_id,
        title=body.title.strip(),
        description=body.description,
        status=target_status,
        priority=body.priority or "medium",
        tags=body.tags or [],
        assignee=body.assignee,
        due_date=body.due_date,
        order=order_val,
        created_by_user_id=user_id,
    )

    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("Created task '%s' (%s) for app '%s'", task.title, task.id, app_id)
    return task


@router.get("/{task_id}", response_model=AppTaskResponse)
def get_app_task(
    app_id: str,
    task_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve a single task by ID."""
    _verify_app(app_id, db, guard)

    task = db.query(AppTask).filter(AppTask.id == task_id, AppTask.app_id == app_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task


@router.put("/{task_id}", response_model=AppTaskResponse)
def update_app_task(
    app_id: str,
    task_id: str,
    body: AppTaskUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update all or subset of fields on an application task."""
    _verify_app(app_id, db, guard)

    task = db.query(AppTask).filter(AppTask.id == task_id, AppTask.app_id == app_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if body.title is not None:
        task.title = body.title.strip()
    if body.description is not None:
        task.description = body.description
    if body.status is not None:
        task.status = body.status
    if body.priority is not None:
        task.priority = body.priority
    if body.tags is not None:
        task.tags = body.tags
    if body.assignee is not None:
        task.assignee = body.assignee
    if body.due_date is not None:
        task.due_date = body.due_date
    if body.order is not None:
        task.order = body.order

    db.commit()
    db.refresh(task)
    logger.info("Updated task '%s' (%s) in app '%s'", task.title, task.id, app_id)
    return task


@router.patch("/{task_id}/status", response_model=AppTaskResponse)
def update_app_task_status(
    app_id: str,
    task_id: str,
    body: AppTaskStatusUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Quickly update the status and/or column order of an application task."""
    _verify_app(app_id, db, guard)

    task = db.query(AppTask).filter(AppTask.id == task_id, AppTask.app_id == app_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    task.status = body.status
    if body.order is not None:
        task.order = body.order

    db.commit()
    db.refresh(task)
    return task


@router.post("/reorder", response_model=List[AppTaskResponse])
def reorder_app_tasks(
    app_id: str,
    payload: AppTaskReorderPayload,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Batch update order and statuses of tasks following drag-and-drop operations."""
    _verify_app(app_id, db, guard)

    task_ids = [item.task_id for item in payload.items]
    if not task_ids:
        return []

    tasks = db.query(AppTask).filter(AppTask.id.in_(task_ids), AppTask.app_id == app_id).all()
    task_map = {t.id: t for t in tasks}

    for item in payload.items:
        task = task_map.get(item.task_id)
        if task:
            task.status = item.status
            task.order = item.order

    db.commit()
    return tasks


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app_task(
    app_id: str,
    task_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a task."""
    _verify_app(app_id, db, guard)

    task = db.query(AppTask).filter(AppTask.id == task_id, AppTask.app_id == app_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    db.delete(task)
    db.commit()
    logger.info("Deleted task '%s' (%s) from app '%s'", task.title, task.id, app_id)
    return None
