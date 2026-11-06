# Screen

The portal screen is `PortalPage` in `frontend/src/modules/portal`. The shell sidebar, while the active app is `portal`, renders the saved sections instead of the platform navigation.

## Who sees Portal

`AppShell` shows the app switcher from the current role. An account admin, a workspace admin, or a workspace developer sees Platform, Apps, and Portal. Any other member sees only Portal.

A workspace admin is an account admin, or a workspace role `workspace_admin` or `admin`. Account admin is `account_role` `account_admin`, `is_account_admin`, or `workspaceCtx.is_account_admin`.

## Routes

Inside `w/:workspaceSlug/:appId`:

- `portal` opens the portal with no item selected
- `portal/app/:portalAppId` opens an app
- `portal/dashboard/:dashboardId` opens a dashboard
- `app/:portalAppId` also opens an app
- `dashboard/:dashboardId` also opens a dashboard
- `home`, when the app id is `portal`, renders the same page

The page title is `Workspace Portal` when the path starts with `/portal`. On `/home` with the portal app selected, the title is `Portal`.

The config hook calls `GET /api/v1/portal/config` with `workspace_slug`, caches for 30 seconds, and runs only when a workspace slug exists.

## Sidebar

Visible items are those with `is_visible` true. A section with no visible items is skipped. The section title is the divider label.

An app links to `/portal/app/{target_id}`. A dashboard links to `/portal/dashboard/{target_id}`. An external link with a `url` is an anchor to that URL, `target="_blank"`, `rel="noopener noreferrer"`. An external link without a URL links to `/portal`.

The sidebar icon ignores the stored `icon` string. A `streamlit` app uses Sparkles. Any other app uses LayoutGrid. A dashboard uses BarChart2. Anything else uses Globe.

When there are no sections, or every section has no visible items, the sidebar shows `No items pinned to sidebar.`

A workspace admin sees **Customize Sidebar** at the bottom of that sidebar. Opening it shows `CustomizeSidebarDrawer`. Closing it refetches the config.

## Empty portal

While the config is loading, the page shows `Loading Portal...`.

On `/portal` with no app and no dashboard in the URL, the page replaces the URL with the first visible item when that item is an app or a dashboard. An external link in the first position does not change the URL.

When nothing is selected, the page shows the heading **Welcome to Workspace Portal** and the sentence `This is your centralized hub for business applications and dashboards. No items have been published to the sidebar navigation yet.` A workspace admin also sees **Customize Sidebar**.

## App view

`PortalAppView` loads the app with the Apps hooks.

While the app record loads, the text is `Loading application...`. When the app is missing, the heading is **Application Not Found**, the body is `The requested application could not be loaded. It may have been deleted or moved.`, and **Retry** reloads the app.

The app is treated as stopped when `app.status` is `stopped` or `inactive`, or the runtime status is `stopped` or `inactive`, and a start is not already in progress. The heading is `{name} is currently offline`. The body is `This application is stopped to save compute resources. Click the button below to start the container instance.` **Start Application** calls the Apps start action. Success toasts `Starting {name}...`. Failure toasts the response `detail`, or `Failed to start application.`

A start is in progress when the runtime status is `starting` or `provisioning`, or the start mutation is pending. The heading is `Starting {name}...`. The line under it is `runtimeStatus.step_description`, or `Provisioning runtime container and establishing networking...`.

A running app is an iframe. The source is `runtimeStatus.url` when that is set, otherwise `/api/v1/apps/{id}/proxy/`. Until the frame loads, the overlay says `Loading {name}...`. The frame title is the app name.

## Dashboard view

`PortalDashboardView` renders `DashboardEditorPage` with `embedded` true and sets the dashboard store edit mode to false for that dashboard id.

## Customize drawer

The dialog heading is **Customize Portal Sidebar**. The subtitle is `Organize categories, reorder items, and manage app & dashboard visibility for your workspace.`

**Add New Category Section** appends a section id `sec_` plus the current time and the title `New Category`. A category title is an editable field whose placeholder is `Category Name`. Categories and items move up and down. Deleting a category removes it. An empty category says `No items in this category yet.`

**Add App or Dashboard** opens **Add to Category** with tabs **Applications**, **Dashboards**, and **External URL**.

Applications lists `name` and `{app_type} • {status}`. An empty list says `No applications found in this workspace.` Choosing one adds an app item id `item_app_{id}_{time}`, icon `LayoutGrid` when `app_type` is `react` and `Sparkles` otherwise, `url` set to the app route, and `order` 99.

Dashboards lists the name and `Draft` or `Published`. An empty list says `No dashboards found in this workspace.` Choosing one adds a dashboard item id `item_dash_{id}_{time}`, icon `BarChart2`, status `draft` or `published`, and `order` 99.

**External URL** asks for **Link Title** (placeholder `e.g. Documentation Hub`) and **Web URL** (placeholder `https://example.com`). **Add Link** with either field blank toasts `Title and URL are required` and does not add an item. A valid link is type `external_link`, icon `Globe`, `target_id` `ext_` plus the time, and `order` 99.

**Save Changes** sends `PUT /api/v1/portal/config` with the sections. Success toasts `Portal sidebar layout saved.` and closes the drawer. Failure toasts the response `detail`, or `Failed to save portal layout.` **Cancel** closes without saving. The shell refetch runs on close.
