# Omnigent server

The shared Omnigent process is not an app row. `main.py` mounts `services.omnigent.router` at `/api/v1/services/omnigent`. These routes do not take a workspace or a user.

Each call returns `phase`, `message`, and `details` from the manager. A failure logs an exception and returns HTTP 500 `{"error":"InternalError","message":"...","code":500}`.

| Method and path | Manager call | Log when it fails |
| --- | --- | --- |
| `POST /start` | `start` | `Error starting Omnigent server` |
| `POST /suspend` | `suspend` | `Error suspending Omnigent server` |
| `POST /resume` | `start` | `Error resuming Omnigent server` |
| `POST /stop` | `stop` | `Error stopping Omnigent server` |
| `POST /restart` | `restart` | `Error restarting Omnigent server` |
| `GET /status` | `get_status` | `Error getting Omnigent server status` |

Start and resume also call `touch_omnigent_activity` before starting, so the idle reaper treats the server as in use. Suspend scales the server down and keeps its volume. Resume calls `start`, not a separate resume method.

`OmnigentManager` in `services/omnigent/manager.py` owns the deployment, service, and ingress. `manifests.py` builds the Kubernetes objects. The logger name on the router stays `services.omnigent.router`.
