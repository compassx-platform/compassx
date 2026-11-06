"""Fetch every page for one param value and write bronze."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import requests
from sqlalchemy.orm import Session

from app.ingestion.composition import execution_logger
from app.ingestion.infrastructure.bronze_writer import _write_bronze, _write_manifest
from app.ingestion.infrastructure.http_fetch import (
    _build_auth_headers,
    _build_auth_params,
    _http_get_with_retry,
)
from app.ingestion.infrastructure.http_policy import MAX_PAGES_DEFAULT
from app.ingestion.infrastructure.jsonpath_extract import _extract_jsonpath
from app.ingestion.infrastructure.rate_limit import _get_bucket
from app.ingestion.infrastructure.templates import _render_dict_template, _render_template
from app.ingestion.models import IngestionConnection, IngestionJobConfig, IngestionRunItem
from app.ingestion.watermarks import advance_watermark, get_watermark

logger = execution_logger()


class ExecuteSingleParam:
    def execute(
        self,
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
        item_id = uuid4()
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


def execute_single_param(
    db: Session,
    job_config: IngestionJobConfig,
    connection: IngestionConnection,
    secret: Optional[str],
    param_value: str,
    run_id: UUID,
) -> IngestionRunItem:
    return ExecuteSingleParam().execute(db, job_config, connection, secret, param_value, run_id)
