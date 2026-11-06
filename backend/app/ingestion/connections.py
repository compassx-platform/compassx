"""
Connection service layer — CRUD for ingestion_connection and credential_secret.

Security rules (from spec D9):
  - Credentials are resolved server-side at execution time only.
  - Raw secret values are never returned, stored in plaintext, or logged.
  - The GET response contains `has_secret=True/False`, not the secret itself.

Public names stay importable from ``app.ingestion.connections``.
"""
from __future__ import annotations

import logging

from app.ingestion.connection.application.create_connection import create_connection
from app.ingestion.connection.application.delete_connection import delete_connection
from app.ingestion.connection.application.get_connection import get_connection
from app.ingestion.connection.application.list_connections import list_connections
from app.ingestion.connection.application.resolve_secret import resolve_secret
from app.ingestion.connection.application.rotate_connection_secret import rotate_connection_secret
from app.ingestion.connection.application.update_connection import update_connection
from app.ingestion.infrastructure.secret_box import _decrypt, _encrypt, _get_fernet

logger = logging.getLogger(__name__)

__all__ = [
    "create_connection",
    "get_connection",
    "list_connections",
    "update_connection",
    "rotate_connection_secret",
    "delete_connection",
    "resolve_secret",
    "_get_fernet",
    "_encrypt",
    "_decrypt",
]
