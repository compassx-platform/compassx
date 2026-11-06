# Catalogs and schemas

A catalog is a `UnifiedCatalog` row. A schema is a `UnifiedCatalogSchema` row under it. The HTTP edge is `add_catalog`, `read_catalogs`, `remove_catalog`, `add_schema`, and `remove_schema` on `/api/v1/catalog`.

## Create

`CreateCatalog` refuses a second catalog with the same name and stores the type, optional connection, database name, storage backend, and base path. The actor recorded on the row is the signed-in user's email, or `system` when the user dict has no email.

`CreateSchema` loads the catalog by name, refuses a missing catalog or a duplicate schema name, and stores the description and the actor from `_current_actor` (email, then `sub`, then `id`, then `system`).

`DeleteCatalog` deletes the catalog row. The ORM cascade removes its schemas and the tables, volumes, notebooks, dashboards, tools, connections, and queries under them. A Postgres catalog's remote database is left as it is. `DeleteSchema` refuses while the schema still has notebooks or dashboards, naming them in the error. When none remain, it deletes the schema row.

## What a caller sees

`ListCatalogs` ensures a catalog named `compassx` exists, then lists catalogs ordered by name. When a workspace id is passed, the list keeps catalogs marked for all workspaces and catalogs bound to that workspace.

A catalog whose type is `postgres` and which has a connection and a database name is not listed from the local schema rows. `ListCatalogs` asks `BrowseConnectionSchemas` for the remote schemas and returns those names with a table count of zero. If that connection fails, the error is printed and the local schema rows are used instead.

## Postgres sync

`POST /api/v1/catalog/catalogs/{catalog_name}/sync` calls `SyncPostgresCatalog`. The catalog must be type `postgres` and must have a connection id and a database name. The reader opens that connection and reads `information_schema` for schemas, base tables, and columns, skipping `pg_catalog`, `information_schema`, `pg_toast`, `catalog_search`, and temporary schemas. Each remote schema and table is upserted into the catalog tables, columns are replaced, and each table is enqueued for embedding. The call returns the counts of schemas, tables, and columns synced. The route logs a sync failure at error and does not change the HTTP path.

## Workspace binding

`CatalogBindingService` binds a catalog to a workspace with a privilege and an optional default flag. Binding the name `compassx` creates that catalog when it is missing. Setting a binding as the default clears the default flag on the workspace's other bindings. The account workspace-create route uses this service to bind `{workspace}_default` as an Iceberg catalog. That route is workspace behavior; Catalog only stores the catalog and the binding.

## Storage on the catalog

`PUT /api/v1/catalog/catalogs/{catalog_name}/storage` updates the catalog's storage backend and base path. `CreateIcebergSchema` resolves a storage backend by name, writes the schema's `storage_backend_id` and `base_path`, and writes a `.schema` marker in blob storage. If the marker write fails, the schema row remains and the log warning is `Failed to write Iceberg schema marker to blob storage: %s`.
