# Service libraries

These files still contain the implementation. Callers import them from `app.services`.

## Identity

`decode_access_token` in `app.services.user_management_service` verifies an HS256 JWT. The secret is `JWT_SECRET_KEY`, default `dev-secret-key-replace-me-in-prod`. The audience is `core-opus`. `jwt.PyJWTError` returns `None`. Sign-in for the product uses `app.user_manager.auth_utils.decode_access_token`.

## Compute

`NodePoolManager` lists cluster nodes and deployments, patches a deployment onto a node pool, and calls the Azure CLI to add or update a pool. Missing Kubernetes config logs `Could not initialize Kubernetes client: %s`. A missing `az` logs `Azure CLI ('az') not found on system path; skipping live AKS nodepool command.` Creating the app pool logs `Creating AKS node pool '%s' with VM size %s...`. An existing pool logs `Node pool '%s' already exists on AKS. Updating parameters...`. A successful add logs `AKS nodepool add dispatched successfully.` A CLI error logs `AKS nodepool add returned error: %s`. Moving a deployment logs `Migrated app deployment '%s' to node pool '%s'` or `Migrated compute deployment '%s' to node pool '%s'`.

The app pool name defaults to `apppool` and VM size `Standard_B2s_v2`. The compute pool defaults to `computepool`, VM size `Standard_D4ads_v5`, minimum `0`, maximum `10`.

## Apps

`IngressService.get_active_mode` returns `kubernetes`, `docker`, or `local`. `APP_RUNNER_MODE` of `kubernetes` or `k8s` is kubernetes. `docker` is docker. `local` or `local-dev` is local. Otherwise `COMPASSX_PLATFORM_PROFILE` of `docker`, `compose`, or `docker-compose` is docker, and `kubernetes`, `k8s`, `kubernetes-local`, or `kubernetes-cloud` is kubernetes. `KUBERNETES_SERVICE_HOST` or a compute setting that reports Kubernetes selects kubernetes. `/var/run/docker.sock`, `DOCKER_HOST`, or a successful `docker version` selects docker. Anything else is `local`. `set_mode_override` replaces that result until it is cleared.

`preview_url_from_endpoints` prefers endpoint key `8080`, then `9201`, then the first `http` URL. The result ends with `/`.

`DriverFactory.get_app_driver` and `get_dev_driver` use that mode. `kubernetes` returns the Kubernetes driver. `docker` returns the Docker driver. Every other mode returns the local driver. The factory logger is `app.services.drivers.factory`.

`app_runner_service` runs and proxies an app through the factory. `app_manifest_service` reads `app.yaml`. `FrameworkDetector.detect_framework` reports a frontend, a backend, and a manifest for a directory. `omnigent_dev_service` runs the dev session, git status, and build chat. `git_status_from_porcelain` turns git porcelain text into a path-to-status map. `DevSessionService` stores dev sessions. `dev_terminal_service` attaches a websocket to the dev driver. `WorkspaceFileService` reads and writes sandbox files through `BuildSandboxCommands`.

## Sandbox

`sandbox_credentials` hashes a gateway token, builds a workspace token, and syncs auth files into a sandbox. `gateway_api_key_for_app` returns the key the app driver injects. `SandboxReaperService` stops idle sandboxes. Apps imports it as `unified_reaper_service`.
