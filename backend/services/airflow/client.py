"""Airflow REST adapter for the Jobs scheduler gateway."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.jobs.interfaces import SchedulerGateway
from services.airflow.config import airflow_settings


class AirflowSchedulerGateway(SchedulerGateway):
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=airflow_settings.api_base_url(),
            auth=(
                airflow_settings.AIRFLOW_CONTROL_USERNAME,
                airflow_settings.AIRFLOW_CONTROL_PASSWORD,
            ),
            timeout=airflow_settings.AIRFLOW_REQUEST_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _id(value: str) -> str:
        return quote(value, safe="")

    def dag_exists(self, dag_id: str) -> bool:
        response = self._client.get(f"/api/v1/dags/{self._id(dag_id)}")
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def set_dag_paused(self, dag_id: str, paused: bool) -> None:
        response = self._client.patch(
            f"/api/v1/dags/{self._id(dag_id)}",
            json={"is_paused": paused},
        )
        response.raise_for_status()

    def trigger_run(self, dag_id: str, dag_run_id: str, conf: dict[str, Any]) -> None:
        response = self._client.post(
            f"/api/v1/dags/{self._id(dag_id)}/dagRuns",
            json={"dag_run_id": dag_run_id, "conf": conf},
        )
        response.raise_for_status()

    def cancel_run(self, dag_id: str, dag_run_id: str) -> None:
        response = self._client.patch(
            f"/api/v1/dags/{self._id(dag_id)}/dagRuns/{self._id(dag_run_id)}",
            json={"state": "failed"},
        )
        response.raise_for_status()

    def retry_task(self, dag_id: str, dag_run_id: str, task_id: str) -> None:
        response = self._client.post(
            f"/api/v1/dags/{self._id(dag_id)}/clearTaskInstances",
            json={
                "dry_run": False,
                "dag_run_id": dag_run_id,
                "task_ids": [task_id],
                "include_upstream": False,
                "include_downstream": False,
                "include_future": False,
                "include_past": False,
                "reset_dag_runs": True,
            },
        )
        response.raise_for_status()

    def get_run(self, dag_id: str, dag_run_id: str) -> dict[str, Any]:
        response = self._client.get(
            f"/api/v1/dags/{self._id(dag_id)}/dagRuns/{self._id(dag_run_id)}"
        )
        response.raise_for_status()
        return response.json()

    def get_task_instances(self, dag_id: str, dag_run_id: str) -> list[dict[str, Any]]:
        response = self._client.get(
            f"/api/v1/dags/{self._id(dag_id)}/dagRuns/{self._id(dag_run_id)}/taskInstances"
        )
        response.raise_for_status()
        return response.json().get("task_instances", [])
