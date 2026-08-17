"""Security helpers for Airflow callbacks and task execution tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from services.airflow.config import airflow_settings


def verify_airflow_signature(body: bytes, signature: str | None) -> None:
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Airflow signature")
    expected = hmac.new(
        airflow_settings.AIRFLOW_CALLBACK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid Airflow signature")


def verify_internal_secret(value: str | None) -> None:
    expected = airflow_settings.AIRFLOW_CALLBACK_SECRET
    if not value or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="Invalid internal credential")


def generate_execution_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_execution_token(raw)


def hash_execution_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
