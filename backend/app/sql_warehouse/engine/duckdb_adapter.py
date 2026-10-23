import asyncio
import logging
import os
import time
from urllib.parse import urlparse

import httpx

from .adapter_base import EngineAdapter, QueryResult

logger = logging.getLogger(__name__)


class DuckDBAdapter(EngineAdapter):
    def __init__(self, database: str = ":memory:", endpoint_url: str | None = None, **_: object):
        self._database = database
        self._endpoint_url = endpoint_url

    async def execute(
        self,
        sql: str,
        query_id: str,
        timeout_sec: int,
        max_threads: int | None,
        max_memory_mb: int | None,
        setup_sql: list[str] | None = None,
    ) -> QueryResult:
        start = time.monotonic()

        # If endpoint_url is configured, dispatch to remote warehouse pod
        if self._endpoint_url:
            secret = os.environ.get("COMPASSX_INTERNAL_SECRET", "")
            headers = {"X-Compassx-Internal-Secret": secret}
            payload = {
                "query_id": query_id,
                "sql": sql,
                "setup_sql": setup_sql,
                "timeout_sec": timeout_sec,
                "max_threads": max_threads,
                "max_memory_mb": max_memory_mb,
            }
            try:
                async with httpx.AsyncClient(timeout=float(timeout_sec) + 10.0) as client:
                    resp = await client.post(
                        f"{self._endpoint_url.rstrip('/')}/v1/query",
                        json=payload,
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        error_detail = (
                            resp.json().get("detail", resp.text)
                            if resp.headers.get("content-type", "").startswith("application/json")
                            else resp.text
                        )
                        raise RuntimeError(error_detail)
                    data = resp.json()
                    return QueryResult(
                        columns=data.get("columns", []),
                        rows=data.get("rows", []),
                        rows_returned=data.get("rows_returned", 0),
                        bytes_scanned=data.get("bytes_scanned", 0),
                        duration_ms=data.get("duration_ms", int((time.monotonic() - start) * 1000)),
                        query_analysis=data.get("query_analysis"),
                        engine_query_id=query_id,
                    )
            except (httpx.ConnectError, httpx.ConnectTimeout) as net_err:
                logger.warning(
                    "Cannot reach remote DuckDB warehouse pod at %s (%s). Falling back to in-process execution.",
                    self._endpoint_url,
                    net_err,
                )

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
        if self._endpoint_url:
            try:
                secret = os.environ.get("COMPASSX_INTERNAL_SECRET", "")
                headers = {"X-Compassx-Internal-Secret": secret}
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{self._endpoint_url.rstrip('/')}/v1/cancel/{engine_query_id}",
                        headers=headers,
                    )
            except Exception:
                pass

    async def explain(self, sql: str) -> str:
        if self._endpoint_url:
            try:
                secret = os.environ.get("COMPASSX_INTERNAL_SECRET", "")
                headers = {"X-Compassx-Internal-Secret": secret}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{self._endpoint_url.rstrip('/')}/v1/explain",
                        json={"sql": sql},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        return resp.json().get("explanation", "")
                    error_detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                    raise RuntimeError(f"Explain failed: {error_detail}")
            except Exception as exc:
                if "Explain failed" in str(exc):
                    raise
                logger.warning("Remote explain failed: %s, falling back to local DuckDB", exc)

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
        if self._endpoint_url:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{self._endpoint_url.rstrip('/')}/healthz")
                    return resp.status_code == 200
            except Exception:
                return False
        return True
