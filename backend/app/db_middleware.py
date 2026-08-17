"""Middleware and utilities for handling database unavailability."""

from functools import wraps
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
import logging

logger = logging.getLogger(__name__)


def handle_db_errors(func):
    """Decorator to catch database errors and return 503 Service Unavailable."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except RuntimeError as e:
            if "database not available" in str(e).lower():
                logger.warning("Database not available: %s", e)
                raise HTTPException(
                    status_code=503,
                    detail="Database service temporarily unavailable. This feature requires database connectivity."
                )
            raise
        except OperationalError as e:
            logger.error("Database operational error: %s", e)
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable. Please try again later."
            )

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            if "database not available" in str(e).lower():
                logger.warning("Database not available: %s", e)
                raise HTTPException(
                    status_code=503,
                    detail="Database service temporarily unavailable. This feature requires database connectivity."
                )
            raise
        except OperationalError as e:
            logger.error("Database operational error: %s", e)
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable. Please try again later."
            )

    # Return async wrapper if coroutine, else sync
    if hasattr(func, '__code__') and 'async' in str(func.__code__):
        return async_wrapper
    return sync_wrapper
