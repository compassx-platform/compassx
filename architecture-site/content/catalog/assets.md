# Notebooks, dashboards, and queries

Catalog stores the asset record. Notebook bytes and dashboard documents are written through storage. The product screens for editing them live in the Notebooks and Dashboards modules.

## Notebooks

`ListNotebooks` and `GetNotebook` read `UnifiedCatalogNotebook` for one schema. `CreateNotebook` writes the notebook JSON through `_write_notebook_content`, inserts the row, and enqueues a search document of type `notebook`. `UpdateNotebook` changes the stored fields and re-enqueues. `MoveNotebook` copies the notebook bytes to the target schema and deletes the old copy when the schema changes. If that file move fails, it logs `Failed to physically move notebook file {path}: {error}` and still updates the catalog row to the new schema and name. `DeleteNotebook` deletes the blob, then the row.

`_read_notebook_content`, `_write_notebook_content`, `_delete_notebook_file`, `_notebook_exists`, and `_run_async` stay importable from `app.catalog.service`. Notebooks, Nova, jobs, and the workspace starter notebook call those names. The functions live in `notebooks/content.py`. They resolve a storage context from the schema. With a context, the key is `notebooks/{blob_path}` under the catalog prefix. Without one, they use the notebooks bucket and `services.storage.fs`.

A failed delete of a storage key logs `Failed to delete storage notebook key %s: %s` or `Failed to delete notebook key %s: %s` at warning and does not raise.

## Dashboards

`CreateDashboard`, `GetDashboard`, `UpdateDashboard`, `MoveDashboard`, and `DeleteDashboard` follow the same shape for `UnifiedCatalogDashboard`. Create and update enqueue type `dashboard`. Delete calls `SearchIndex.delete` and logs `Failed to delete embedding for dashboard %s: %s` when that delete fails, then deletes the catalog row. Renaming the catalog dashboard also renames the linked row in `app.dashboards.models.dashboard.Dashboard` when `dashboard_id` is set.

## Queries

`CreateQuery` stores the SQL text and the first version row, then enqueues type `query`. `CreateQueryVersion` appends a version and re-enqueues. `RestoreQueryVersion` copies that version's text back onto the query. `UpdateQuery` and `MoveQuery` change the record and re-enqueue on update. `DeleteQuery` deletes the search document first. On failure it rolls the session back, logs `Failed to delete embedding for query %s: %s`, and then deletes the query row and commits.

Version reads are `ListQueryVersions` and `GetQueryVersion`. They do not touch the search index.
