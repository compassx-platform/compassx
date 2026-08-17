import asyncio
import time

from sqlalchemy import create_engine, text

from .adapter_base import EngineAdapter, QueryResult


class PostgresAdapter(EngineAdapter):
    def __init__(self, dsn: str | None = None, **_: object):
        if not dsn:
            raise ValueError("Postgres warehouse config requires a dsn value.")
        self._dsn = dsn

    async def execute(
        self,
        sql: str,
        query_id: str,
        timeout_sec: int,
        max_threads: int | None,
        max_memory_mb: int | None,
        setup_sql: list[str] | None = None,
    ) -> QueryResult:
        del query_id, max_threads, max_memory_mb
        if setup_sql:
            raise ValueError("setup_sql is only supported by the DuckDB warehouse adapter.")
        start = time.monotonic()

        def _run():
            engine = create_engine(self._dsn, connect_args={"connect_timeout": min(timeout_sec, 30)})
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                if not result.returns_rows:
                    conn.commit()
                    return [], []
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                return columns, rows

        columns, rows = await asyncio.to_thread(_run)
        return QueryResult(columns=columns, rows=rows, rows_returned=len(rows), bytes_scanned=0, duration_ms=int((time.monotonic() - start) * 1000))

    async def cancel(self, engine_query_id: str) -> None:
        del engine_query_id

    async def explain(self, sql: str) -> str:
        result = await self.execute(f"EXPLAIN {sql}", "explain", 300, None, None)
        return "\n".join(" ".join(str(c) for c in row) for row in result.rows)

    async def health_check(self) -> bool:
        try:
            await self.execute("SELECT 1", "health", 30, None, None)
            return True
        except Exception:
            return False

