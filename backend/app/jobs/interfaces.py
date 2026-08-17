"""Deployment-independent ports used by the Jobs application layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SchedulerGateway(ABC):
    """Control-plane contract implemented by an orchestration adapter."""

    @abstractmethod
    def dag_exists(self, dag_id: str) -> bool: ...

    @abstractmethod
    def set_dag_paused(self, dag_id: str, paused: bool) -> None: ...

    @abstractmethod
    def trigger_run(self, dag_id: str, dag_run_id: str, conf: dict[str, Any]) -> None: ...

    @abstractmethod
    def cancel_run(self, dag_id: str, dag_run_id: str) -> None: ...

    @abstractmethod
    def retry_task(self, dag_id: str, dag_run_id: str, task_id: str) -> None: ...

    @abstractmethod
    def get_run(self, dag_id: str, dag_run_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_task_instances(self, dag_id: str, dag_run_id: str) -> list[dict[str, Any]]: ...
