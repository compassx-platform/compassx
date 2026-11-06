# Documents

A notebook the screen can open is a `UnifiedCatalogNotebook` row. The file path on that row is `blob_path`. A caller may name the notebook in four ways, and the privilege check uses the row that was found:

1. The exact `blob_path`.
2. `catalog.schema.name`, when the path does not end in `.ipynb` and has three dot-separated parts.
3. `catalog/schema/name` or `catalog/schema/name.ipynb`.
4. The bare notebook name.

A missing row is 404 `Notebook not found in catalog`. A database error during lookup is 500 `Catalog lookup failed: {error}`. A path that contains `..` is 400 `Invalid path` when it is turned into a storage key.

## Config and list

`GET /api/v1/notebook/config` requires a signed-in workspace member. It returns `base_url`, `ws_url`, `token`, and `workspace_slug`. `token` is always empty. The base URL is `JUPYTER_BASE_URL` when that is set, otherwise `/api/v1/notebook/jupyter`. The WebSocket URL follows `JUPYTER_WS_URL` the same way. `workspace_slug` is empty when the request has no workspace.

`GET /api/v1/notebook/list` returns notebooks in catalogs bound to the workspace, ordered by catalog, schema, then name. The caller must `BROWSE` each one. Each item has `id`, `path`, `name`, `full_name`, `catalog_name`, `schema_name`, `storage_location`, `last_compute_resource_id`, and `last_kernel_name`. The storage location is the catalog storage path `notebooks/{blob_path}` when the schema has a storage context, otherwise the notebooks bucket key.

## Create

`POST /api/v1/notebook/create` takes `name`, optional `folder` (accepted and ignored), and optional `catalog_name` and `schema_name`. When the catalog or schema is missing, the workspace default catalog binding and its first schema are used. Outside a workspace that is 422 `catalog_name and schema_name are required outside a workspace.` A workspace with no bound schema is 422 `The workspace has no bound catalog schema for notebooks.`

The caller must hold `CREATE` on that schema. The name keeps letters, digits, and underscores. Anything else becomes `_`. A name that becomes empty is `untitled`. Catalog create then writes the row and the file. A name that already exists is 409. Any other `ValueError` from Catalog is 400. The caller becomes the owner.

## Load, save, delete, compute

`GET /api/v1/notebook/files/{path}` requires `SELECT`. A missing file is 404 `Notebook not found`. The body is the notebook JSON plus `_catalog`, which includes the id, names, timestamps, `created_by`, `updated_by`, `last_compute_resource_id`, and `last_kernel_name`.

`PUT /api/v1/notebook/files/{path}` requires `EDIT` and writes the JSON body. The response is `{ "saved": true, "path": "..." }`.

`DELETE /api/v1/notebook/files/{path}` requires `MANAGE`. It deletes the file through Catalog, then deletes the catalog row. The response is `{ "deleted": true, "path": "..." }`.

`PUT /api/v1/notebook/{id}/compute` requires `EDIT` on the notebook and `USE_COMPUTE` on `resource_id`. The body is `resource_id` and `kernel_name`. A missing id is 404 `Notebook not found`. A commit failure is 500 `Failed to save compute info: {error}`. Success is `{ "saved": true, "notebook_id": "..." }`.
