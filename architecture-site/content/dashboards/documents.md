# Documents

A document is the JSON on the `dashboards` row plus the catalog row that names it. List, read, save, delete, publish, discard, clone, and layout all go through this module. Create from the product screen goes through Catalog and lands in the schema you selected. `POST /api/v1/dashboards` creates into the workspace default schema.

## List

`GET /api/v1/dashboards` loads every dashboard, newest `updated_at` first, then keeps only rows that have a `UnifiedCatalogDashboard` in a catalog bound to the current workspace. Unregistered rows are left out. Each remaining row is kept when `guard.can` allows `BROWSE` on `catalog.schema.name`.

The list item is `id`, `name`, `folderId`, `isDraft`, `publishedAt`, `createdBy`, `permissionMode`, `createdAt`, `updatedAt`, `catalog_name`, and `schema_name`.

## Create

`POST /api/v1/dashboards` returns 201. The body is `name`, optional `folderId`, and `permissionMode` (default `individual`).

The action resolves a destination schema before it writes:

1. The workspace's default catalog binding, else the first catalog with `all_workspaces`.
2. If neither exists, only a workspace admin may create `workspace_catalog_{first 8 of workspace id}` and a default binding.
3. The first schema in that catalog. If there is none, only a workspace admin may create a schema named `default`.
4. The caller must hold `CREATE` on that schema.

It then inserts a draft with one page named `Page 1`, empty widgets, empty datasets, and `claim_ownership` on the new securable. The response is the full document: the list fields plus `pages`, `widgets`, `datasets`, and `settings`.

Catalog's create, used by the screen, writes the same page shape into the schema the person picked. Name clashes in that schema are rejected there. This module's create does not check for a duplicate name.

## Read and save

`GET /api/v1/dashboards/{id}` requires `BROWSE`. A missing row, or a row with no catalog registration, is 404 `Dashboard not found`.

`PUT /api/v1/dashboards/{id}` requires `EDIT`. The body may set `name`, `pages`, `widgets`, `datasets`, `settings`, `permissionMode`, and `folderId`. Omitted fields stay as they are. A new name relocates grants from the old `catalog.schema.name` to the new one before the document name changes. If there is no catalog row, the rename is a no-op and the document name still changes.

## Delete, publish, discard

`DELETE /api/v1/dashboards/{id}` requires `MANAGE`, returns 204, deletes the catalog registration, then deletes the document.

`POST /api/v1/dashboards/{id}/publish` requires `EDIT`. It sets `is_draft` to false and `published_at` to the current UTC time.

`POST /api/v1/dashboards/{id}/discard` requires `EDIT`. It sets `is_draft` to true and leaves pages, widgets, and datasets as they are. There is no published snapshot to restore.

## Clone

`POST /api/v1/dashboards/{id}/clone` requires `BROWSE` on the source, then the same default-schema `CREATE` check as create. The copy is named `{name} (copy)`, is a draft, and is owned by the caller. Page ids, widget ids, and dataset ids are new. Widget `pageId` and dataset `dashboardId` point at the copy.

## Layout

`PUT /api/v1/dashboards/{id}/pages/{pageId}/layout` requires `EDIT`. The body is `{ "layout": [...] }`. A page id that is not on the document is 404 `Page not found`. The matching page's `layout` is replaced and the pages list is written back.
