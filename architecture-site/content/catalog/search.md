# Search

Search is a port, `SearchIndex`, implemented by `SqlSearchIndex`. Application types call `enqueue` and `delete`. The adapter calls `enqueue_asset_for_embedding` and `delete_asset_from_search` on `app.catalog.search_indexer` at call time. That module is a shim over `infrastructure/search_indexer.py`.

## What gets indexed

Creating or updating a table, volume, notebook, dashboard, or query enqueues one asset. The asset key is the source row id plus the object type. The text sent for embedding is built by `compose_embedding_text` from the type, name, description, and content summary. Postgres sync enqueues each synced table with a summary of column name and data type. Foreign sync does the same for tables brought in from an external connection.

Enqueue updates the asset row and inserts an embedding job. The embedding worker, started from `main.py`, polls those jobs, calls `get_embedding`, and stores the vector. If no connection is marked for embeddings, `get_embedding` logs `No LLM connection is marked 'use_for_embedding'.` at warning, on logger `app.catalog.embedding_service`, and returns no vector. The HTTP search then answers 503. The agent tool falls back to keyword search and logs `Semantic embedding not available for %r; falling back to keyword search` at info.

`Delete` of a dashboard or query removes the asset and its jobs. `DeleteTable` deletes the `CatalogSearchAsset` row for that table id directly.

A failed enqueue does not roll back the catalog row, except `DeleteQuery`, which rolls back when the search delete itself fails and then continues with the query delete. The warning text is the sentence already on that action, on logger `app.catalog.service`.

## Query

`GET /api/v1/catalog/search` is `search_catalog_assets` in `routes.py`. It authorizes each hit against the caller's governance principal and returns the assets they can see. The agent tool `catalog` searches the same index from `search_catalog`. Its operations, and the promoted tools stored in the catalog, are on [Tools](tools.md). When no embedding connection exists, that operation logs `Semantic embedding not available for %r; falling back to keyword search` at info and searches by keyword.

## Browse and foreign sync

`BrowseConnectionDatabases`, `BrowseConnectionSchemas`, and `BrowseConnectionTables` open the saved connection through `infrastructure/postgres_reader.py` and return the remote names. A connection whose stored secret cannot be decrypted logs `Could not decrypt auth_config for connection %s: %s`.

`POST /api/v1/catalog/connections/{connection_id}/sync-foreign` runs `sync_foreign_catalog`. It reads the remote tables, upserts them as foreign catalog tables, enqueues each one, and writes a `CatalogSearchForeignSyncLog` row. Failure of the sync logs `Foreign catalog sync failed: %s` at error with a traceback. `GET .../foreign-sync-log` returns those rows.

## Connections

Connection definitions, provider plugins, and the connection HTTP routes stay in `connections/`. They are not part of this split. Catalog browse and foreign sync read the connection rows those routes store.
