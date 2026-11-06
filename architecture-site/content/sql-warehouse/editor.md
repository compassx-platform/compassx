# Editor

The editor keeps one person's query tabs, and it lists catalogs so a statement can name a table. Saving a statement into the catalog is a Catalog call, not a call this module owns.

## Drafts

Drafts are rows in `query.draft_queries`, scoped to the user and the workspace. A request with no workspace sees only drafts whose `workspace_id` is null.

`GET /api/v1/sql/drafts` returns that user's drafts, ordered by `tab_order`, then `created_at`.

`POST /api/v1/sql/drafts` accepts `name`, `sql_text`, `catalog`, `schema_name`, and `tab_order`. A blank name becomes `Query {count + 1}`, where the count is that user's drafts in the workspace. The first one is `Query 1`. A later create skips numbers that were deleted, because the name is the count plus one, not the next unused number.

`PUT /api/v1/sql/drafts/{id}` updates the fields that were sent. A blank name is left unchanged. Another user's draft, or a draft in another workspace, is 404 `Draft query not found`.

`DELETE /api/v1/sql/drafts/{id}` uses the same lookup and returns `{ "deleted": true, "id": "..." }`.

## Catalog browser

These routes read the account database. The workspace is taken only from the request workspace.

`GET /api/v1/sql-warehouse/catalog/catalogs` returns `{ "catalogs": [{ "name", "catalog_type" }] }` for catalogs bound to the workspace, plus catalogs marked for every workspace. `catalog_type` falls back to `managed`.

`GET /api/v1/sql-warehouse/catalog/schemas?catalog=default` returns `{ "schemas": [names] }`. The name `default` falls back to the first catalog when no catalog is named `default`. A Postgres catalog with a connection and database lists schemas from that connection. Any other catalog lists `UnifiedCatalogSchema` rows. An unknown catalog returns `{ "schemas": [] }`.

`GET /api/v1/sql-warehouse/catalog/tables?catalog=default&schema=public` follows the same split. Postgres lists connection tables. Other catalogs use Catalog's table list. An unknown catalog returns `{ "tables": [] }`.

`GET /api/v1/sql-warehouse/catalog/columns` requires `table`. Columns are `{ "name", "type", "nullable" }` from Catalog introspection. A missing catalog, schema, or table returns `{ "columns": [] }`.

## Screen

The product screen is `frontend/src/modules/sql_warehouse/SqlWarehousePage.tsx`, under the workspace app.

- `sql-warehouse` redirects to `sql-warehouse/editor`.
- `sql-warehouse/editor` is the editor. The sidebar title is **SQL Editor**. The search box placeholder is `Search queries`. A new tab starts as `SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;`.
- `sql-warehouse/warehouses` heading is **SQL Warehouses**. The button is **Create warehouse**. Search placeholder is `Search warehouses...`. An empty list says `No SQL Warehouses available.` The create dialog title is **Create Warehouse**, with Name, Engine (`DuckDB`, `ClickHouse`, `Postgres`), Description, **Cancel**, and **Create**. Create stays disabled until the name is filled in. A row opens `sql-warehouse/warehouses/{id}/monitoring`, and the page heading is the warehouse name.
- `sql-warehouse/history` heading is **Query History**. An empty filter says `No queries match filters.` Refresh reloads the list.

Saving the current statement into a catalog schema calls `POST /catalog/catalogs/{catalog}/schemas/{schema}/queries`. That write belongs to Catalog.
