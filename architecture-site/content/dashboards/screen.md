# Screen

The product screens live in `frontend/src/modules/dashboards`. Routes, under the workspace app:

- `dashboards` — the list.
- `dashboards/:dashboardId` — the canvas.
- `dashboards/:dashboardId/edit` — the editor.

The list heading is **Dashboards**. The search box placeholder is `Search dashboards...`. An empty workspace says `No dashboards yet.`

**Create Dashboard** opens a dialog. The name starts as `untitled_dashboard_1`, then the next free number. Catalog defaults to `main`, then `default`, then the first catalog that has schemas. Schema defaults to `default`, then `public`, then the first schema. The helper under the schema list says `Select a catalog to load its schemas.` A catalog with no schemas says `No schemas found in this catalog.` Submit is disabled until name, catalog, and schema are set. While the request is in flight the button reads `Creating...`.

That submit does not call `POST /api/v1/dashboards`. It calls `POST /catalog/catalogs/{catalog}/schemas/{schema}/dashboards` with the name. Success toast is `Created dashboard "{name}"`. The new card shows in the list after the catalog and dashboard queries refresh.

Opening a card goes to the canvas. Clone toast is `Cloned "{name}"`. A failed clone says `Failed to clone dashboard`. Delete toast is `Deleted "{name}"`. A failed delete says `Failed to delete dashboard`.

The editor data panel saves a dataset with toast `Dataset saved`, or `Failed to save dataset`. Removing a dataset that a widget still uses says `Dataset is used by one or more widgets`. Export failure says `Export failed`. Adding a widget says `Widget copied`. Adding a filter says `Filter added`. Adding HTML says `HTML widget added`.

The top bar **Publish** toasts `Dashboard published`, or `Publish failed`. **Discard** asks `Discard all draft changes and restore last published version?` and then toasts `Draft discarded`, or `Discard failed`. The server only sets the draft flag. It does not put the last published pages back. **Share** toasts `Share coming soon`.
