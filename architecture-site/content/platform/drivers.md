# Drivers

A driver turns a `RuntimeSpec` into infrastructure. The public operations are create, start, stop, delete, status, list, exec, logs, stream logs, and copy file. Infrastructure errors become `compassx.models` errors. The classes stay where callers import them: `compassx.drivers.local.LocalDriver`, `compassx.drivers.docker.DockerDriver`, and `compassx.drivers.kubernetes.KubernetesDriver`. Docker and Kubernetes import on first use so the CLI can run without those libraries. `get_docker_driver_cls` and `get_kubernetes_driver_cls` are the lazy imports.

Every managed resource is labeled `compassx/runtime-id`, `compassx/runtime-type`, and `compassx/managed-by=compassx-platform`. `infra_id` is the pid, container id, or deployment name. It stays inside the resource manager.

`PlatformContainer` registers `local`, `docker`, and `kubernetes`. The Docker driver joins network `{compose project}_default`, which is `compassx_default` for the shipped profiles. The Kubernetes driver uses `K8sApiClient` and the profile namespace.

## Local

`LocalDriver` stores each runtime under `.compassx/runtimes/{runtime id}` relative to the repo root passed in, or the default state directory. Create requires a command. A second create of the same id raises `RuntimeAlreadyExistsError`: `Local runtime already exists: {id}`. A missing command raises `RuntimeProvisionError`: `Local runtime {id} requires a command`. A spawn failure raises `Failed to spawn local runtime {id}: {error}`.

Success logs `Local runtime started: runtime_id=%s pid=%s command=%s`. Stop logs `Local runtime stopped: runtime_id=%s pid=%s`. Delete logs `Local runtime deleted: runtime_id=%s`. A missing id is `Local runtime not found: {id}`.

## Docker

The SDK is optional. A missing package raises `DriverUnavailableError`: `docker SDK not installed. \`pip install docker\`.` A daemon that does not answer raises `Docker daemon not reachable: {error}`.

Create looks for a local image tag before the requested image. A match logs `Docker driver: mapped image %s -> local %s` or `Docker driver: mapped image %s -> local tag %s`. Success logs `Docker runtime created: runtime_id=%s container=%s image=%s` and returns the container id.

A missing image raises `Image not found: {image}`. Create, start, stop, and delete API failures raise `Docker failed to create runtime {id}: {error}`, `Failed to start runtime {id}: {error}`, `Failed to stop runtime {id}: {error}`, and `Failed to delete runtime {id}: {error}`. Stop logs `Docker runtime stopped: runtime_id=%s`. Delete logs `Docker runtime deleted: runtime_id=%s`. A missing container is `Docker runtime not found: {id}`. A duplicate raises `RuntimeAlreadyExistsError`.

## Kubernetes

`K8sApiClient` tries in-cluster config and logs `K8s: loaded in-cluster config`. It then patches the kubernetes client v36 bearer-token key and logs `K8s: patched InClusterConfigLoader for v36 BearerToken key`. Outside a cluster it loads `~/.kube/config` and logs `K8s: loaded local kubeconfig (~/.kube/config)`. Neither config raises `Kubernetes not reachable. Run \`minikube start\` for local development.` A missing kubernetes package raises `kubernetes package not installed. \`pip install kubernetes\`.`

`SKIP_K8S_SSL_VERIFY` set to `1`, `true`, or `yes` disables verification and logs `K8s: SSL verification disabled`. For a local API host the client clears proxy variables that would send the request through a proxy, and logs `K8s: cleared proxy env for local API host %s: %s`.

The driver creates the namespace when it is missing and logs `K8s: namespace %s created`. Create applies a Deployment. An API failure raises `Kubernetes failed to create runtime {id}: {reason}`. Success logs `K8s runtime created: runtime_id=%s deployment=%s image=%s`. Scale logs `K8s runtime scaled: runtime_id=%s replicas=%s`. Delete logs `K8s runtime deleted: runtime_id=%s`. A missing deployment is `Kubernetes runtime not found: {id}`. A missing pod during exec or logs is `No pod found for runtime: {id}`.
