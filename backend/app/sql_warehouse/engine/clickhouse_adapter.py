import asyncio
import time

from .adapter_base import EngineAdapter, QueryResult


class ClickHouseAdapter(EngineAdapter):
    def __init__(self, host: str = "localhost", port: int = 8123, user: str = "default", password: str = "", database: str = "default", **_: object):
        self._client_kwargs = dict(host=host, port=port, user=user, password=password, database=database)

    def _get_client(self):
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError("ClickHouse driver is not installed. Install clickhouse-connect to run ClickHouse warehouses.") from exc
        return clickhouse_connect.get_client(**self._client_kwargs)

    async def execute(
        self,
        sql: str,
        query_id: str,
        timeout_sec: int,
        max_threads: int | None,
        max_memory_mb: int | None,
        setup_sql: list[str] | None = None,
    ) -> QueryResult:
        del setup_sql
        settings = {"query_id": query_id, "max_execution_time": timeout_sec}
        if max_threads:
            settings["max_threads"] = max_threads
        if max_memory_mb:
            settings["max_memory_usage"] = max_memory_mb * 1024 * 1024
        start = time.monotonic()

        def _run():
            return self._get_client().query(sql, settings=settings)

        result = await asyncio.to_thread(_run)
        return QueryResult(
            columns=list(result.column_names),
            rows=[list(r) for r in result.result_rows],
            rows_returned=len(result.result_rows),
            bytes_scanned=int((result.summary or {}).get("read_bytes", 0)),
            duration_ms=int((time.monotonic() - start) * 1000),
            engine_query_id=query_id,
        )

    async def cancel(self, engine_query_id: str) -> None:
        await asyncio.to_thread(lambda: self._get_client().command(f"KILL QUERY WHERE query_id = '{engine_query_id}'"))

    async def explain(self, sql: str) -> str:
        def _run():
            result = self._get_client().query(f"EXPLAIN {sql}")
            return "\n".join(str(r[0]) for r in result.result_rows)

        return await asyncio.to_thread(_run)

    async def health_check(self) -> bool:
        try:
            return bool(await asyncio.to_thread(lambda: self._get_client().ping()))
        except Exception:
            return False

