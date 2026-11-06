# SQL warehouse

Product module. A warehouse is a named engine a workspace uses to run SQL. The engine is DuckDB, ClickHouse, or Postgres. The row lives in the system database. A query writes a history row in the same database, and a DuckDB warehouse can attach catalog tables before it runs.

HTTP lives in `app.sql_warehouse.routes`. The router prefix is `/api/v1`. Each handler keeps its name and forwards to one application type. Warehouse lookups stay importable from `app.sql_warehouse.warehouse.manager`. `QueryExecutor` stays importable from `app.sql_warehouse.query.executor`.

This module does not register a tool. Agents run SQL through the SQL Warehouse tool, key `sql_warehouse`, which Agents registers. That tool is documented with Agents.

## Code

- `backend/app/sql_warehouse/routes.py` — HTTP. Helper names `_resolve_user_and_workspace` and `_record_to_dict` stay importable here and live in `shared/support.py`.
- `backend/app/sql_warehouse/warehouse/application/` — list, create, read, start, stop, set default, delete, and health. `manager.py` forwards the lookup and write names callers already import.
- `backend/app/sql_warehouse/warehouse/pod_orchestrator.py` — starts, stops, and deletes the warehouse container. Its logs use logger `warehouse_orchestrator`.
- `backend/app/sql_warehouse/query/application/` — run, explain, validate, cancel, history, and result.
- `backend/app/sql_warehouse/query/executor.py` — cache, policy, catalog setup, and the engine call. Its logs stay on logger `app.sql_warehouse.query.executor`.
- `backend/app/sql_warehouse/query/query_record.py` — history and active-query rows.
- `backend/app/sql_warehouse/draft/application/` — editor drafts.
- `backend/app/sql_warehouse/catalog/` — the editor's catalog browser, and the DuckDB attach plan.
- `backend/app/sql_warehouse/engine/` — one adapter per engine. `get_adapter` picks it.
- `backend/app/sql_warehouse/models.py` and `schemas.py` — the system-database tables and the request models. There is no second domain model.

## Owns

System database, schema `compute`: `sql_warehouse_warehouses`.

System database, schema `query`: `history`, `active_queries`, and `draft_queries`.

The result cache is an in-process map. It is not a table. Empty results are not kept.

## Calls

`WarehousePodOrchestrator` asks the platform driver for a container. When no driver is available it still returns a runtime id and an endpoint, and logs a warning. DuckDB query setup reads catalog and storage rows to attach Postgres and Iceberg. Governance is not checked on these routes. The signed-in user and the workspace come from the request.

## Topics

- [Warehouses](warehouses.md)
- [Queries](queries.md)
- [Editor](editor.md)
- [Test cases](test-cases.md)
