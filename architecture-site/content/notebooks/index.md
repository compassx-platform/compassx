# Notebooks

Product module. A notebook is a catalog object plus an `.ipynb` file. This module lists, creates, loads, and saves that file, remembers the last compute resource, and proxies the kernel to Enterprise Gateway. The catalog row is written by Catalog. The bytes are written through Catalog's notebook storage helpers.

HTTP lives in `app.notebooks.routes.notebook_routes` and `app.notebooks.routes.jupyter_proxy`.

- `/api/v1/notebook` is the document and experiment API.
- `/api/v1/notebook/jupyter` is the kernel proxy.

Each handler keeps its name and forwards to one application type. `_safe_key`, `_key_to_rel`, `_NOTEBOOKS_BUCKET`, and `_NOTEBOOKS_PREFIX` stay importable from `notebook_routes`. `register_kernel_resource` stays importable from `jupyter_proxy`. Catalog lookup failures log `Notebook catalog lookup failed for {path}: {error}` at error on logger `app.notebooks.routes.notebook_routes`. Kernel proxy logs stay on logger `app.notebooks.routes.jupyter_proxy`.

This module does not register a tool. Agents edit and run cells through Notebook Manager, key `notebook_manager`, which Agents registers and Nova implements. That tool is documented with Agents.

## Code

- `backend/app/notebooks/routes/notebook_routes.py` — document and experiment HTTP. `NotebookServerConfig`, `NotebookComputeRequest`, `CreateRequest`, and `RegisterModelRequest` stay here.
- `backend/app/notebooks/document/application/` — config, list, create, compute, load, save, and delete.
- `backend/app/notebooks/experiment/application/` — MLflow runs, artifacts, and the model registry.
- `backend/app/notebooks/shared/support.py` — path checks, catalog resolution, and the Jupyter base URL.
- `backend/app/notebooks/routes/jupyter_proxy.py` — kernel HTTP and the channel WebSocket.
- `backend/app/notebooks/kernel/registry.py` — the kernel-to-resource map and the Enterprise Gateway address.
- `backend/app/notebooks/kernel/application/` — one file per proxy action.

## Owns

No table of its own. The catalog notebook row is Catalog's. The last compute resource and kernel name are columns on that row. The kernel-to-resource map is an in-process dict.

## Calls

Governance `Guard` checks `Privilege` on `Securable.notebook` and `Securable.compute`. File bytes go through Catalog's `_read_notebook_content`, `_write_notebook_content`, `_notebook_exists`, and `_delete_notebook_file`. Create calls Catalog's `create_notebook`. Kernels are proxied to Enterprise Gateway. Experiments call the MLflow HTTP API.

## Topics

- [Documents](documents.md)
- [Kernels](kernels.md)
- [Experiments](experiments.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
