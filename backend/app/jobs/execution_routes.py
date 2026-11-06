"""Internal operator protocol and public task execution endpoints.

Handlers stay here. Each one forwards to one application type.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.jobs.task.application.download_execution_notebook import (
    download_execution_notebook as download_execution_notebook_action,
)
from app.jobs.task.application.exchange_token import exchange_token as exchange_token_action
from app.jobs.task.application.execution_status import execution_status as execution_status_action
from app.jobs.task.application.prepare_task import prepare_task as prepare_task_action
from app.jobs.task.application.run_task import run_task as run_task_action
from app.jobs.dependencies import get_scheduler_gateway
from app.jobs.interfaces import SchedulerGateway

internal_router = APIRouter(prefix="/api/v1/internal", tags=["jobs-internal"])
execution_router = APIRouter(prefix="/api/v1/job-executions", tags=["job-executions"])


class PrepareTaskIn(BaseModel):
    dag_id: str
    dag_run_id: str
    task_key: str
    try_number: int = 1
    token_ref: str | None = None


class TaskExecutionIn(BaseModel):
    task_run_id: uuid.UUID
    task_type: str
    target_ref: str
    parameters: dict = Field(default_factory=dict)


@internal_router.post("/job-tasks/prepare")
def prepare_task(
    body: PrepareTaskIn,
    x_compassx_internal_secret: str | None = Header(None),
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    return prepare_task_action(body, x_compassx_internal_secret, gateway, db)


@internal_router.post("/execution-tokens/{token_ref}/exchange")
def exchange_token(
    token_ref: str,
    x_compassx_internal_secret: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    return exchange_token_action(token_ref, x_compassx_internal_secret, db)


@execution_router.post("/run", status_code=202)
def run_task(
    body: TaskExecutionIn,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    return run_task_action(body, request, background_tasks, authorization, db)


@execution_router.get("/{execution_id}/notebook")
async def download_execution_notebook(
    execution_id: str,
    authorization: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    return await download_execution_notebook_action(execution_id, authorization, db)


@internal_router.get("/job-executions/{execution_id}")
def execution_status(
    execution_id: str,
    x_compassx_internal_secret: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    return execution_status_action(execution_id, x_compassx_internal_secret, db)
