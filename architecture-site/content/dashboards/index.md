# Dashboards

Product module. A dashboard is a draft document: pages, widgets, datasets, and settings, stored as JSON on one account-database row. The governed object is the catalog registration that points at that row. Without a registration, the row has no catalog path and no grant can reach it.

HTTP lives in `app.dashboards.routes.dashboard_routes`. The router prefix is `/api/v1/dashboards`. Each handler keeps its name and forwards to one application type. Helper names such as `_authorized_dashboard` stay importable from that module and live in `shared/support.py`. This module writes no log lines.

The screen at `w/:workspaceSlug/:appId/dashboards` creates a dashboard through Catalog, into the catalog and schema you pick. `POST /api/v1/dashboards` is a second create path that registers the new document in the workspace default schema. Both paths insert the same `Dashboard` row.

This module does not expose a tool. Agents change dashboards through Dashboard Manager, which Agents registers and Nova implements. That tool is documented with Agents.

## Code

- `backend/app/dashboards/routes/dashboard_routes.py` — HTTP. `CreateBody`, `SaveBody`, and `LayoutBody` stay here.
- `backend/app/dashboards/document/application/` — list, create, read, save, delete, publish, discard, clone, and page layout.
- `backend/app/dashboards/dataset/application/` — query, schema, export, and field values.
- `backend/app/dashboards/shared/support.py` — catalog securable, privilege checks, SQL literal binding, warehouse query, and catalog registration.
- `backend/app/dashboards/models/dashboard.py` — the `dashboards` table. `app.models.dashboard` re-exports the same class. There is no second domain model.

## Owns

Account-database table `dashboards`. Columns that matter: `id`, `name`, `folder_id`, `permission_mode`, `is_draft`, `published_at`, `pages`, `widgets`, `datasets`, `settings`, `created_by`.

## Calls

Governance `Guard` checks `Privilege` on `Securable.dashboard(catalog, schema, name)`. The securable is built from `UnifiedCatalogDashboard`, not from the document row. Dataset SQL runs on the system database through `QueryExecutor` with `source="dashboard"`. A named warehouse comes from `get_warehouse_by_id`. Otherwise the first warehouse with status `running` is used.

## Topics

- [Documents](documents.md)
- [Datasets](datasets.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
