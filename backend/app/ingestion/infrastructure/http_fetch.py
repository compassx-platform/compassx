"""One HTTP call with the ingestion retry rules."""
from __future__ import annotations

import base64
import random
import time
from typing import Any, Dict, Optional, Tuple

import requests

from app.ingestion.composition import execution_logger
from app.ingestion.infrastructure.http_policy import (
    BACKOFF_BASE,
    BACKOFF_MAX,
    MAX_ATTEMPTS_429,
    MAX_ATTEMPTS_5XX,
)
from app.ingestion.infrastructure.rate_limit import _TokenBucket
from app.ingestion.models import IngestionConnection

logger = execution_logger()


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
