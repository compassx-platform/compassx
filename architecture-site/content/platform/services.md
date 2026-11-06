# Service HTTP

Three routers start and inspect platform services from the backend. `main.py` mounts them. Compute's own `/services/{name}/{action}` route is a different API and stays in Compute. Omnigent stays in Apps.

A failure on every route below returns JSON `{"error": type, "message": text, "code": status}` and logs an exception or a warning. The body is not a FastAPI `detail` string.

## Enterprise Gateway

Prefix `/api/v1/services/enterprise-gateway`. Logger `services.enterprise_gateway.router`.

`POST /start`, `POST /stop`, `POST /restart`, and `GET /status` call `get_eg_manager()`. Success is `{"phase": phase, "message": message}`. An exception logs `Error starting EG`, `Error stopping EG`, `Error restarting EG`, or `Error getting EG status` and returns HTTP 500 `InternalError` with `str(exc)`.

`GET /kernels` proxies `{eg}/api/kernels`. A failure logs `EG /api/kernels failed: %s` and returns HTTP 503 `EGUnreachable`, `Enterprise Gateway not reachable.`

`GET /kernels/{kernel_id}` proxies kernel status. EG HTTP 404 becomes HTTP 404 `NotFound`, `Kernel {id} not found.` Any other failure logs `EG kernel status failed: %s` and returns the same 503.

`DELETE /kernels/{kernel_id}` shuts the kernel down. EG HTTP 404 uses the same not-found body. Success is `{"shutdown": true, "kernel_id": id}`. A failure logs `EG kernel shutdown failed: %s` and returns the 503.

`GET /kernelspecs` proxies `{eg}/api/kernelspecs`. A non-200 response is `EGError`, `Could not fetch kernelspecs.`, with that status code. A connection failure logs `EG kernelspecs failed: %s` and returns the 503.

The base URL is `eg_settings.internal_url()`.

## Airflow

Prefix `/api/v1/services/airflow`. Logger `services.airflow.router`.

`POST /start`, `POST /stop`, `POST /restart`, and `GET /status` call `get_airflow_manager()`. Success is `{"phase": phase, "message": message, "details": details}`. Exceptions log `Error starting Airflow`, `Error stopping Airflow`, `Error restarting Airflow`, or `Error getting Airflow status`, and return HTTP 500 `InternalError`.

## Jupyter Server

Prefix `/api/v1/services/jupyter-server`. Logger `services.jupyter_server.router`.

`POST /start`, `POST /stop`, `POST /restart`, and `GET /status` call `get_js_manager()`. Start also starts Enterprise Gateway when the manager does. Success is `{"phase": phase, "message": message}`. Exceptions log `Error starting Jupyter Server`, `Error stopping Jupyter Server`, `Error restarting Jupyter Server`, or `Error getting Jupyter Server status`, and return HTTP 500 `InternalError`.

Each handler in the three router modules forwards to one file under that service's `http/application/` directory. The route paths and JSON stay on the facades.
