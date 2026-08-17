import hashlib
import logging
import uuid
import time
from datetime import datetime, timezone

from app.sql_warehouse.engine.router import get_adapter
from app.sql_warehouse.catalog.duckdb_resolver import build_duckdb_catalog_plan
from app.sql_warehouse.query.json_values import to_json_value
from app.sql_warehouse.query.query_record import QueryRecordStore
from app.sql_warehouse.query.result_cache import result_cache
from app.sql_warehouse.warehouse.resource_policy import enforce_policy

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self, db, data_db=None):
        self.db = db
        self.data_db = data_db or db
        self.records = QueryRecordStore(self.data_db)
        self.cache = result_cache

    async def run(
        self,
        warehouse,
        sql: str,
        user_id: str,
        session_id: str | None = None,
        max_rows: int = 10000,
        catalog: str | None = None,
        schema_name: str | None = None,
        source: str = "sql_editor",
        dashboard_id: str | None = None,
        dataset_id: str | None = None,
        run_by_user_id: str | None = None,
        run_by_user_name: str | None = None,
    ) -> dict:
        start = time.monotonic()
        sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        enforce_policy(warehouse, self.records)

        # Check cache
        if not session_id:
            cached = await self.cache.get(sql_hash, str(warehouse.id))
            if cached:
                logger.info("query_cache_hit", extra={"sql_hash": sql_hash, "warehouse_id": warehouse.id})
                query_id = str(uuid.uuid4())
                self.records.create(
                    id=query_id,
                    warehouse_id=warehouse.id,
                    user_id=user_id,
                    session_id=session_id,
                    sql_text=sql,
                    sql_hash=sql_hash,
                    status="succeeded",
                    engine=warehouse.engine,
                    source=source,
                    dashboard_id=dashboard_id,
                    dataset_id=dataset_id,
                    run_by_user_id=run_by_user_id,
                    run_by_user_name=run_by_user_name,
                    cache_hit=True,
                    rows_returned=cached.get("rows_returned", 0),
                    duration_ms=0,
                )
                return {**cached, "query_id": query_id, "cache_hit": True}

        query_id = str(uuid.uuid4())
        self.records.create(
            id=query_id,
            warehouse_id=warehouse.id,
            user_id=user_id,
            session_id=session_id,
            sql_text=sql,
            sql_hash=sql_hash,
            status="queued",
            engine=warehouse.engine,
            source=source,
            dashboard_id=dashboard_id,
            dataset_id=dataset_id,
            run_by_user_id=run_by_user_id,
            run_by_user_name=run_by_user_name,
            cache_hit=False,
        )
        self.records.register_active(query_id, warehouse.id, query_id)
        policy = warehouse.resource_policy or {}
        adapter = get_adapter(warehouse)
        self.records.set_status(query_id, "running", started_at=datetime.now(timezone.utc))
        try:
            setup_sql = None
            if warehouse.engine == "duckdb":
                setup_sql = build_duckdb_catalog_plan(self.records.db).setup_sql
                if catalog:
                    if schema_name:
                        setup_sql.append(f'USE "{catalog}"."{schema_name}";')
                    else:
                        setup_sql.append(f'USE "{catalog}";')
            result = await adapter.execute(
                sql=sql,
                query_id=query_id,
                timeout_sec=int(policy.get("query_timeout_sec", 300)),
                max_threads=policy.get("max_threads"),
                max_memory_mb=policy.get("max_memory_mb"),
                setup_sql=setup_sql,
            )
        except Exception as exc:
            self.records.set_status(query_id, "failed", error_message=str(exc), completed_at=datetime.now(timezone.utc))
            self.records.deregister_active(query_id)
            logger.info("query_completed", extra={"query_id": query_id, "warehouse_id": warehouse.id, "user_id": user_id, "engine": warehouse.engine, "status": "failed"})
            raise

        rows = to_json_value(result.rows[:max_rows])
        payload = {
            "columns": result.columns,
            "rows": rows,
            "rows_returned": len(rows),
            "row_count": len(rows),
            "truncated": len(result.rows) > max_rows,
            "bytes_scanned": result.bytes_scanned,
            "duration_ms": result.duration_ms,
            "execution_time_ms": result.duration_ms,
            "query_analysis": result.query_analysis,
        }
        if rows and len(rows) <= 10000:
            await self.cache.set(sql_hash, str(warehouse.id), payload)
        self.records.set_status(
            query_id,
            "succeeded",
            rows_returned=len(rows),
            bytes_scanned=result.bytes_scanned,
            duration_ms=result.duration_ms,
            completed_at=datetime.now(timezone.utc),
            result_payload=payload,
            query_analysis=result.query_analysis,
        )
        self.records.deregister_active(query_id)
        logger.info(
            "query_completed",
            extra={"query_id": query_id, "warehouse_id": warehouse.id, "user_id": user_id, "engine": warehouse.engine, "status": "succeeded", "duration_ms": result.duration_ms, "rows_returned": len(rows), "cache_hit": False},
        )
        return {**payload, "query_id": query_id, "cache_hit": False}
