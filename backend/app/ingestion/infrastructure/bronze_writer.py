"""Bronze page and manifest writes. Object storage, then a local file."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, List, Optional, Tuple

from app.ingestion.composition import execution_logger

logger = execution_logger()


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
