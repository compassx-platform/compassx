# Kernels

Enterprise Gateway has no authentication of its own. This proxy is the check. A kernel is not a securable. It runs on a compute resource, and the caller needs `USE_COMPUTE` on that resource. The link is `KERNEL_COMPASSX_JOB_ID` in the kernel environment, or the in-process map filled by `register_kernel_resource`.

A kernel with no resource id is 404 `kernel not found`. A resource in another workspace is the same 404. The workspace default compute resource is usable by any member of that workspace. When Enterprise Gateway still lists a kernel but did not keep the resource id, and this workspace has a default resource, the kernel is recorded against that default and then checked.

The HTTP routes sit under `/api/v1/notebook/jupyter` and require a signed-in workspace member. The channel WebSocket does not, because a browser socket cannot carry the usual headers. It authenticates itself.

## Start and list

`GET /api/v1/notebook/jupyter/api` and `GET .../api/kernelspecs` are forwarded to Enterprise Gateway.

`GET .../api/kernels` returns only the kernels whose resource this caller may use. Kernels they cannot use are left out of the list.

`POST .../api/kernels` reads the JSON body and requires `USE_COMPUTE` on `env.KERNEL_COMPASSX_JOB_ID`. It then fills environment values when they are absent:

- `KERNEL_NOTEBOOK_SESSION_TOKEN` and `NOTEBOOK_SESSION_TOKEN` from the bearer token.
- `KERNEL_CATALOG_API_URL` and `CATALOG_API_URL`, the in-cluster backend URL plus `/api/v1/catalog`.
- `KERNEL_WORKSPACE_ID`, `WORKSPACE_ID`, `KERNEL_WORKSPACE_SLUG`, and `WORKSPACE_SLUG` from the request workspace, or from the `workspace` query parameter, or from `x-workspace-slug`.
- `MLFLOW_TRACKING_URI` and `KERNEL_MLFLOW_TRACKING_URI`.
- `MLFLOW_S3_ENDPOINT_URL` and `KERNEL_MLFLOW_S3_ENDPOINT_URL`.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, and the same names with a `KERNEL_` prefix. Those three read `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, and `STORAGE_REGION`, with defaults `minioadmin`, `minioadmin`, and `us-east-1`. The handler reaches `os.environ` and this module does not import `os`, so that line raises `NameError` when a start gets that far.

The modified body is posted to Enterprise Gateway `/api/kernels`. The status and body are returned as Enterprise Gateway sent them.

## Get, stop, restart

`GET`, `DELETE`, and `PATCH .../api/kernels/{id}` require access to that kernel, then forward the request. `POST .../api/kernels/{id}/restart` does the same. JupyterLab restarts with POST. DELETE uses the same privilege as start.

## Channels

`WS /api/v1/notebook/jupyter/api/kernels/{id}/channels` reads `workspace` and `token` from the query string. A missing workspace closes with code 4401 and reason `Missing workspace`. A bad token closes with 4401 or 4403. A missing system database closes with 4503 `system database not available`. A kernel the caller cannot use closes with 4403 `Not authorized for this kernel`. The socket is accepted only after that check.

The proxy then connects to Enterprise Gateway on the same path and copies text and binary frames both ways. A frame from the browser touches the sandbox reaper for that compute resource, so an active kernel is not treated as idle. A failed upstream connection logs `WS proxy: failed to connect upstream {url}: {error}` at warning. Group lookup failures log `Group expansion failed for principal {id}` with a traceback.
