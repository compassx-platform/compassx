"""Database-backed CompassX DAG factory (shard 1)."""

from __future__ import annotations

import hashlib
import os
from datetime import timedelta

import pendulum
import psycopg2
from airflow import DAG

from compassx_operator import (
    CompassXTaskOperator,
    on_failure,
    on_retry,
    on_success,
)

SHARD_INDEX = 0
SHARD_COUNT = max(int(os.environ.get("COMPASSX_DAG_SHARD_COUNT", "1")), 1)
SYSTEM_DB_URL = os.environ["COMPASSX_SYSTEM_DB_URL"]
BACKEND_URL = os.environ.get("COMPASSX_BACKEND_URL", "http://host.docker.internal:8000").rstrip("/")
INTERNAL_SECRET = os.environ["COMPASSX_INTERNAL_SECRET"]
_dag_cache = {}


def _belongs_to_shard(job_id: str) -> bool:
    digest = int(hashlib.sha256(job_id.encode()).hexdigest()[:16], 16)
    return digest % SHARD_COUNT == SHARD_INDEX


def _load_specs() -> list[dict]:
    with psycopg2.connect(SYSTEM_DB_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT job_id::text, dag_id, job_version, workspace_id::text,
                       schedule_cron, timezone, max_active_runs, retry_policy,
                       resolved_tasks, spec_checksum
                FROM jobs.airflow_job_specs
                WHERE is_active = TRUE
            """)
            columns = [item.name for item in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
                if _belongs_to_shard(str(row[0]))
            ]


def _build_dag(spec: dict) -> DAG:
    retry = spec["retry_policy"] or {}
    dag = DAG(
        dag_id=spec["dag_id"],
        schedule=spec["schedule_cron"],
        start_date=pendulum.datetime(2026, 1, 1, tz=spec["timezone"] or "UTC"),
        catchup=False,
        max_active_runs=spec["max_active_runs"] or 1,
        default_args={
            "owner": "compassx",
            "retries": retry.get("retries", 0),
            "retry_delay": timedelta(seconds=retry.get("retry_delay_seconds", 300)),
        },
        tags=["compassx", f"workspace:{spec['workspace_id'] or 'global'}"],
        params={
            "compassx_backend_url": BACKEND_URL,
            "compassx_internal_secret": INTERNAL_SECRET,
        },
    )
    operators = {}
    for task_spec in spec["resolved_tasks"] or []:
        task_key = task_spec["task_key"]
        task_options = {}
        if task_spec.get("retry_count") is not None:
            task_options["retries"] = task_spec["retry_count"]
        if task_spec.get("retry_delay_seconds") is not None:
            task_options["retry_delay"] = timedelta(
                seconds=task_spec["retry_delay_seconds"]
            )
        operators[task_key] = CompassXTaskOperator(
            dag=dag,
            task_id=task_key,
            task_spec=task_spec,
            backend_url=BACKEND_URL,
            internal_secret=INTERNAL_SECRET,
            on_success_callback=on_success,
            on_failure_callback=on_failure,
            on_retry_callback=on_retry,
            **task_options,
        )
    for task_spec in spec["resolved_tasks"] or []:
        for dependency in task_spec.get("depends_on") or []:
            operators[task_spec["task_key"]].set_upstream(operators[dependency])
    return dag


try:
    active_ids = set()
    for row in _load_specs():
        active_ids.add(row["job_id"])
        cached = _dag_cache.get(row["job_id"])
        if cached and cached[0] == row["spec_checksum"]:
            dag = cached[1]
        else:
            dag = _build_dag(row)
            _dag_cache[row["job_id"]] = (row["spec_checksum"], dag)
        globals()[row["dag_id"]] = dag
    for stale_id in set(_dag_cache) - active_ids:
        _dag_cache.pop(stale_id, None)
except Exception as exc:
    print(f"[compassx] DAG factory could not load job specifications: {exc}")
