from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class AppTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = "backlog"
    priority: str = "medium"
    tags: Optional[List[str]] = None
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    order: Optional[int] = 0


class AppTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    order: Optional[int] = None


class AppTaskStatusUpdate(BaseModel):
    status: str
    order: Optional[int] = None


class AppTaskItemReorder(BaseModel):
    task_id: str
    status: str
    order: int = 0


class AppTaskReorderPayload(BaseModel):
    items: List[AppTaskItemReorder]


class AppTaskResponse(BaseModel):
    id: str
    app_id: str
    workspace_id: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    tags: Optional[List[str]] = None
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    order: int = 0
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
