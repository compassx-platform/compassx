"""
Generic REST executor for Pull-Based API Ingestion.

Called by the API trigger endpoint (manual) or by the Airflow task (scheduled).
Implements:
  - param-value resolution (static / catalog_query / parent_api)
  - bounded-concurrency fan-out (ThreadPoolExecutor, max = connection.max_concurrency)
  - per-param HTTP fetch with pagination (none / offset / page / cursor_field)
  - token-bucket rate limiting per connection (shared across concurrent workers)
  - exponential backoff with Retry-After support on 429 / 5xx
  - watermark extraction + advance-on-success (at-least-once per D8)
  - bronze blob writes (compassx-bronze/<workspace_id>/ingestion/<job_config_id>/<param>/<run_id>/page_N.json)
  - _manifest.json per (job_config_id, param_value, run_id)
  - ingestion_run + ingestion_run_item persistence

Per spec §10:
  - 429: read Retry-After if present, else exponential backoff (base=1s, max=60s, max_attempts=5)
  - 5xx: same backoff, max_attempts=3
  - 4xx other: no retry — fail immediately
  - max_pages per param per run: 500 (configurable via INGESTION_MAX_PAGES env)
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import requests
from jsonpath_ng.ext import parse as jsonpath_parse
from sqlalchemy.orm import Session

from app.ingestion.models import (
    IngestionConnection,
    IngestionJobConfig,
    IngestionRun,
    IngestionRunItem,
)
from app.ingestion.watermarks import NONE_SENTINEL, advance_watermark, get_watermark

logger = logging.getLogger(__name__)

MAX_PAGES_DEFAULT = int(os.environ.get("INGESTION_MAX_PAGES", "500"))
BACKOFF_BASE = 1.0
BACKOFF_MAX = 60.0
MAX_ATTEMPTS_429 = 5
MAX_ATTEMPTS_5XX = 3


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (per Connection, shared across concurrent workers)
# ---------------------------------------------------------------------------

class _TokenBucket:
    """Thread-safe token bucket — refilled at `rate_rps` tokens/second."""

    def __init__(self, rate_rps: float):
        self._rate = max(rate_rps, 0.1)
        self._tokens = self._rate
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
        # Sleep outside the lock for the fractional amount needed
        sleep_for = (1.0 - self._tokens) / self._rate
        time.sleep(sleep_for)
        with self._lock:
            self._tokens = 0.0


# Cache buckets per connection_id so concurrent workers for the same connection share one.
_bucket_registry: Dict[str, _TokenBucket] = {}
_bucket_lock = threading.Lock()


def _get_bucket(connection_id: str, rate_rps: float) -> _TokenBucket:
    with _bucket_lock:
        if connection_id not in _bucket_registry:
            _bucket_registry[connection_id] = _TokenBucket(rate_rps)
        return _bucket_registry[connection_id]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _build_auth_headers(
    connection: IngestionConnection, secret: Optional[str]
) -> Dict[str, str]:
    """Return the auth headers/params for this connection."""
    auth_type = connection.auth_type
    cfg = connection.auth_config or {}
    headers: Dict[str, str] = {}

    if auth_type == "api_key_header":
        header_name = cfg.get("header_name", "X-API-Key")
        headers[header_name] = secret or ""
    elif auth_type == "bearer_token":
        headers["Authorization"] = f"Bearer {secret or ''}"
    elif auth_type == "basic_auth":
        import base64
        username = cfg.get("username", "")
        cred = base64.b64encode(f"{username}:{secret or ''}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
    # api_key_query and none are handled at request-build time
    return headers


def _build_auth_params(
    connection: IngestionConnection, secret: Optional[str]
) -> Dict[str, str]:
    if connection.auth_type == "api_key_query":
        param_name = (connection.auth_config or {}).get("param_name", "api_key")
        return {param_name: secret or ""}
    return {}


def _backoff_sleep(attempt: int, retry_after: Optional[float] = None) -> None:
    if retry_after is not None:
        time.sleep(min(retry_after, BACKOFF_MAX))
        return
    delay = min(BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1), BACKOFF_MAX)
    time.sleep(delay)


def _http_get_with_retry(
    session: requests.Session,
    url: str,
    headers: Dict[str, str],
    params: Dict[str, Any],
    json_body: Optional[Dict],
    method: str,
    bucket: _TokenBucket,
) -> Tuple[int, Any]:
    """
    Execute one HTTP call with retry logic per spec §10.
    Returns (status_code, response_json_or_text).
    Raises RuntimeError on unrecoverable failure.
    """
    attempts_5xx = 0
    attempts_429 = 0

    while True:
        bucket.acquire()
        try:
            if method.upper() == "POST":
                resp = session.post(url, headers=headers, params=params, json=json_body, timeout=30)
            else:
                resp = session.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Network error: {exc}") from exc

        status = resp.status_code

        if status == 200:
            try:
                return status, resp.json()
            except Exception:
                return status, resp.text

        if status == 429:
            attempts_429 += 1
            if attempts_429 > MAX_ATTEMPTS_429:
                raise RuntimeError(f"HTTP 429 rate-limited after {MAX_ATTEMPTS_429} retries")
            retry_after = None
            try:
                retry_after = float(resp.headers.get("Retry-After", ""))
            except (TypeError, ValueError):
                pass
            logger.warning("HTTP 429 — backoff attempt %d", attempts_429)
            _backoff_sleep(attempts_429, retry_after)
            continue

        if status >= 500:
            attempts_5xx += 1
            if attempts_5xx > MAX_ATTEMPTS_5XX:
                body = resp.text[:500]
                raise RuntimeError(f"HTTP {status} after {MAX_ATTEMPTS_5XX} retries: {body}")
            logger.warning("HTTP %s — backoff attempt %d", status, attempts_5xx)
            _backoff_sleep(attempts_5xx)
            continue

        # 4xx (other than 429) — no retry
        body = resp.text[:500]
        raise RuntimeError(f"HTTP {status}: {body}")


# ---------------------------------------------------------------------------
# Blob storage helpers (uses app.storage if available, local-file fallback)
# ---------------------------------------------------------------------------

def _write_bronze(workspace_id: str, job_config_id: str, param_value: str, run_id: str,
                  page: int, data: Any) -> Tuple[str, int]:
    """
    Write a single page of raw API response to bronze storage.
    Returns (blob_path, byte_count).
    Path: compassx-bronze/<workspace_id>/ingestion/<job_config_id>/<param_value>/<run_id>/page_<n>.json
    """
    content = json.dumps(data, ensure_ascii=False).encode("utf-8")
    blob_path = (
        f"{workspace_id}/ingestion/{job_config_id}/{param_value}/{run_id}/page_{page}.json"
    )
    bucket = "compassx-bronze"

    try:
        from app.storage.backend import get_default_backend
        backend = get_default_backend()
        backend.put_object(bucket, blob_path, BytesIO(content), length=len(content))
    except Exception:
        # Local-file fallback for dev environments without object storage
        local_root = os.path.join(os.environ.get("BRONZE_LOCAL_ROOT", "/tmp/bronze"), bucket)
        local_path = os.path.join(local_root, blob_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(content)
        logger.debug("Bronze written (local fallback): %s", local_path)

    return f"cx://{bucket}/{blob_path}", len(content)


def _write_manifest(workspace_id: str, job_config_id: str, param_value: str,
                    run_id: str, pages: List[dict], cursor_value: Optional[str]) -> None:
    manifest = {
        "job_config_id": job_config_id,
        "param_value": param_value,
        "run_id": run_id,
        "pages": pages,
        "cursor_value": cursor_value,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    content = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    blob_path = f"{workspace_id}/ingestion/{job_config_id}/{param_value}/{run_id}/_manifest.json"
    bucket = "compassx-bronze"

    try:
        from app.storage.backend import get_default_backend
        backend = get_default_backend()
        backend.put_object(bucket, blob_path, BytesIO(content), length=len(content))
    except Exception:
        local_root = os.path.join(os.environ.get("BRONZE_LOCAL_ROOT", "/tmp/bronze"), bucket)
        local_path = os.path.join(local_root, blob_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(content)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_template(template: str, param_value: str, cursor: Optional[str]) -> str:
    return (
        template
        .replace("{param_value}", param_value)
        .replace("{asset_id}", param_value)
        .replace("{cursor}", cursor or "")
    )


def _render_dict_template(
    template: Dict[str, Any], param_value: str, cursor: Optional[str]
) -> Dict[str, Any]:
    rendered = {}
    for k, v in template.items():
        if isinstance(v, str):
            rendered[k] = _render_template(v, param_value, cursor)
        else:
            rendered[k] = v
    return rendered


# ---------------------------------------------------------------------------
# JSONPath extraction
# ---------------------------------------------------------------------------

def _extract_jsonpath(data: Any, path: str) -> Optional[str]:
    """Extract a scalar value from `data` using a JSONPath expression."""
    try:
        expr = jsonpath_parse(path)
        matches = [m.value for m in expr.find(data)]
        if matches:
            return str(matches[-1])
    except Exception as exc:
        logger.warning("JSONPath extraction failed (path=%s): %s", path, exc)
    return None


# ---------------------------------------------------------------------------
# Param value resolution
# ---------------------------------------------------------------------------

def resolve_param_values(
    db: Session,
    job_config: IngestionJobConfig,
    connection: IngestionConnection,
    secret: Optional[str],
) -> List[str]:
    """
    Resolve the list of param values to fan out over.
    Handles: static | catalog_query | parent_api
    """
    ptype = job_config.param_source_type
    pcfg = job_config.param_source_config or {}

    if ptype == "static":
        vals = pcfg.get("values", [])
        if not vals:
            return [NONE_SENTINEL]
        return [str(v) for v in vals]

    if ptype == "catalog_query":
        # Call the catalog service to resolve asset values
        try:
            from app.catalog.services import query_catalog_values  # type: ignore
            results = query_catalog_values(
                db,
                object_type=pcfg.get("catalog_object_type", "asset"),
                filters=pcfg.get("filter", {}),
                value_field=pcfg.get("value_field", "external_id"),
            )
            return results or [NONE_SENTINEL]
        except ImportError:
            logger.warning("catalog_query param source: catalog service not available, returning __none__")
            return [NONE_SENTINEL]

    if ptype == "parent_api":
        # Call the parent endpoint to get a list of param values
        parent_path = pcfg.get("path_template", "")
        list_path = pcfg.get("response_list_path", "$[*]")
        value_field = pcfg.get("value_field", "id")

        url = connection.base_url.rstrip("/") + "/" + parent_path.lstrip("/")
        auth_headers = _build_auth_headers(connection, secret)
        auth_headers.update(dict(connection.default_headers or {}))
        auth_params = _build_auth_params(connection, secret)

        bucket = _get_bucket(str(connection.id), float(connection.rate_limit_rps))
        sess = requests.Session()
        try:
            _, data = _http_get_with_retry(
                sess, url, auth_headers, auth_params, None, "GET", bucket
            )
            # Extract the list
            list_expr = jsonpath_parse(list_path)
            items = [m.value for m in list_expr.find(data)]
            values = []
            for item in items:
                if isinstance(item, dict):
                    values.append(str(item.get(value_field, "")))
                else:
                    values.append(str(item))
            return values or [NONE_SENTINEL]
        except Exception as exc:
            logger.error("parent_api param resolution failed: %s", exc)
            return [NONE_SENTINEL]

    logger.warning("Unknown param_source_type=%s, defaulting to __none__", ptype)
    return [NONE_SENTINEL]


# ---------------------------------------------------------------------------
# Single-param executor
# ---------------------------------------------------------------------------

def execute_single_param(
    db: Session,
    job_config: IngestionJobConfig,
    connection: IngestionConnection,
    secret: Optional[str],
    param_value: str,
    run_id: UUID,
) -> IngestionRunItem:
    """
    Fetch all pages for one param value and write to bronze.
    Returns a populated (but not yet committed) IngestionRunItem.
    """
    item_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    workspace_id = str(job_config.workspace_id)
    job_config_id = str(job_config.id)
    run_id_str = str(run_id)

    # Look up current watermark cursor
    wm = get_watermark(db, job_config.id, param_value)
    cursor = wm.cursor_value if wm else None

    auth_headers = _build_auth_headers(connection, secret)
    auth_headers.update(dict(connection.default_headers or {}))
    auth_params = _build_auth_params(connection, secret)

    bucket = _get_bucket(str(connection.id), float(connection.rate_limit_rps))
    sess = requests.Session()

    pages_fetched = 0
    rows_landed = 0
    bytes_landed = 0
    page_manifest: List[dict] = []
    new_cursor: Optional[str] = cursor
    first_bronze_path: Optional[str] = None
    error_message: Optional[str] = None

    try:
        pagination_type = job_config.pagination_type
        pagination_config = job_config.pagination_config or {}
        page_size = pagination_config.get("page_size", 100)
        offset = 0
        page_num = 0
        has_more = True

        while has_more and pages_fetched < MAX_PAGES_DEFAULT:
            # Build URL and params
            path = _render_template(job_config.path_template, param_value, cursor)
            url = connection.base_url.rstrip("/") + "/" + path.lstrip("/")

            req_params = dict(auth_params)
            req_params.update(_render_dict_template(job_config.query_template or {}, param_value, cursor))

            # Inject cursor into the cursor query param if configured
            if cursor and job_config.cursor_query_param:
                req_params[job_config.cursor_query_param] = cursor

            # Pagination-specific param injection
            if pagination_type == "offset":
                offset_param = pagination_config.get("offset_param", "offset")
                limit_param = pagination_config.get("limit_param", "limit")
                req_params[offset_param] = offset
                req_params[limit_param] = page_size

            elif pagination_type == "page":
                page_param = pagination_config.get("page_param", "page")
                size_param = pagination_config.get("size_param", "page_size")
                req_params[page_param] = page_num
                req_params[size_param] = page_size

            body = None
            if job_config.http_method == "POST" and job_config.body_template:
                body = _render_dict_template(job_config.body_template, param_value, cursor)

            # Execute HTTP request
            _, data = _http_get_with_retry(
                sess, url, auth_headers, req_params, body,
                job_config.http_method, bucket
            )

            # Write page to bronze
            blob_path, byte_count = _write_bronze(
                workspace_id, job_config_id, param_value, run_id_str, pages_fetched, data
            )
            if first_bronze_path is None:
                first_bronze_path = blob_path

            # Count rows (if data is a list or has a list inside)
            page_rows = len(data) if isinstance(data, list) else 1

            page_manifest.append({
                "page": pages_fetched,
                "blob_path": blob_path,
                "rows": page_rows,
                "bytes": byte_count,
            })
            pages_fetched += 1
            rows_landed += page_rows
            bytes_landed += byte_count

            # Extract new cursor from last page
            if job_config.cursor_field_path:
                extracted = _extract_jsonpath(data, job_config.cursor_field_path)
                if extracted:
                    new_cursor = extracted

            # Determine if more pages exist
            if pagination_type == "none":
                has_more = False

            elif pagination_type == "offset":
                # Stop when page returned fewer rows than page_size
                has_more = page_rows >= page_size
                offset += page_rows

            elif pagination_type == "page":
                has_more = page_rows >= page_size
                page_num += 1

            elif pagination_type == "cursor_field":
                next_path = pagination_config.get("next_cursor_path")
                if next_path:
                    next_val = _extract_jsonpath(data, next_path)
                    has_more = bool(next_val)
                    if next_val:
                        cursor = next_val
                else:
                    has_more = False

        # Write manifest
        _write_manifest(workspace_id, job_config_id, param_value, run_id_str, page_manifest, new_cursor)

        # Advance watermark on success (D8)
        advance_watermark(db, job_config.id, param_value, new_cursor, run_id)

        return IngestionRunItem(
            id=item_id,
            run_id=run_id,
            param_value=param_value,
            status="succeeded",
            pages_fetched=pages_fetched,
            rows_landed=rows_landed,
            bytes_landed=bytes_landed,
            bronze_path=first_bronze_path,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    except Exception as exc:
        logger.error(
            "execute_single_param failed: job_config=%s param=%s: %s",
            job_config_id, param_value, exc, exc_info=True,
        )
        return IngestionRunItem(
            id=item_id,
            run_id=run_id,
            param_value=param_value,
            status="failed",
            pages_fetched=pages_fetched,
            rows_landed=rows_landed,
            bytes_landed=bytes_landed,
            bronze_path=first_bronze_path,
            error_message=str(exc)[:1000],
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Top-level run orchestrator
# ---------------------------------------------------------------------------

def execute_run(
    db: Session,
    job_config_id: UUID,
    workspace_id: UUID,
    airflow_dag_run_id: Optional[str] = None,
) -> IngestionRun:
    """
    Orchestrate a full ingestion run for one job config.
    Called by the /trigger API endpoint or the Airflow task.
    """
    from app.ingestion.job_configs import get_job_config
    from app.ingestion.connections import resolve_secret

    cfg = get_job_config(db, workspace_id, job_config_id)
    conn = cfg.connection
    secret = resolve_secret(db, conn)

    # Create run record
    run = IngestionRun(
        id=uuid.uuid4(),
        job_config_id=job_config_id,
        airflow_dag_run_id=airflow_dag_run_id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id

    # Resolve param values
    param_values = resolve_param_values(db, cfg, conn, secret)
    total_params = len(param_values)

    # Fan-out with bounded concurrency (D10)
    max_workers = min(conn.max_concurrency, total_params) or 1
    items: List[IngestionRunItem] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                execute_single_param, db, cfg, conn, secret, pv, run_id
            ): pv
            for pv in param_values
        }
        for future in as_completed(futures):
            item = future.result()
            db.add(item)
            items.append(item)

    db.commit()

    # Aggregate results
    succeeded = sum(1 for i in items if i.status == "succeeded")
    failed = sum(1 for i in items if i.status == "failed")

    if failed == 0:
        final_status = "succeeded"
    elif succeeded == 0:
        final_status = "failed"
    else:
        final_status = "partial"

    run.status = final_status
    run.finished_at = datetime.now(timezone.utc)
    run.total_params = total_params
    run.succeeded_params = succeeded
    run.failed_params = failed
    run.total_rows_landed = sum(i.rows_landed for i in items)
    run.total_bytes_landed = sum(i.bytes_landed for i in items)
    if failed > 0:
        errors = [i.error_message for i in items if i.error_message]
        run.error_summary = "; ".join(errors[:3])

    db.commit()
    db.refresh(run)
    logger.info(
        "Run %s finished: status=%s params=%d succeeded=%d failed=%d",
        run_id, final_status, total_params, succeeded, failed,
    )
    return run
