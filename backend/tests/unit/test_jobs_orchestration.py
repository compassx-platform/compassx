import hashlib
import hmac

import httpx
import pytest
from fastapi import HTTPException

from app.jobs.security import verify_airflow_signature
from app.jobs.execution_service import task_executors
from app.jobs.validation import validate_job_spec
from compassx.runtime.spec_builders import default_spec_builders, NOTEBOOK_JOB_IMAGE
from services.airflow.client import AirflowSchedulerGateway
from services.airflow.config import airflow_settings


def _task(key="run_notebook", depends_on=None):
    return {
        "task_key": key,
        "task_type": "notebook",
        "target_ref": "example.ipynb",
        "depends_on": depends_on or [],
    }


def test_publish_validation_accepts_acyclic_notebook_graph():
    validate_job_spec("0 2 * * *", [_task("first"), _task("second", ["first"])])


def test_publish_validation_rejects_cycles():
    with pytest.raises(HTTPException, match="cycle"):
        validate_job_spec(None, [_task("first", ["second"]), _task("second", ["first"])])


def test_publish_validation_rejects_airflow_unsafe_task_key():
    with pytest.raises(HTTPException, match="Task keys"):
        validate_job_spec(None, [_task("Not Safe")])


def test_publish_validation_rejects_invalid_retry_policy():
    task = _task()
    task["retry_count"] = 11
    with pytest.raises(HTTPException, match="retry count"):
        validate_job_spec(None, [task])


def test_airflow_callback_signature_is_verified(monkeypatch):
    monkeypatch.setattr(airflow_settings, "AIRFLOW_CALLBACK_SECRET", "test-secret")
    body = b'{"state":"success"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    verify_airflow_signature(body, signature)
    with pytest.raises(HTTPException):
        verify_airflow_signature(body, "invalid")


def test_scheduler_gateway_triggers_correlated_run():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"dag_id": "compassx_job_1"})
        return httpx.Response(200, json={})

    client = httpx.Client(
        base_url="http://airflow.test",
        transport=httpx.MockTransport(handler),
    )
    gateway = AirflowSchedulerGateway(client)
    assert gateway.dag_exists("compassx_job_1")
    gateway.trigger_run(
        "compassx_job_1",
        "compassx_manual_1",
        {"job_run_id": "run-1"},
    )
    assert requests[-1].url.path.endswith("/dagRuns")
    assert b"compassx_manual_1" in requests[-1].content
    gateway.set_dag_paused("compassx_job_1", True)
    assert requests[-1].method == "PATCH"
    assert b'"is_paused":true' in requests[-1].content


def test_notebook_job_runtime_is_profile_independent():
    builder = default_spec_builders().get("notebook-job")
    spec = builder.build("job-exec-1", user_id="user-1")
    assert spec.runtime_type == "notebook-job"
    assert spec.container_image == NOTEBOOK_JOB_IMAGE
    assert spec.command == ["tail", "-f", "/dev/null"]


def test_local_dev_registers_notebook_task_executor():
    assert task_executors.get("notebook").task_type == "notebook"
    with pytest.raises(ValueError, match="No execution adapter"):
        task_executors.get("query")
