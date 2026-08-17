import asyncio
import pytest
from sqlalchemy.orm import Session

import app.sql_warehouse.models
from app.sql_warehouse.models import SqlWarehouse, SqlQueryRecord
from app.sql_warehouse.query.executor import QueryExecutor


def test_query_executor_saves_analysis(db_session: Session):
    # 1. Create a dummy Warehouse
    warehouse = SqlWarehouse(
        id="test-wh-123",
        name="Test DuckDB Warehouse",
        description="Testing query analysis",
        engine="duckdb",
        status="running",
        config={},
        resource_policy={},
        created_by="test-user",
    )
    db_session.add(warehouse)
    db_session.commit()

    # 2. Instantiate QueryExecutor
    executor = QueryExecutor(db_session)

    # 3. Run a query in an event loop
    async def _run():
        return await executor.run(
            warehouse=warehouse,
            sql="SELECT 1 AS id, 'hello' AS msg",
            user_id="test-user",
            session_id=None,
            max_rows=100,
        )

    res = asyncio.run(_run())

    # 4. Assert response contains query_analysis
    assert "query_analysis" in res
    analysis = res["query_analysis"]
    assert analysis is not None
    assert "cumulative_cardinality" in analysis
    assert "latency" in analysis

    # 5. Fetch from DB and assert stored correctly
    query_id = res["query_id"]
    record = db_session.query(SqlQueryRecord).filter_by(id=query_id).first()
    assert record is not None
    assert record.status == "succeeded"
    assert record.query_analysis is not None
    assert "cumulative_cardinality" in record.query_analysis
