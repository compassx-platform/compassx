"""
Watermark service — tracks incremental cursor state per (job_config, param_value).

Per spec D6 and D8:
  - Watermark lives in ingestion_watermark, keyed by (job_config_id, param_value).
  - '__none__' is the sentinel param_value for non-parameterised jobs.
  - Watermark only advances on full per-param success (at-least-once semantics).

Public names stay importable from ``app.ingestion.watermarks``.
"""
from __future__ import annotations

import logging

from app.ingestion.watermark.application.advance_watermark import advance_watermark
from app.ingestion.watermark.application.get_watermark import get_watermark
from app.ingestion.watermark.application.reset_watermark import reset_watermark
from app.ingestion.watermark.constants import NONE_SENTINEL

logger = logging.getLogger(__name__)

__all__ = ["NONE_SENTINEL", "get_watermark", "advance_watermark", "reset_watermark"]
