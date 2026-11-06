"""
Generic REST executor for Pull-Based API Ingestion.

Public names stay importable from ``app.ingestion.execution``.
Each action forwards to one application type. Helpers keep the same names.
"""
from __future__ import annotations

import logging

from app.ingestion.infrastructure.bronze_writer import _write_bronze, _write_manifest
from app.ingestion.infrastructure.http_fetch import (
    _backoff_sleep,
    _build_auth_headers,
    _build_auth_params,
    _http_get_with_retry,
)
from app.ingestion.infrastructure.http_policy import (
    BACKOFF_BASE,
    BACKOFF_MAX,
    MAX_ATTEMPTS_429,
    MAX_ATTEMPTS_5XX,
    MAX_PAGES_DEFAULT,
)
from app.ingestion.infrastructure.jsonpath_extract import _extract_jsonpath
from app.ingestion.infrastructure.rate_limit import (
    _TokenBucket,
    _bucket_lock,
    _bucket_registry,
    _get_bucket,
)
from app.ingestion.infrastructure.templates import _render_dict_template, _render_template
from app.ingestion.run.application.execute_run import execute_run
from app.ingestion.run.application.execute_single_param import execute_single_param
from app.ingestion.run.application.resolve_param_values import resolve_param_values

logger = logging.getLogger(__name__)

__all__ = [
    "execute_run",
    "execute_single_param",
    "resolve_param_values",
    "_TokenBucket",
    "_get_bucket",
    "_bucket_registry",
    "_bucket_lock",
    "_build_auth_headers",
    "_build_auth_params",
    "_backoff_sleep",
    "_http_get_with_retry",
    "_write_bronze",
    "_write_manifest",
    "_render_template",
    "_render_dict_template",
    "_extract_jsonpath",
    "MAX_PAGES_DEFAULT",
    "BACKOFF_BASE",
    "BACKOFF_MAX",
    "MAX_ATTEMPTS_429",
    "MAX_ATTEMPTS_5XX",
]
