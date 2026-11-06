# Shared libraries

Shared libraries are the packages every module imports. They are not a product service and they do not register an agent tool. There is no Tools page.

A file that already lives in its module keeps a one-line re-export at the old path. A file that still implements behavior stays at `app.services`, `app.models`, `app.schemas`, or `app.routes`, because callers and tests import that path. Moving it would change the logger name and the object tests patch.

## Owners

| Path | Owner |
| --- | --- |
| `app/services/encryption.py` | Agents. Re-exports `app.agents.services.encryption` |
| `app/services/llm_client.py` | Agents and AI Gateway. Re-exports `app.agents.services.llm_client` |
| `app/services/document_processor.py` | Agents. Re-exports `app.agents.services.document_processor` |
| `app/services/db_introspector.py` | Agents. Re-exports `app.agents.services.db_introspector` |
| `app/services/user_management_service.py` | Identity. Decodes a JWT and returns `None` on failure |
| `app/services/data_catalog_service.py` | Legacy data catalog. The module object is `app.data.services.data_catalog_service` |
| `app/services/node_pool_manager.py` | Compute. AKS and compute node pools |
| `app/services/drivers/` | Apps. Local, Docker, and Kubernetes app and dev drivers |
| `app/services/ingress_service.py` | Apps. Mode and public URL |
| `app/services/app_runner.py` | Apps |
| `app/services/app_manifest_service.py` | Apps |
| `app/services/framework_detector/` | Apps |
| `app/services/omnigent_dev_service.py` | Apps |
| `app/services/dev_session_service.py` | Apps |
| `app/services/dev_terminal_service.py` | Apps |
| `app/services/studio/` | Apps. Sandbox file commands |
| `app/services/sandbox_credentials.py` | Sandbox |
| `app/services/sandbox_reaper_service.py` | Sandbox |
| `app/routes` re-exports | The module named in [Shims](shims.md) |
| `app/routes/app_routes.py`, `app_dev_routes.py`, `app_task_routes.py`, `lifecycle_routes.py` | Apps facades |
| `app/routes/portal_routes.py` | Portal facade |
| `app/routes/workspace_routes.py` | Workspace. Re-exports `app.workspace.workspace_routes.router` |
| `app/models`, `app/schemas` | The module that owns the table or the request body. See [Shims](shims.md) |
| `app/database.py`, `app/config.py`, `app/dependencies.py` | Composition. See [Composition](composition.md) |

`app/seed` has no Python files.

## Pages

- [Shims](shims.md)
- [Composition](composition.md)
- [Service libraries](services.md)
- [Test cases](test-cases.md)
