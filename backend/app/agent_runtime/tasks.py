"""Agent Runtime tasks.

A task waits until a person marks it ready. That move creates a session and
starts it with the task brief. The task outlives the session.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.agent_runtime.models import (
    AgentRuntimeTask,
    AgentRuntimeTaskDB,
    CreateAgentSessionRequest,
    CreateAgentTaskRequest,
    TaskEvent,
)

TASKS_STORE_PATH = os.path.join(
    os.path.expanduser("~"), ".compassx", "agent_runtime_tasks.json"
)

TERMINAL = {"done", "cancelled"}


def load_tasks(service) -> None:
    try:
        if os.path.exists(TASKS_STORE_PATH):
            with open(TASKS_STORE_PATH, "r", encoding="utf-8") as handle:
                for item in json.load(handle):
                    task = AgentRuntimeTask(**item)
                    service._tasks[task.id] = task
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to load stored tasks: %s", exc)


def create_task(service, req: CreateAgentTaskRequest, workspace_id: Optional[str] = None) -> AgentRuntimeTask:
    """File a task in draft. Filing does not start a session."""
    actor = _actor(req.actor)
    title = (req.title or "").strip()
    if not title:
        raise ValueError("Task title is empty.")
    if len(title) > 200:
        title = title[:200]
    project_id = (req.project_id or "").strip() or None
    if project_id and not service.get_project(project_id):
        raise ValueError(f"Project '{project_id}' does not exist.")
    source_session_id = (req.source_session_id or "").strip() or None
    if source_session_id and not service.get_session(source_session_id):
        raise ValueError(f"Session '{source_session_id}' not found.")
    now = _now()
    task = AgentRuntimeTask(
        id=f"art_{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        project_id=project_id,
        title=title,
        brief=(req.brief or "").strip(),
        stage="draft",
        source_session_id=source_session_id,
        agent_type=_agent_type(service, req.agent_type),
        llm_model=(req.llm_model or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    _record(task, actor, "created", "", "draft", "Filed")
    _save(service, task)
    return task


def inbox_is_idle(names: list[str]) -> bool:
    """A Nova turn is still running while an inbox file is waiting or marked working."""
    for name in names:
        if name.endswith(".working"):
            return False
        if name.endswith(".json") and not name.endswith(".done.json") and not name.endswith(".bad.json"):
            return False
    return True


def has_finished_reply(messages) -> bool:
    """True when the latest user turn has an assistant reply after it."""
    last_user = -1
    for index, message in enumerate(messages or []):
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", "")
        if role == "user":
            last_user = index
    if last_user < 0:
        return False
    for message in list(messages)[last_user + 1 :]:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", "")
        kind = message.get("kind") if isinstance(message, dict) else getattr(message, "kind", "")
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
        if role == "assistant" and kind == "reply" and str(content or "").strip():
            return True
    return False


def _task_for_session(service, session_id: str) -> Optional[AgentRuntimeTask]:
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                row = (
                    db.query(AgentRuntimeTaskDB)
                    .filter(AgentRuntimeTaskDB.session_id == session_id, AgentRuntimeTaskDB.stage == "in_progress")
                    .order_by(AgentRuntimeTaskDB.updated_at.desc())
                    .first()
                )
                if row:
                    task = row.to_pydantic()
                    with service._lock:
                        service._tasks[task.id] = task
                    return task
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to find the task for a session: %s", exc)
    with service._lock:
        matches = [
            task for task in service._tasks.values()
            if task.session_id == session_id and task.stage == "in_progress"
        ]
    return matches[0] if matches else None


def release_finished_session(service, session_id: str) -> Optional[AgentRuntimeTask]:
    """Move an in-progress task to review once Nova has finished its reply."""
    from app.sandbox.agents import is_nova_agent

    session = service.get_session(session_id)
    if not session or not is_nova_agent(session.agent_type):
        return None
    if not has_finished_reply(session.messages):
        return None
    task = _task_for_session(service, session_id)
    if not task:
        return None
    try:
        from app.agent_runtime.sandbox_controller import nova_sandbox_controller

        names = nova_sandbox_controller.inbox_names(session, service._exec)
    except Exception:
        return None
    if not inbox_is_idle(names):
        return None
    return submit_task(service, task.id, "Agent finished", "agent")


def list_tasks(service, workspace_id: Optional[str] = None) -> List[AgentRuntimeTask]:
    tasks = _query_tasks(service, workspace_id)
    for task in tasks:
        if task.stage != "in_progress" or not task.session_id:
            continue
        try:
            service.sync_terminal_notices(task.session_id)
        except Exception as exc:
            service_logger(service).warning("[AgentRuntimeService] Could not check a finished task: %s", exc)
    return _query_tasks(service, workspace_id)


def _query_tasks(service, workspace_id: Optional[str] = None) -> List[AgentRuntimeTask]:
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                query = db.query(AgentRuntimeTaskDB)
                if workspace_id:
                    query = query.filter(
                        (AgentRuntimeTaskDB.workspace_id == workspace_id)
                        | (AgentRuntimeTaskDB.workspace_id.is_(None))
                    )
                rows = query.order_by(AgentRuntimeTaskDB.updated_at.desc()).all()
                tasks = [row.to_pydantic() for row in rows]
                with service._lock:
                    for task in tasks:
                        service._tasks[task.id] = task
                return tasks
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to query tasks from DB, falling back to memory: %s", exc)

    with service._lock:
        tasks = list(service._tasks.values())
    if workspace_id:
        tasks = [task for task in tasks if not task.workspace_id or task.workspace_id == workspace_id]
    return sorted(tasks, key=lambda task: task.updated_at, reverse=True)


def get_task(service, task_id: str) -> Optional[AgentRuntimeTask]:
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                row = db.query(AgentRuntimeTaskDB).filter(AgentRuntimeTaskDB.id == task_id).first()
                if row:
                    task = row.to_pydantic()
                    with service._lock:
                        service._tasks[task.id] = task
                    return task
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to get task from DB, falling back to memory: %s", exc)
    with service._lock:
        return service._tasks.get(task_id)


def mark_waiting(service, task_id: str, note: str, actor: str) -> AgentRuntimeTask:
    """Park a draft, or stop an in-progress run that cannot continue."""
    task = _require(service, task_id)
    reason = _require_note(note, "A reason")
    who = _actor(actor)
    if task.stage in {"draft", "ready"}:
        if who != "person":
            raise ValueError("Only a person can park a task that has not started.")
        task.waiting_reason = reason
        task.start_error = ""
        _move(service, task, "waiting", who, reason)
        return task
    if task.stage == "in_progress":
        if who != "agent":
            raise ValueError("Only the agent can park a task that is in progress.")
        _stop_session(service, task.session_id)
        task.session_id = None
        task.waiting_reason = reason
        _move(service, task, "waiting", who, reason)
        return task
    raise ValueError(f"Task cannot be parked from {task.stage}.")


def mark_ready(service, task_id: str, actor: str) -> AgentRuntimeTask:
    """Person-only. Starts an Agent Runtime session for this task."""
    if _actor(actor) != "person":
        raise ValueError("Only a person can mark a task ready.")
    with service._lock:
        if task_id in service._starting_task_ids:
            raise ValueError("This task is already starting.")
        service._starting_task_ids.add(task_id)
    try:
        task = _require(service, task_id)
        if task.stage == "in_progress" and task.session_id:
            raise ValueError("A session is already running for this task.")
        if task.stage not in {"draft", "waiting", "ready"}:
            raise ValueError(f"Task cannot be started from {task.stage}.")
    except Exception:
        service._starting_task_ids.discard(task_id)
        raise
    session = None
    try:
        if task.stage != "ready":
            task.waiting_reason = ""
            task.start_error = ""
            _move(service, task, "ready", "person", "Marked ready")
        else:
            _record(task, "person", "retry", "ready", "ready", "Retrying start")
            _save(service, task)
        session = service.create_session(
            CreateAgentSessionRequest(
                title=task.title,
                agent_type=task.agent_type or "nova",
                sandbox_mode="new",
                project_id=task.project_id,
                llm_model=task.llm_model,
            ),
            workspace_id=task.workspace_id,
        )
        service.deliver_prompt(session.id, _start_prompt(task), llm_model=task.llm_model)
    except Exception as exc:
        if session is not None:
            service.delete_session(session.id)
        task.session_id = None
        task.start_error = str(exc)
        _record(task, "person", "start_failed", "ready", "ready", str(exc))
        _save(service, task)
        return task
    else:
        task.session_id = session.id
        task.start_error = ""
        _move(service, task, "in_progress", "agent", f"Session {session.id} started")
        return task
    finally:
        service._starting_task_ids.discard(task_id)


def submit_task(service, task_id: str, note: str, actor: str) -> AgentRuntimeTask:
    """Agent hands the outcome back. This does not accept the task."""
    if _actor(actor) != "agent":
        raise ValueError("Only the agent can submit a task for review.")
    task = _require(service, task_id)
    if task.stage != "in_progress":
        raise ValueError(f"Task cannot be submitted from {task.stage}.")
    _move(service, task, "in_review", "agent", (note or "").strip() or "Submitted for review")
    return task


def accept_task(service, task_id: str, actor: str) -> AgentRuntimeTask:
    if _actor(actor) != "person":
        raise ValueError("Only a person can accept a task.")
    task = _require(service, task_id)
    if task.stage != "in_review":
        raise ValueError(f"Task cannot be accepted from {task.stage}.")
    _move(service, task, "done", "person", "Accepted")
    return task


def request_changes(service, task_id: str, note: str, actor: str) -> AgentRuntimeTask:
    """Person sends the task back. The same session continues, or a new one starts."""
    if _actor(actor) != "person":
        raise ValueError("Only a person can request changes.")
    task = _require(service, task_id)
    if task.stage != "in_review":
        raise ValueError(f"Changes cannot be requested from {task.stage}.")
    comment = _require_note(note, "A review comment")
    with service._lock:
        if task_id in service._starting_task_ids:
            raise ValueError("This task is already starting.")
        service._starting_task_ids.add(task_id)
    created = None
    try:
        session = service.get_session(task.session_id) if task.session_id else None
        if session and session.status != "stopped":
            service.deliver_prompt(session.id, _changes_prompt(task, comment), llm_model=task.llm_model)
        else:
            created = service.create_session(
                CreateAgentSessionRequest(
                    title=task.title,
                    agent_type=task.agent_type or "nova",
                    sandbox_mode="new",
                    project_id=task.project_id,
                    llm_model=task.llm_model,
                ),
                workspace_id=task.workspace_id,
            )
            service.deliver_prompt(created.id, _changes_prompt(task, comment), llm_model=task.llm_model)
            task.session_id = created.id
        task.start_error = ""
        _move(service, task, "in_progress", "person", comment)
        return task
    except Exception as exc:
        if created is not None:
            service.delete_session(created.id)
        task.start_error = str(exc)
        _record(task, "person", "continue_failed", "in_review", "in_review", str(exc))
        _save(service, task)
        return task
    finally:
        service._starting_task_ids.discard(task_id)


def cancel_task(service, task_id: str, actor: str, note: str = "") -> AgentRuntimeTask:
    if _actor(actor) != "person":
        raise ValueError("Only a person can cancel a task.")
    task = _require(service, task_id)
    if task.stage in TERMINAL:
        raise ValueError(f"Task cannot be cancelled from {task.stage}.")
    if task.stage == "in_progress":
        _stop_session(service, task.session_id)
    _move(service, task, "cancelled", "person", (note or "").strip() or "Cancelled")
    return task


def _start_prompt(task: AgentRuntimeTask) -> str:
    brief = task.brief.strip() or "No additional brief."
    return (
        f"Task: {task.title}\n\n{brief}\n\n"
        "Do this task. If you cannot continue, say what is missing. "
        "When the work is finished, summarize the outcome. "
        "A person reviews that outcome before the task is done."
    )


def _changes_prompt(task: AgentRuntimeTask, comment: str) -> str:
    brief = task.brief.strip() or "No additional brief."
    return (
        f"Task: {task.title}\n\n{brief}\n\n"
        f"Changes requested: {comment}\n\n"
        "Continue this task. Summarize the outcome when the requested changes are done."
    )


def _agent_type(service, raw: Optional[str]) -> str:
    clean = (raw or "nova").lower().strip() or "nova"
    try:
        from app.sandbox.agents import agent_registry
        known = {item["id"] for item in agent_registry.catalog()}
        known.update({"bash"})
        if clean not in known:
            return "nova"
    except Exception:
        if clean not in {"nova", "antigravity", "pi", "opencode", "bash", "claude", "codex", "cursor"}:
            return "nova"
    return clean


def _actor(actor: str) -> str:
    who = (actor or "person").strip().lower()
    if who not in {"person", "agent"}:
        raise ValueError("Actor must be person or agent.")
    return who


def _require_note(note: str, label: str) -> str:
    clean = (note or "").strip()
    if not clean:
        raise ValueError(f"{label} is required.")
    return clean


def _require(service, task_id: str) -> AgentRuntimeTask:
    task = get_task(service, task_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found.")
    return task


def _move(service, task: AgentRuntimeTask, stage: str, actor: str, note: str) -> None:
    previous = task.stage
    task.stage = stage
    _record(task, actor, stage, previous, stage, note)
    _save(service, task)


def _record(task: AgentRuntimeTask, actor: str, action: str, from_stage: str, to_stage: str, note: str) -> None:
    task.updated_at = _now()
    task.events.append(TaskEvent(
        at=task.updated_at,
        actor=actor,
        action=action,
        from_stage=from_stage,
        to_stage=to_stage,
        note=note,
    ))


def _save(service, task: AgentRuntimeTask) -> None:
    task.updated_at = task.updated_at or _now()
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is not None:
            with SystemSessionLocal() as db:
                row = db.query(AgentRuntimeTaskDB).filter(AgentRuntimeTaskDB.id == task.id).first()
                payload = _row_values(task)
                if row is None:
                    db.add(AgentRuntimeTaskDB(**payload))
                else:
                    for key, value in payload.items():
                        setattr(row, key, value)
                db.commit()
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to save task to DB: %s", exc)
    with service._lock:
        service._tasks[task.id] = task
        _persist(service)


def _row_values(task: AgentRuntimeTask) -> dict:
    created = _parse_dt(task.created_at)
    updated = _parse_dt(task.updated_at)
    return {
        "id": task.id,
        "workspace_id": task.workspace_id,
        "project_id": task.project_id,
        "title": task.title,
        "brief": task.brief,
        "stage": task.stage,
        "waiting_reason": task.waiting_reason,
        "start_error": task.start_error,
        "source_session_id": task.source_session_id,
        "session_id": task.session_id,
        "agent_type": task.agent_type,
        "llm_model": task.llm_model,
        "events": [event.model_dump() for event in task.events],
        "created_at": created,
        "updated_at": updated,
    }


def _persist(service) -> None:
    try:
        os.makedirs(os.path.dirname(TASKS_STORE_PATH), exist_ok=True)
        with open(TASKS_STORE_PATH, "w", encoding="utf-8") as handle:
            json.dump([task.model_dump() for task in service._tasks.values()], handle, indent=2)
    except Exception as exc:
        service_logger(service).warning("[AgentRuntimeService] Failed to persist tasks to file fallback: %s", exc)


def _stop_session(service, session_id: Optional[str]) -> None:
    if not session_id:
        return
    session = service.get_session(session_id)
    if not session:
        return
    session.status = "stopped"
    service._persist_session_row(session)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def service_logger(service):
    import logging
    return getattr(service, "logger", None) or logging.getLogger("app.agent_runtime.service")
