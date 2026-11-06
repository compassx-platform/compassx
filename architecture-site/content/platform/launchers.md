# Launchers

A launcher starts the platform services for one mode. `PlatformContainer.launchers` builds three: `LocalProcessLauncher` for `local`, `DockerComposeLauncher` for `docker`, and `KubernetesLauncher` for `kubernetes`. Their loggers stay `compassx.launchers.local_process`, `compassx.launchers.docker_compose`, and `compassx.launchers.kubernetes`.

## Local process

`LocalProcessLauncher` reads `services.{name}.command` and `cwd` from the profile. A service with no command raises `LauncherError`: `Service '{name}' has no local command configured in profile '{profile}'. Add services.{name}.command.`

`{venv_python}` becomes the virtualenv interpreter: `Scripts/python.exe` on Windows and `bin/python` elsewhere. It checks `BACKEND_VENV_PATH` first, then `{cwd}/.venv`. If neither exists the error is `Could not find a backend Python interpreter. Set BACKEND_VENV_PATH to an external venv, or create one at {path} (see backend/README.md).`

State files live under `.compassx/services/`. If the recorded pid is still alive, start logs `local: %s already running (pid=%s)` and leaves it. A windowed service opens a console. Windows uses a new console. macOS uses Terminal. Start logs `local: started %s pid=%s (%s)` with the strategy class name. A background service logs `local: started %s pid=%s`. Stop logs `local: stopped %s pid=%s`.

## Docker Compose

`DockerComposeLauncher` runs `docker compose` with the profile's compose files and project name. Every command is logged as `compose: %s`.

When `docker.ensure_images` is true, start builds or reuses the local images first. A cached tag logs `docker-launcher: image %s available, skip`. When nothing needs a build it logs `docker-launcher: all required images are cached/available`. A build logs `docker-launcher: building %s from %s`.

Start then runs `up -d --wait` and logs `compose: services up: %s`. Stop runs `stop` and logs `compose: services stopped: %s`. Restart runs `restart`.

Compose names are not always the profile names. `airflow` is `airflow-webserver` and `airflow-scheduler`. `minio-console` and `jupyter-server` have no container of their own, so Compose start and stop skip them. Every other name is used as-is.

`ps --format json --all` supplies status. A missing container is `not created`. Detail is `state={state}` and, when Docker reports health, ` health={health}`. `healthy` is true only when that health value is `healthy`.

A failed compose command becomes `LauncherError`. Port conflicts say `A required port is already in use by another process. Stop the conflicting process or change the port mapping. Details: {stderr}`. An unknown service says `Unknown compose service. Check service names in the compose file. Details: {stderr}`. A pull failure says `Image could not be pulled (missing image or no registry access). Details: {stderr}`. Anything else says `docker compose {args} failed (rc={code}): {stderr}`.

## Kubernetes

`KubernetesLauncher` applies manifests and, when `kubernetes.port_forwards` is true, forwards the profile's `exposed_services`. If that list is empty it forwards `frontend`. It logs `k8s-launcher: port-forwards active for: %s` and then `k8s-launcher: services started: %s`.

`kubernetes-local` patches images and applies the local manifest set, including namespace, config, RBAC, ingress, backend, frontend, Enterprise Gateway, and Jupyter Server. `kubernetes-cloud` applies the manifests as stored. A missing manifest logs `k8s-launcher: manifest not found (skipped): %s`. No files at all logs `k8s-launcher: no manifests to apply`. A missing manifests directory logs `k8s-launcher: manifests directory not found: %s`.

Image preparation logs `k8s-launcher: image %s already in minikube, skip`, `k8s-launcher: pulling %s`, `k8s-launcher: building %s from %s`, and `k8s-launcher: loading %s into minikube`. RBAC readiness logs `k8s-launcher: RBAC ready`. Ingress installation logs `k8s-launcher: applying ingress-nginx controller (server-side apply)` and `k8s-launcher: ingress-nginx controller applied successfully`.

Stop scales each known deployment or statefulset to `0` replicas and stops port-forwards. It does not delete the namespace.

A stale port-forward is removed. Success logs `k8s-launcher: killed stale kubectl PID=%s holding port %s`. A failure is debug: `k8s-launcher: _kill_stale_port_forward(%s) failed (non-fatal): %s`. kubectl itself is logged as `k8s-launcher: running %s`.
