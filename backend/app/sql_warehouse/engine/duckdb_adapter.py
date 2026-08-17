import asyncio
import time

from .adapter_base import EngineAdapter, QueryResult


class DuckDBAdapter(EngineAdapter):
    def __init__(self, database: str = ":memory:", **_: object):
        self._database = database

    async def execute(
        self,
        sql: str,
        query_id: str,
        timeout_sec: int,
        max_threads: int | None,
        max_memory_mb: int | None,
        setup_sql: list[str] | None = None,
    ) -> QueryResult:
        del query_id, timeout_sec
        start = time.monotonic()

        def _run():
            try:
                import duckdb
            except ImportError as exc:
                raise RuntimeError("DuckDB driver is not installed. Install duckdb to run DuckDB warehouses.") from exc
            import tempfile
            import os
            import json

            conn = duckdb.connect(self._database)
            profile_path = None
            query_analysis = None
            try:
                if max_threads:
                    conn.execute(f"SET threads TO {int(max_threads)}")
                if max_memory_mb:
                    conn.execute(f"SET memory_limit = '{int(max_memory_mb)}MB'")
                for statement in setup_sql or []:
                    conn.execute(statement)

                try:
                    profile_fd, profile_path = tempfile.mkstemp(suffix=".json")
                    os.close(profile_fd)
                    conn.execute("PRAGMA enable_profiling = 'json';")
                    conn.execute(f"PRAGMA profiling_output = '{profile_path}';")
                except Exception:
                    profile_path = None

                rel = conn.execute(sql)
                columns = [d[0] for d in (rel.description or [])]
                rows = rel.fetchall() if columns else []

                if profile_path:
                    try:
                        conn.execute("PRAGMA disable_profiling;")
                        if os.path.exists(profile_path):
                            with open(profile_path, "r", encoding="utf-8") as f:
                                query_analysis = json.load(f)
                    except Exception:
                        pass

                return columns, [list(r) for r in rows], query_analysis
            finally:
                try:
                    if profile_path and os.path.exists(profile_path):
                        os.remove(profile_path)
                except Exception:
                    pass
                conn.close()

        columns, rows, query_analysis = await asyncio.to_thread(_run)
        return QueryResult(
            columns=columns,
            rows=rows,
            rows_returned=len(rows),
            bytes_scanned=0,
            duration_ms=int((time.monotonic() - start) * 1000),
            query_analysis=query_analysis,
        )

    async def cancel(self, engine_query_id: str) -> None:
        del engine_query_id

    async def explain(self, sql: str) -> str:
        def _run():
            try:
                import duckdb
            except ImportError as exc:
                raise RuntimeError("DuckDB driver is not installed. Install duckdb to explain DuckDB queries.") from exc
            conn = duckdb.connect(self._database)
            try:
                return "\n".join(str(row) for row in conn.execute(f"EXPLAIN {sql}").fetchall())
            finally:
                conn.close()

        return await asyncio.to_thread(_run)

    async def health_check(self) -> bool:
        return True
