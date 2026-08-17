"""Publish-time validation for immutable Job versions."""

from __future__ import annotations

import re

from fastapi import HTTPException


def validate_job_spec(schedule_cron: str | None, tasks: list[dict]) -> None:
    if schedule_cron:
        fields = schedule_cron.split()
        if len(fields) != 5:
            raise HTTPException(status_code=422, detail="Schedule must be a five-field cron expression")
    keys = [task.get("task_key", "").strip() for task in tasks]
    if not keys or any(not key for key in keys):
        raise HTTPException(status_code=422, detail="A published job requires tasks with task keys")
    invalid_keys = [key for key in keys if not re.fullmatch(r"[a-z][a-z0-9_]{0,249}", key)]
    if invalid_keys:
        raise HTTPException(
            status_code=422,
            detail="Task keys must start with a lowercase letter and contain only lowercase letters, digits, and underscores",
        )
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="Task keys must be unique")
    known = set(keys)
    graph = {task["task_key"]: set(task.get("depends_on") or []) for task in tasks}
    for task in tasks:
        if task.get("task_type") not in {"notebook", "query", "dashboard_refresh"}:
            raise HTTPException(status_code=422, detail=f"Unsupported task type: {task.get('task_type')}")
        if not task.get("target_ref"):
            raise HTTPException(status_code=422, detail=f"Task {task['task_key']} requires a target")
        unknown = graph[task["task_key"]] - known
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Task {task['task_key']} has unknown dependencies: {sorted(unknown)}",
            )
        retry_count = task.get("retry_count")
        retry_delay = task.get("retry_delay_seconds")
        if retry_count is not None and not 0 <= retry_count <= 10:
            raise HTTPException(status_code=422, detail=f"Task {task['task_key']} retry count must be between 0 and 10")
        if retry_delay is not None and retry_delay < 0:
            raise HTTPException(status_code=422, detail=f"Task {task['task_key']} retry delay cannot be negative")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise HTTPException(status_code=422, detail="Task graph contains a cycle")
        if key in visited:
            return
        visiting.add(key)
        for dependency in graph[key]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in keys:
        visit(key)
