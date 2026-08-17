"""Airflow operator that dispatches work to CompassX execution APIs."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from airflow.exceptions import AirflowException
from airflow.models import BaseOperator


def _request(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise AirflowException(f"CompassX API returned {exc.code}: {detail}") from exc


def task_state_callback(context, state: str) -> None:
    backend_url = context["dag"].params["compassx_backend_url"]
    secret = context["dag"].params["compassx_internal_secret"]
    task_instance = context["task_instance"]
    payload = {
        "dag_id": context["dag"].dag_id,
        "dag_run_id": context["dag_run"].run_id,
        "task_id": task_instance.task_id,
        "try_number": max(task_instance.try_number, 1),
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        f"{backend_url}/api/v1/webhooks/airflow/task-state",
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-CompassX-Signature": signature,
        },
    )
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception as exc:
        print(f"[compassx] callback delivery failed: {exc}")


def on_success(context):
    task_state_callback(context, "success")


def on_failure(context):
    task_state_callback(context, "failed")


def on_retry(context):
    task_state_callback(context, "up_for_retry")


class CompassXTaskOperator(BaseOperator):
    """Thin dispatcher. User code never executes in the Airflow worker."""

    def __init__(self, *, task_spec: dict, backend_url: str, internal_secret: str, **kwargs):
        super().__init__(**kwargs)
        self.task_spec = task_spec
        self.backend_url = backend_url.rstrip("/")
        self.internal_secret = internal_secret

    def execute(self, context):
        task_state_callback(context, "running")
        task_instance = context["task_instance"]
        dag_run = context["dag_run"]
        conf = dag_run.conf or {}
        task_key = self.task_spec["task_key"]
        token_ref = (conf.get("execution_token_refs") or {}).get(task_key)
        internal_headers = {"X-CompassX-Internal-Secret": self.internal_secret}
        prepared = _request(
            "POST",
            f"{self.backend_url}/api/v1/internal/job-tasks/prepare",
            body={
                "dag_id": context["dag"].dag_id,
                "dag_run_id": dag_run.run_id,
                "task_key": task_key,
                "try_number": max(task_instance.try_number, 1),
                "token_ref": token_ref,
            },
            headers=internal_headers,
        )
        exchanged = _request(
            "POST",
            f"{self.backend_url}/api/v1/internal/execution-tokens/{prepared['token_ref']}/exchange",
            headers=internal_headers,
        )
        execution = _request(
            "POST",
            f"{self.backend_url}/api/v1/job-executions/run",
            body={
                "task_run_id": prepared["task_run_id"],
                "task_type": self.task_spec["task_type"],
                "target_ref": self.task_spec["target_ref"],
                "parameters": self.task_spec.get("parameters") or {},
            },
            headers={"Authorization": f"Bearer {exchanged['access_token']}"},
        )
        execution_ref = execution["execution_ref"]
        task_instance.xcom_push(key="execution_ref", value=execution_ref)
        timeout_at = time.monotonic() + float(self.execution_timeout.total_seconds() if self.execution_timeout else 3600)
        while time.monotonic() < timeout_at:
            status = _request(
                "GET",
                f"{self.backend_url}/api/v1/internal/job-executions/{execution_ref}",
                headers=internal_headers,
            )
            if status["state"] == "success":
                return {"execution_ref": execution_ref, "output_uri": status.get("output_uri")}
            if status["state"] == "failed":
                raise AirflowException(status.get("error") or "CompassX task execution failed")
            time.sleep(5)
        raise AirflowException("CompassX task execution timed out")
