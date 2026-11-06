# Kernels

A notebook kernel runs on the compute resource the notebook is attached to. Compute does not proxy Jupyter itself. Notebooks owns `/api/v1/notebook/jupyter`. Compute tells the notebook which pod is ready and asks Enterprise Gateway to start a kernel on it.

## Connection info

`GET /resources/{resource_id}/kernel-info` requires `USE_COMPUTE`. It records activity with the sandbox reaper before reading status.

No `job_id` returns HTTP 400 `PodNotRunning` and `No running pod for resource: {id}`. A missing resource is HTTP 404 `NotFound`. On the Kubernetes path, `JobNotFoundError` is HTTP 404 `JobNotFound`. A phase other than `Running` is HTTP 400 `PodNotRunning` and `Compute pod for resource {id} is {phase}. Wait for it to be Running before connecting.`

The kernelspec is `spark_python`, `ray_python`, `flink_python`, or `duckdb_python`. Any other runtime uses `spark_python` on this route.

On the platform path the body has `pod_name` and `pod_ip` null, `kernel_ready` false, and kernel env `COMPASSX_JOB_ID`, `KERNEL_RUNTIME`, `KERNEL_CATALOG_API_URL`, and `CATALOG_API_URL`. The catalog URL is `try_resolve_url_container("backend", "http://localhost:8000")` plus `/api/v1/catalog`.

On the Kubernetes path the route reads the pod IP. It execs `python -c "import ipykernel; print('ok')"` with a 10 second timeout. `kernel_ready` is true when the output contains `ok`. A failed check logs debug `ipykernel check failed for resource {id}: {error}` and `kernel_ready` stays false. A pod read failure is HTTP 500 `K8sError` and `Could not read pod: {error}`. The kernel env on this path is `COMPASSX_JOB_ID`, `KERNEL_RUNTIME`, and `KERNEL_CATALOG_API_URL`. It does not include `CATALOG_API_URL`.

## Start a kernel

`POST /resources/{resource_id}/start-kernel` requires `USE_COMPUTE`. The same running check applies. A phase that is not `Running` is HTTP 400 `PodNotRunning` and `Compute pod for resource {id} is {phase}. Wait for Running state.`

The kernelspec map is the same, except an unknown runtime uses `duckdb_python` here.

The route lists kernels at Enterprise Gateway `{internal_url}/api/kernels`. A kernel whose env `KERNEL_COMPASSX_JOB_ID` equals this job is deleted. That logs `start-kernel: killed stale kernel {kernel} for resource {id}`. A cleanup failure logs debug `start-kernel: stale kernel cleanup failed (non-fatal): {error}` and the start continues.

The new kernel env is:

- `KERNEL_COMPASSX_JOB_ID` and `KERNEL_RUNTIME`
- `KERNEL_CATALOG_API_URL` and `CATALOG_API_URL`
- `KERNEL_NOTEBOOK_SESSION_TOKEN` and `NOTEBOOK_SESSION_TOKEN`, taken from the `Authorization` bearer token, or empty
- `KERNEL_WORKSPACE_ID` and `WORKSPACE_ID`
- `KERNEL_WORKSPACE_SLUG` and `WORKSPACE_SLUG`, from `ComputeResourceService._resolve_workspace_name`

If the request has no workspace id, the route loads the resource and uses its `workspace_id`. A failure there is ignored.

A created kernel id is registered with Notebooks through `register_kernel_resource(kernel_id, resource_id)`. A failure there is ignored. The Enterprise Gateway JSON is the HTTP body.

Enterprise Gateway HTTP errors log `EG kernel start failed resource_id={id} status={status} body={text}` and return HTTP 502 `EGError` with `EG returned {status}: {text}`. A connection error logs `EG kernel start failed resource_id={id} url={url} error={error}` and returns HTTP 503 `EGUnreachable` with `Enterprise Gateway is not reachable at {url}. Start the Enterprise Gateway service or its local port-forward, then retry.` Any other failure logs `EG kernel start failed resource_id={id}` and returns HTTP 500 `EGError`.

## Logs

`GET /resources/{resource_id}/logs` requires `USE_COMPUTE`. It streams server-sent events. If `sse-starlette` is not installed the response is HTTP 501 `NotSupported` and `sse-starlette not installed`.

On the platform path, a phase other than `Running` or `Pending` is HTTP 400 `RuntimeNotRunning` and `No running runtime for resource: {id}`. Each log line is `{"data": line}`. A missing runtime yields `[info] Compute runtime {id} is initializing. Logs will appear once the container starts.`

On the Kubernetes path, a missing pod name is HTTP 400 `PodNotRunning` and `No running pod for resource: {id}`. Lines come from `stream_pod_logs` in the compute namespace.
