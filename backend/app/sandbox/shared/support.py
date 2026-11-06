"""Shared sandbox helpers. Logs stay on the service logger."""
import logging
from typing import Optional

logger = logging.getLogger("app.sandbox.service")


def _normalize_key(val: Optional[str]) -> str:
    if not val:
        return ""
    return str(val).strip().lower().replace("_", "-")
