# Tools

Catalog exposes two kinds of tool.

A promoted tool is a Python function stored as a catalog object. It lives under a schema, next to tables and notebooks, and an agent can call it by name.

`CatalogTool` is the built-in agent tool whose key is `catalog`. An agent uses it to list and search the assets already registered in the catalog. It is not a row in `catalog_tools`.

## Promoted tools

A promoted tool is a `UnifiedCatalogTool` row. The name is unique inside one catalog and schema. `full_name` is `catalog.schema.name`. Each promotion writes a `UnifiedCatalogToolVersion` row. Promoting the same name again increments `current_version`, replaces the current source, parameters, description, and connection list, and appends a new version. Older version rows stay.

The HTTP routes are on `app.catalog.tool_routes`, mounted from `main.py`. The same handlers also answer the unversioned paths, which are hidden from the OpenAPI schema.

| Call | Path | Result |
| --- | --- | --- |
| Promote | `POST /api/v1/catalog/tools/promote` and `POST /catalog/tools/promote` | 201 and the tool, including its versions |
| List | `GET /api/v1/catalog/tools` and `GET /catalog/tools` | Tools, optionally filtered by `catalog` and `schema` or `schema_name` |
| Read | `GET /api/v1/catalog/tools/{tool_id}` | One tool. A missing id is 404, `Tool '{tool_id}' not found.` |

Promote takes the signed-in user id as the owner and as `promoted_by`. A failure is HTTP 400 with the exception text, and the route logs `Failed to promote tool: %s` with a traceback on logger `app.catalog.tool_routes`.

`promote_tool` creates the catalog and schema when they are missing, with descriptions `Auto-created catalog for {name}` and `Auto-created schema for {name}`. When the request omits a description, parameter schema, or connection list, `parse_tool_code_metadata` reads them from the first function in the source. A decorator keyword `name`, `description`, or `connections` overrides the function name and docstring. Argument annotations become JSON Schema types. A parse failure logs `Could not parse AST from tool source code: %s` at warning and the tool is still stored, named `unnamed_tool` when no name was given.

## From a notebook

Inside a notebook kernel, `cx.tools.promote(function, catalog=..., schema=...)` in `services/compassx_tools/promotion.py` sends the function source to `POST /api/v1/catalog/tools/promote`. The function is usually marked with `@cx.tool(name=..., description=..., connections=[...])`. The name defaults to the function name. The notebook path comes from the call or from `COMPASSX_NOTEBOOK_PATH`, `NOTEBOOK_PATH`, or `JPY_SESSION_NAME`. On success the cell prints `[OK] Promoted tool '{full_name}' (v{version}) to Unified Catalog!`. If every HTTP attempt fails and the in-process fallback also fails, the call raises `Failed to promote tool to catalog API: {error}`.

## What you see in the catalog

The data catalog screen loads tools with `GET /catalog/tools` for the open schema. The schema has a **Tools** count next to Tables, Volumes, Notebooks, Dashboards, and Queries. Opening a tool goes to `/data-catalog/{catalog}/{schema}/tool/{name}`.

The tool page has Overview, Parameter Schema, Source Code, Version History, and Permissions. Overview shows the full name, current version, owner, timestamps, and the source notebook when one was stored. A notebook path opens that notebook. Parameter Schema lists each argument, its type, and whether it is required. Source Code shows the current version's Python. Version History lists every promotion, who promoted it, and when.

## How an agent runs a promoted tool

When an agent session starts, the orchestrator loads every `UnifiedCatalogTool`. Nova, and an agent named `ai-data-engineer`, receive all of them. Another agent receives a tool when its name or full name is in that agent's enabled tools, or when the agent has no enabled-tool list. The wrapper is `ExternalCatalogTool`. Its key is the tool name, and it runs the pinned current version through `execute_agent_tool`, using the first declared connection when the call does not pass `connection_id`. A failure while loading these tools logs `Could not load external catalog tools into manifest: %s` and the rest of the session still starts.

## The catalog agent tool

`CatalogTool` in `app.catalog.tools` registers itself on the agent tool registry at import. The registry key is `catalog`, and the display name is Catalog Manager. If registration fails, the log is `Failed to register CatalogTool dynamically: %s` at error.

The agent passes `operation` and `payload`. An unknown operation returns `Unsupported catalog operation: {operation}`. Any exception is logged as `Catalog operation %s failed: %s` and returned as a failed tool result. The account session opened for the call is closed afterward.

When the agent has a workspace id, list and search operations only see catalogs marked for all workspaces and catalogs bound to that workspace. An agent with no workspace id is not filtered. Asking for a catalog outside that set raises `Access denied to catalog '{name}' in this workspace`.

| Operation | What it does |
| --- | --- |
| `list_catalogs` | Catalogs the workspace may see, each with its schema names. |
| `list_schemas` | Schemas of `payload.catalog_name`, with table and notebook counts. The catalog name is required. |
| `list_tables` | Tables, optionally limited to one catalog and schema. The default limit is 100 and the cap is 500. Each row includes the full name and the column names. |
| `search_catalog` | Semantic search of `vector_db.assets`. An empty query lists assets of the requested type. With an embedding, results are ranked by cosine similarity, at most 25. Without an embedding it logs `Semantic embedding not available for %r; falling back to keyword search` at info and searches names and descriptions, then catalog tables and notebooks. |
| `get_asset_schema` | Columns of `catalog.schema.table` through `get_table`. |
| `get_asset_details` | Search-index metadata plus the table, notebook, dashboard, or volume row. `full_name` and `object_type` are required. |
| `check_data_coverage` | Opens the table through the SQL warehouse DuckDB plan and reports whether any row matches `filters`, plus up to five sample rows. A `date_range` filter uses the first date-like column, or a column named `timestamp`. |
| `resolve_entity` | Looks up `entity_name`. With `candidate_table` and `candidate_column`, it searches that column. Otherwise it scans catalog tables for `name`, `tag`, `asset_name`, `code`, `label`, `title`, `id`, or `uuid`. No match returns an empty object. |
| `list_related_assets` | Foreign keys of a Postgres catalog table. A catalog that is not type `postgres`, or that has no connection, returns an empty list. A failed introspect logs `Failed to introspect foreign keys for %s: %s` and also returns an empty list. |
| `sync_foreign_catalog` | Runs `sync_foreign_catalog` for `connection_id` into `foreign_catalog_name`. Both are required, and the foreign catalog must be visible to the workspace. |
| `search_catalog_metadata` | Keyword search of catalog, schema, and table rows. `object_type` may be `all`, `catalog`, `schema`, or `table`. The default limit is 20 and the cap is 100. `all` sorts the combined results by name and then applies the limit. |

`search_catalog` is the agent path. The HTTP search on `GET /api/v1/catalog/search` is a separate route and returns 503 when no embedding connection is configured. That route is described on [Search](search.md).
