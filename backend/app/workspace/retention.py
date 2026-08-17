"""RetentionWorker: nightly background task for data plane partition management.

Per spec section 5 + 9:
- Drop partitions older than retention window
- Create partitions for next 2 months if missing
- Log operations
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Retention in days per table
DATA_PLANE_RETENTION: dict[str, int] = {
    "wp_query_history": 90,
    "wp_agent_run_logs": 180,
    "wp_agent_turn_logs": 180,
    "wp_llm_call_logs": 90,
}

# Partition time column per table
_TIME_COL: dict[str, str] = {
    "wp_query_history": "started_at",
    "wp_agent_run_logs": "started_at",
    "wp_agent_turn_logs": "created_at",
    "wp_llm_call_logs": "called_at",
}


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _partition_name(table: str, year: int, month: int) -> str:
    return f"{table}_{year:04d}_{month:02d}"


class RetentionWorker:
    """Manages partitions for data plane tables.

    Call `run_once()` to perform one maintenance cycle.
    Call `start()` to run nightly as a background asyncio task.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("RetentionWorker started")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                logger.exception("RetentionWorker error")
            # Sleep ~24h
            await asyncio.sleep(86400)

    def run_once(self) -> None:
        from app.database import SystemSessionLocal
        if SystemSessionLocal is None:
            logger.debug("RetentionWorker: data DB not configured, skipping")
            return

        db = SystemSessionLocal()
        try:
            today = date.today()
            for table, retention_days in DATA_PLANE_RETENTION.items():
                self._drop_old_partitions(db, table, today, retention_days)
                self._ensure_future_partitions(db, table, today, months_ahead=2)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("RetentionWorker: maintenance failed")
        finally:
            db.close()

    def _drop_old_partitions(
        self, db, table: str, today: date, retention_days: int
    ) -> None:
        cutoff = today - timedelta(days=retention_days)
        # Walk backwards from 3 years ago to cutoff month
        check_year = today.year - 3
        check_month = 1
        while True:
            partition_start, partition_end = _month_range(check_year, check_month)
            if partition_start > cutoff:
                break
            if partition_end <= cutoff:
                name = _partition_name(table, check_year, check_month)
                try:
                    db.execute(
                        __import__("sqlalchemy").text(f"DROP TABLE IF EXISTS {name}")
                    )
                    logger.info("RetentionWorker: dropped partition %s", name)
                except Exception:
                    logger.warning("RetentionWorker: could not drop %s", name)
            # Advance month
            if check_month == 12:
                check_year += 1
                check_month = 1
            else:
                check_month += 1
            if check_year > today.year + 1:
                break

    def _ensure_future_partitions(
        self, db, table: str, today: date, months_ahead: int
    ) -> None:
        import sqlalchemy as sa
        current = today.replace(day=1)
        for i in range(months_ahead + 1):
            year = current.year + (current.month - 1 + i) // 12
            month = (current.month - 1 + i) % 12 + 1
            start, end = _month_range(year, month)
            name = _partition_name(table, year, month)
            try:
                db.execute(sa.text(
                    f"CREATE TABLE IF NOT EXISTS {name} "
                    f"PARTITION OF {table} "
                    f"FOR VALUES FROM ('{start}') TO ('{end}')"
                ))
            except Exception:
                logger.debug("RetentionWorker: partition %s may already exist", name)
