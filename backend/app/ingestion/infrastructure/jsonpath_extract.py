"""JSONPath read used for cursors and parent-api lists."""
from __future__ import annotations

from typing import Any, Optional

from jsonpath_ng.ext import parse as jsonpath_parse

from app.ingestion.composition import execution_logger

logger = execution_logger()


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
