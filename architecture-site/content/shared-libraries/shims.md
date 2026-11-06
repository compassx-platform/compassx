# Shims

A shim is a file whose only job is to keep an old import working. The implementation lives in the owning module.

## Routes

These files re-export the module that owns the router:

- `app.routes.agent_routes` from `app.agents.routes.agent_routes`
- `app.routes.agent_context_routes` from `app.agents.routes.agent_context_routes`
- `app.routes.chat_routes` from `app.agents.routes.chat_routes`
- `app.routes.llm_connection_routes` from `app.agents.routes.llm_connection_routes`
- `app.routes.git_connection_routes` from `app.agents.routes.git_connection_routes`
- `app.routes.db_connection_routes` from `app.agents.routes.db_connection_routes`
- `app.routes.notebook_routes` from `app.notebooks.routes.notebook_routes`
- `app.routes.dashboard_routes` from `app.dashboards.routes.dashboard_routes`
- `app.routes.data_catalog_routes` from `app.data.routes.data_catalog_routes`
- `app.routes.workspace_routes` exports `router` from `app.workspace.workspace_routes`

`app.routes.app_routes`, `app.routes.app_dev_routes`, `app.routes.app_task_routes`, and `app.routes.lifecycle_routes` are the Apps HTTP facades. `app.routes.portal_routes` is the Portal HTTP facade. Their handlers forward to application files under `app.apps` and `app.portal`.

## Models

- `app.models.agents` re-exports `app.agents.models.agents`
- `app.models.dashboard` re-exports `app.dashboards.models.dashboard`
- `app.models.compute_resources` re-exports `app.compute.models.compute_resources`
- `app.models.unified_catalog` re-exports `app.catalog.models`
- `app.models.data_catalog` re-exports `app.data.models.data_catalog`
- `app.models.dataset` re-exports `app.data.models.dataset`

These classes are declared on `SystemBase` in `app.models` and stay there:

- `App` in `app.models.app`
- `AppTask` in `app.models.app_task`
- `DevWorkspace` in `app.models.dev_workspace`
- `DevSession` in `app.models.dev_session`
- `PortalConfig` in `app.models.portal_config`, table `portal_configs`, schema `apps`

`app.models` also imports `AgentRuntimeSessionDB` so that table is registered.

## Schemas

- `app.schemas.agents` re-exports `app.agents.schemas.agents`
- `app.schemas.data_catalog` re-exports `app.data.schemas.data_catalog`
- `app.schemas.apps` holds the app create, update, and response models
- `app.schemas.app_tasks` holds the task create, update, and reorder models
- `app.schemas.portal_config` holds `PortalItem`, `PortalSection`, `PortalConfigOut`, and `PortalConfigUpdate`

## Services

- `app.services.encryption` re-exports `app.agents.services.encryption`
- `app.services.llm_client` re-exports `app.agents.services.llm_client`
- `app.services.document_processor` re-exports `app.agents.services.document_processor`
- `app.services.db_introspector` re-exports `app.agents.services.db_introspector`
- `app.services.data_catalog_service` replaces its module entry with `app.data.services.data_catalog_service`, so a patch of `app.services.data_catalog_service` patches the legacy catalog service
