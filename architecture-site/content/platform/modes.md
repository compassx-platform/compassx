# Deployment modes

A deployment mode chooses which platform services start. It is not the service mode. A service mode is `local`, `docker`, or `kubernetes` and comes from the profile. A deployment mode is `full` or `app` and comes from `compassx/modes.yaml`.

`full` has no service list, so every service in the active profile starts. `app` starts `postgres`, `redis`, `backend`, and `frontend`. It sets `STORAGE_BACKEND` to `local`, and Docker Compose also loads `deployments/docker-compose/docker-compose.app.yml`.

The name is resolved in this order: the command argument, `COMPASSX_PLATFORM_MODE`, `.compassx/active-mode`, then `full`. An unknown name raises `PlatformError` with `Deployment mode '{name}' is not defined. Available: {list}`.

`PlatformContainer` loads the mode and calls `apply_mode_environment`. Mode environment values replace values already set on the process. `PlatformManager` drops services the mode does not include. Asking to start a service the mode excludes raises `PlatformError` with `Service(s) {names} are not part of deployment mode '{mode}'. Use --mode full to start them.`

`compassx mode list` and `compassx mode use` forward to `compassx/cli/application/mode_list.py` and `mode_use.py`. The command names stay on `compassx.cli.main`.
