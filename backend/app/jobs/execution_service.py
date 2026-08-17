"""Profile-aware execution of Jobs tasks outside Airflow workers."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from abc import ABC, abstractmethod
from pathlib import PurePosixPath

from app.database import SystemSessionLocal
from app.jobs.models.run_trace import JobExecution
from app.jobs.security import utcnow
from services.storage.config import storage_settings

logger = logging.getLogger(__name__)


class TaskExecutor(ABC):
    """Execution strategy selected by task type, independent of Airflow."""

    task_type: str

    @abstractmethod
    def execute(
        self,
        execution_id: str,
        *,
        target_ref: str,
        parameters: dict,
        user_id: str,
        workspace_id: str,
        access_token: str,
        runtime_manager,
    ) -> None:
        raise NotImplementedError


class TaskExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, TaskExecutor] = {}

    def register(self, executor: TaskExecutor) -> None:
        self._executors[executor.task_type] = executor

    def get(self, task_type: str) -> TaskExecutor:
        try:
            return self._executors[task_type]
        except KeyError as exc:
            raise ValueError(f"No execution adapter is registered for task type: {task_type}") from exc

    def registered_types(self) -> set[str]:
        return set(self._executors)


def _notebook_command(notebook_path: str, parameters: dict, execution_id: str) -> list[str]:
    safe_name = PurePosixPath(notebook_path).stem or "notebook"
    input_path = f"/tmp/compassx/{execution_id}/{safe_name}.ipynb"
    output_path = f"/tmp/compassx/{execution_id}/{safe_name}-output.ipynb"
    parameter_args = " ".join(
        f"-p {shlex.quote(str(key))} {shlex.quote(json.dumps(value) if not isinstance(value, str) else value)}"
        for key, value in parameters.items()
    )
    command = " && ".join(
        [
            f"mkdir -p {shlex.quote(str(PurePosixPath(input_path).parent))}",
            (
                "python /opt/compassx/download_notebook.py "
                f"{shlex.quote(execution_id)} {shlex.quote(input_path)}"
            ),
            (
                f"papermill {shlex.quote(input_path)} {shlex.quote(output_path)} "
                f"{parameter_args}".rstrip()
            ),
            (
                f"COMPASSX_OUTPUT_FILENAME={shlex.quote(PurePosixPath(output_path).name)} "
                "python /opt/compassx/upload_notebook_output.py "
                f"{shlex.quote(output_path)}"
            ),
        ]
    )
    return ["sh", "-c", command]


def _execute_notebook(
    execution_id: str,
    *,
    notebook_path: str,
    parameters: dict,
    user_id: str,
    workspace_id: str,
    access_token: str,
    runtime_manager,
) -> None:
    """Background entry point; owns its DB session and ephemeral runtime."""
    db = SystemSessionLocal()
    runtime_id = f"job-exec-{execution_id.replace('-', '')[:12]}"
    execution = db.query(JobExecution).filter(
        JobExecution.execution_id == execution_id
    ).first()
    if execution is None:
        db.close()
        return
    try:
        execution.state = "running"
        execution.runtime_id = runtime_id
        execution.started_at = utcnow()
        db.commit()

        async def _run():
            await runtime_manager.create_runtime(
                "notebook-job",
                runtime_id=runtime_id,
                user_id=user_id,
                workspace_id=workspace_id,
                options={
                    "profile_id": "job",
                    "requests": {"cpu": "250m", "memory": "512Mi"},
                    "limits": {"cpu": "1", "memory": "1Gi"},
                    "extra_env": {
                        "COMPASSX_ENV": "runtime",
                        "STORAGE_BACKEND": storage_settings.STORAGE_BACKEND,
                        "STORAGE_NOTEBOOKS_BUCKET": storage_settings.STORAGE_NOTEBOOKS_BUCKET,
                        "STORAGE_NOTEBOOKS_PREFIX": storage_settings.STORAGE_NOTEBOOKS_PREFIX,
                        "STORAGE_OUTPUTS_BUCKET": storage_settings.STORAGE_OUTPUTS_BUCKET,
                        "STORAGE_OUTPUTS_PREFIX": storage_settings.STORAGE_OUTPUTS_PREFIX,
                        "MINIO_INTERNAL_ENDPOINT": storage_settings.MINIO_INTERNAL_ENDPOINT,
                        "MINIO_ACCESS_KEY": storage_settings.MINIO_ACCESS_KEY,
                        "MINIO_SECRET_KEY": storage_settings.MINIO_SECRET_KEY,
                        "COMPASSX_BACKEND_URL": __import__(
                            "compassx.lookup", fromlist=["try_resolve_url_container"]
                        ).try_resolve_url_container("backend", "http://host.docker.internal:8000"),
                        "COMPASSX_EXECUTION_TOKEN": access_token,
                    },
                },
            )
            return await runtime_manager.exec(
                runtime_id,
                _notebook_command(notebook_path, parameters, execution_id),
            )

        result = asyncio.run(_run())
        execution.logs = (result.stdout or "")[-100_000:]
        if result.exit_code:
            raise RuntimeError(result.stderr or f"Notebook exited with code {result.exit_code}")
        output_lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        execution.output_uri = output_lines[-1] if output_lines else None
        execution.state = "success"
    except Exception as exc:
        logger.exception("Notebook job execution failed: %s", execution_id)
        execution.state = "failed"
        execution.error = str(exc)[:10_000]
    finally:
        execution.ended_at = utcnow()
        db.commit()
        try:
            asyncio.run(runtime_manager.delete_runtime(runtime_id))
        except Exception:
            logger.warning("Could not delete job runtime %s", runtime_id, exc_info=True)
        db.close()


class NotebookTaskExecutor(TaskExecutor):
    task_type = "notebook"

    def execute(
        self,
        execution_id: str,
        *,
        target_ref: str,
        parameters: dict,
        user_id: str,
        workspace_id: str,
        access_token: str,
        runtime_manager,
    ) -> None:
        _execute_notebook(
            execution_id,
            notebook_path=target_ref,
            parameters=parameters,
            user_id=user_id,
            workspace_id=workspace_id,
            access_token=access_token,
            runtime_manager=runtime_manager,
        )


task_executors = TaskExecutorRegistry()
task_executors.register(NotebookTaskExecutor())


def execute_task(
    execution_id: str,
    *,
    task_type: str,
    target_ref: str,
    parameters: dict,
    user_id: str,
    workspace_id: str,
    access_token: str,
    runtime_manager,
) -> None:
    task_executors.get(task_type).execute(
        execution_id,
        target_ref=target_ref,
        parameters=parameters,
        user_id=user_id,
        workspace_id=workspace_id,
        access_token=access_token,
        runtime_manager=runtime_manager,
    )


def recover_orphaned_executions(runtime_manager) -> int:
    """Fail and clean executions whose owning backend process was restarted."""
    db = SystemSessionLocal()
    recovered = 0
    try:
        executions = (
            db.query(JobExecution)
            .filter(JobExecution.state.in_(["queued", "running"]))
            .all()
        )
        for execution in executions:
            execution.state = "failed"
            execution.error = "Execution interrupted because the backend restarted."
            execution.ended_at = utcnow()
            db.commit()
            if execution.runtime_id:
                try:
                    asyncio.run(runtime_manager.delete_runtime(execution.runtime_id))
                except Exception:
                    logger.warning(
                        "Could not remove orphaned job runtime %s",
                        execution.runtime_id,
                        exc_info=True,
                    )
            recovered += 1
        return recovered
    finally:
        db.close()
