# Catalog

Product module. Unified metadata for catalogs, schemas, tables, volumes, lineage, promoted tools, and the catalog copies of notebooks, dashboards, and queries.

The public HTTP router is still `app.catalog.routes.router` at `/api/v1/catalog`. The public Python functions are still imported from `app.catalog.service`. Both are facades. Each service function constructs one application type and calls it. Callers do not change.

## Code

- `backend/app/catalog/routes.py` — HTTP edge. Handlers check governance, call a service function, and map `ValueError` to HTTP 400.
- `backend/app/catalog/service.py` — facade. Same function names as before, including the private notebook content helpers other modules import.
- `backend/app/catalog/composition.py` — builds the log, search index, and Postgres reader ports.
- `backend/app/catalog/models.py` and `schemas.py` — the existing ORM models and request models. There is no second domain model.
- `backend/app/catalog/<resource>/application/` — one application type per action.
- `backend/app/catalog/tables/repository.py` and `schema/repository.py` — shared SQLAlchemy lookups and column replacement.
- `backend/app/catalog/infrastructure/` — Iceberg, volumes, search indexing, embeddings, storage context, and Z-order. The old import paths (`app.catalog.iceberg_manager`, `app.catalog.search_indexer`, and the others) are shims.
- `backend/app/catalog/connections/` — left in place.
- `backend/app/catalog/tool_routes.py`, `tool_service.py`, and `tools.py` — promoted tools, and the built-in `catalog` agent tool. These files stay at those import paths.
- Catalog UI in `frontend/src/modules/data`.

## Owns

Catalog, schema, table, column, volume, lineage, notebook, dashboard, query, tool, and connection rows. Search-index rows and embedding jobs. Iceberg metadata files written through the storage backend.

## Calls

Storage for volume and notebook bytes. Governance on the HTTP edge, before a write. Workspace bindings. The search indexer. A Postgres connection when the catalog type is `postgres` or a table is foreign. Notebooks, dashboards, jobs, and Nova call back into this module through `app.catalog.service` and the models.

## How an action runs

`add_table` in `routes.py` requires `CREATE` on the schema, then calls `create_table`. That function builds `CreateTable` with the search index and the catalog log from `composition.py`. `CreateTable.execute` checks the catalog and schema, refuses a duplicate name, inserts the `UnifiedCatalogTable` row, commits, then asks the search index to enqueue an embedding. If enqueue fails, the table row stays and the log writes `Failed to enqueue embedding for table %s: %s` at warning, on the logger `app.catalog.service`.

The same shape is used for volumes, notebooks, dashboards, queries, and Iceberg tables. Delete of a dashboard or a query goes through `SearchIndex.delete` before the row is removed.

## Topics

- [Catalogs and schemas](catalogs.md)
- [Tables](tables.md)
- [Volumes](volumes.md)
- [Notebooks, dashboards, and queries](assets.md)
- [Search](search.md)
- [Tools](tools.md)

## Test cases

[Test cases](test-cases.md) are the end-to-end checks for this module.

## Later split

Other modules still import these functions and, in places, private helpers such as `_read_notebook_content`. Those calls become a port before Catalog moves to its own process. Do not merge the legacy data catalog into this module.
