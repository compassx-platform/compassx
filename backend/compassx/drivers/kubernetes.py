"""Kubernetes Driver — runs runtimes as Deployments/Pods.

infra_id == deployment name. Pods are discovered via the
compassx/runtime-id label, so pod restarts never leak upward.

Ported from backend/app/compute/services/manager.py + logs.py.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import AsyncIterator

from compassx.drivers.k8s_client import K8sApiClient
from compassx.interfaces.driver import ResourceDriver
from compassx.models import (
    ExecResult,
    RuntimeInfo,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeProvisionError,
    RuntimeSpec,
)
from compassx.models.runtime import (
    MANAGED_BY_LABEL,
    MANAGED_BY_VALUE,
    RUNTIME_ID_LABEL,
    RUNTIME_TYPE_LABEL,
)

logger = logging.getLogger(__name__)

_PENDING_RETRY_INTERVAL = 2   # seconds between retries when pod is Pending
_PENDING_MAX_WAIT = 60        # max seconds to wait for pod to start
_SENTINEL = object()          # signals end of log stream

_PHASE_MAP = {
    "Pending": RuntimePhase.PENDING,
    "Running": RuntimePhase.RUNNING,
    "Succeeded": RuntimePhase.STOPPED,
    "Failed": RuntimePhase.FAILED,
    "Unknown": RuntimePhase.UNKNOWN,
}


class KubernetesDriver(ResourceDriver):
    name = "kubernetes"

    def __init__(
        self,
        client: K8sApiClient,
        namespace: str = "compassx-jobs",
        image_pull_policy: str = "IfNotPresent",
    ) -> None:
        self._k8s = client
        self._namespace = namespace
        self._image_pull_policy = image_pull_policy
        from kubernetes import client as k8s_models
        from kubernetes.client.exceptions import ApiException

        self._m = k8s_models
        self._ApiException = ApiException

    # ── helpers ──────────────────────────────────────────────────────────

    def _deployment_name(self, runtime_id: str) -> str:
        return f"compassx-runtime-{runtime_id}"

    def _ensure_namespace(self) -> None:
        try:
            self._k8s.core().read_namespace(name=self._namespace)
        except self._ApiException as exc:
            if exc.status in (401, 403):
                # ServiceAccount has namespaced RBAC (cannot read cluster namespaces)
                logger.debug(
                    "K8s: read_namespace returned %s, assuming namespace %s exists",
                    exc.status,
                    self._namespace,
                )
                return
            if exc.status != 404:
                raise
            ns = self._m.V1Namespace(
                metadata=self._m.V1ObjectMeta(
                    name=self._namespace,
                    labels={"compassx/managed": "true"},
                )
            )
            self._k8s.core().create_namespace(body=ns)
            logger.info("K8s: namespace %s created", self._namespace)

    def _build_deployment(self, spec: RuntimeSpec):
        m = self._m
        labels = {
            **spec.labels,
            "app": "compassx",
            RUNTIME_ID_LABEL: spec.runtime_id,
            RUNTIME_TYPE_LABEL: spec.runtime_type,
            MANAGED_BY_LABEL: MANAGED_BY_VALUE,
        }
        selector = {RUNTIME_ID_LABEL: spec.runtime_id}

        env_vars = [m.V1EnvVar(name=k, value=v) for k, v in spec.env.items()]
        ports = [
            m.V1ContainerPort(container_port=p.container_port, name=p.name[:15])
            for p in spec.ports
        ]
        requests: dict[str, str] = {}
        limits: dict[str, str] = {}
        res = spec.resources
        if res.cpu_request:
            requests["cpu"] = res.cpu_request
        if res.memory_request:
            requests["memory"] = res.memory_request
        if res.cpu_limit:
            limits["cpu"] = res.cpu_limit
        if res.memory_limit:
            limits["memory"] = res.memory_limit
        if res.gpu:
            limits["nvidia.com/gpu"] = str(res.gpu)
        # Extra k8s-specific limits (e.g. from compute profiles) pass through metadata.
        limits.update(spec.metadata.get("k8s_extra_limits") or {})
        requests.update(spec.metadata.get("k8s_extra_requests") or {})

        volume_mounts = []
        volumes = []
        for v in spec.volumes:
            volume_mounts.append(
                m.V1VolumeMount(name=v.name, mount_path=v.mount_path, read_only=v.read_only)
            )
            if v.claim_name:
                volumes.append(
                    m.V1Volume(
                        name=v.name,
                        persistent_volume_claim=m.V1PersistentVolumeClaimVolumeSource(
                            claim_name=v.claim_name
                        ),
                    )
                )
            elif v.host_path:
                volumes.append(
                    m.V1Volume(
                        name=v.name,
                        host_path=m.V1HostPathVolumeSource(path=v.host_path),
                    )
                )

        container = m.V1Container(
            name=spec.runtime_type or "runtime",
            image=spec.container_image,
            command=list(spec.command) or None,
            args=list(spec.args) or None,
            env=env_vars,
            ports=ports or None,
            resources=m.V1ResourceRequirements(
                requests=requests or None, limits=limits or None
            ),
            image_pull_policy=self._image_pull_policy,
            volume_mounts=volume_mounts or None,
            working_dir=spec.working_dir or None,
        )

        pod_spec = m.V1PodSpec(
            containers=[container],
            restart_policy="Always",
            volumes=volumes or None,
        )

        return m.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=m.V1ObjectMeta(
                name=self._deployment_name(spec.runtime_id),
                namespace=spec.namespace or self._namespace,
                labels=labels,
                annotations=spec.annotations or None,
            ),
            spec=m.V1DeploymentSpec(
                replicas=1,
                selector=m.V1LabelSelector(match_labels=selector),
                template=m.V1PodTemplateSpec(
                    metadata=m.V1ObjectMeta(
                        labels=labels, annotations=spec.annotations or None
                    ),
                    spec=pod_spec,
                ),
            ),
        )

    def _get_pod(self, runtime_id: str):
        """Return the newest pod for a runtime, preferring Running pods."""
        pods = self._k8s.core().list_namespaced_pod(
            namespace=self._namespace,
            label_selector=f"{RUNTIME_ID_LABEL}={runtime_id}",
        )
        if not pods.items:
            return None
        items = sorted(
            pods.items,
            key=lambda pod: (
                0 if (pod.status and pod.status.phase == "Running") else 1,
                pod.metadata.creation_timestamp
                or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        return items[0]

    def _read_deployment(self, runtime_id: str):
        try:
            return self._k8s.apps().read_namespaced_deployment(
                name=self._deployment_name(runtime_id), namespace=self._namespace
            )
        except self._ApiException as exc:
            if exc.status == 404:
                raise RuntimeNotFoundError(
                    f"Kubernetes runtime not found: {runtime_id}"
                ) from exc
            raise

    # ── lifecycle ────────────────────────────────────────────────────────

    async def create_runtime(self, spec: RuntimeSpec) -> str:
        deployment = self._build_deployment(spec)
        name = self._deployment_name(spec.runtime_id)

        def _apply():
            self._ensure_namespace()
            apps = self._k8s.apps()
            try:
                existing = apps.read_namespaced_deployment(
                    name=name, namespace=self._namespace
                )
            except self._ApiException as exc:
                if exc.status != 404:
                    raise
                apps.create_namespaced_deployment(
                    namespace=self._namespace, body=deployment
                )
            else:
                deployment.metadata.resource_version = (
                    existing.metadata.resource_version
                )
                apps.replace_namespaced_deployment(
                    name=name, namespace=self._namespace, body=deployment
                )

        try:
            await asyncio.to_thread(_apply)
        except self._ApiException as exc:
            raise RuntimeProvisionError(
                f"Kubernetes failed to create runtime {spec.runtime_id}: {exc.reason}"
            ) from exc
        logger.info(
            "K8s runtime created: runtime_id=%s deployment=%s image=%s",
            spec.runtime_id,
            name,
            spec.container_image,
        )
        return name

    async def start_runtime(self, runtime_id: str) -> None:
        await self._scale(runtime_id, 1)

    async def stop_runtime(self, runtime_id: str) -> None:
        await self._scale(runtime_id, 0)

    async def _scale(self, runtime_id: str, replicas: int) -> None:
        name = self._deployment_name(runtime_id)

        def _patch():
            try:
                self._k8s.apps().patch_namespaced_deployment_scale(
                    name=name,
                    namespace=self._namespace,
                    body={"spec": {"replicas": replicas}},
                )
            except self._ApiException as exc:
                if exc.status == 404:
                    raise RuntimeNotFoundError(
                        f"Kubernetes runtime not found: {runtime_id}"
                    ) from exc
                raise

        await asyncio.to_thread(_patch)
        logger.info("K8s runtime scaled: runtime_id=%s replicas=%s", runtime_id, replicas)

    async def delete_runtime(self, runtime_id: str) -> None:
        name = self._deployment_name(runtime_id)

        def _delete():
            try:
                self._k8s.apps().delete_namespaced_deployment(
                    name=name, namespace=self._namespace
                )
            except self._ApiException as exc:
                if exc.status == 404:
                    raise RuntimeNotFoundError(
                        f"Kubernetes runtime not found: {runtime_id}"
                    ) from exc
                raise

        await asyncio.to_thread(_delete)
        logger.info("K8s runtime deleted: runtime_id=%s", runtime_id)

    # ── inspection ───────────────────────────────────────────────────────

    def _info_from_pod(self, runtime_id: str, pod, deployment=None) -> RuntimeInfo:
        if pod is None:
            replicas = deployment.spec.replicas if deployment and deployment.spec else 0
            phase = RuntimePhase.STOPPED if not replicas else RuntimePhase.PENDING
            return RuntimeInfo(
                runtime_id=runtime_id,
                phase=phase,
                infra_id=self._deployment_name(runtime_id),
            )

        phase_str = pod.status.phase if pod.status and pod.status.phase else "Unknown"
        phase = _PHASE_MAP.get(phase_str, RuntimePhase.UNKNOWN)
        started_at = pod.status.start_time if pod.status else None
        finished_at = None
        message = ""

        if pod.status:
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.waiting and cs.state.waiting.reason in (
                    "ErrImagePull",
                    "ImagePullBackOff",
                ):
                    message = "Image could not be pulled. Check runtime image."
                    phase = RuntimePhase.FAILED
                if cs.state and cs.state.terminated:
                    terminated = cs.state.terminated
                    finished_at = terminated.finished_at
                    if terminated.reason == "OOMKilled":
                        message = "Out of memory. Try a larger compute profile."
                        phase = RuntimePhase.FAILED
                    elif terminated.exit_code and terminated.exit_code != 0:
                        message = (
                            terminated.message
                            or f"Container exited with code {terminated.exit_code}"
                        )

        labels = pod.metadata.labels or {}
        return RuntimeInfo(
            runtime_id=runtime_id,
            runtime_type=labels.get(RUNTIME_TYPE_LABEL, ""),
            phase=phase,
            infra_id=pod.metadata.name,
            message=message,
            created_at=pod.metadata.creation_timestamp,
            started_at=started_at,
            finished_at=finished_at,
            labels=labels,
        )

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        def _status():
            deployment = self._read_deployment(runtime_id)
            pod = self._get_pod(runtime_id)
            return self._info_from_pod(runtime_id, pod, deployment)

        return await asyncio.to_thread(_status)

    async def list_runtimes(self) -> list[RuntimeInfo]:
        def _list():
            deployments = self._k8s.apps().list_namespaced_deployment(
                namespace=self._namespace,
                label_selector=f"{MANAGED_BY_LABEL}={MANAGED_BY_VALUE}",
            )
            infos = []
            for dep in deployments.items:
                runtime_id = (dep.metadata.labels or {}).get(RUNTIME_ID_LABEL, "")
                if not runtime_id:
                    continue
                pod = self._get_pod(runtime_id)
                infos.append(self._info_from_pod(runtime_id, pod, dep))
            return infos

        return await asyncio.to_thread(_list)

    # ── interaction ──────────────────────────────────────────────────────

    def _require_pod(self, runtime_id: str):
        pod = self._get_pod(runtime_id)
        if pod is None:
            raise RuntimeNotFoundError(f"No pod found for runtime: {runtime_id}")
        return pod

    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult:
        from kubernetes.stream import stream as k8s_stream

        def _exec():
            pod = self._require_pod(runtime_id)
            resp = k8s_stream(
                self._k8s.core().connect_get_namespaced_pod_exec,
                pod.metadata.name,
                self._namespace,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    stdout_chunks.append(resp.read_stdout())
                if resp.peek_stderr():
                    stderr_chunks.append(resp.read_stderr())
            resp.close()
            exit_code = resp.returncode if resp.returncode is not None else 0
            return ExecResult(
                exit_code=exit_code,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
            )

        return await asyncio.to_thread(_exec)

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        def _logs():
            pod = self._require_pod(runtime_id)
            kwargs: dict = {"name": pod.metadata.name, "namespace": self._namespace}
            if tail is not None:
                kwargs["tail_lines"] = tail
            return self._k8s.core().read_namespaced_pod_log(**kwargs)

        try:
            return await asyncio.to_thread(_logs)
        except self._ApiException as exc:
            if exc.status == 404:
                raise RuntimeNotFoundError(
                    f"No pod found for runtime: {runtime_id}"
                ) from exc
            raise

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        """Stream logs line by line (ported from compute/services/logs.py).

        - Pending: retry every 2s for up to 60s.
        - Running: follow=True, yield each line as it arrives.
        - Succeeded/Failed: return tail then stop.
        Blocking urllib3 iteration runs in a daemon thread relaying via
        an asyncio.Queue so the event loop never blocks.
        """
        pod = await asyncio.to_thread(self._get_pod, runtime_id)
        if pod is None:
            yield f"[error] No pod found for runtime: {runtime_id}"
            return
        pod_name = pod.metadata.name

        waited = 0
        phase = "Unknown"
        while waited < _PENDING_MAX_WAIT:
            try:
                pod = await asyncio.to_thread(
                    self._k8s.core().read_namespaced_pod,
                    name=pod_name,
                    namespace=self._namespace,
                )
            except self._ApiException as exc:
                if exc.status == 404:
                    yield f"[error] Pod not found: {pod_name}"
                    return
                raise

            phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"
            if phase == "Pending":
                await asyncio.sleep(_PENDING_RETRY_INTERVAL)
                waited += _PENDING_RETRY_INTERVAL
                continue
            break
        else:
            yield f"[error] Pod {pod_name} still Pending after {_PENDING_MAX_WAIT}s"
            return

        kwargs: dict = {
            "name": pod_name,
            "namespace": self._namespace,
            "tail_lines": 100,
            "_preload_content": False,
        }
        if phase == "Running":
            kwargs["follow"] = True

        try:
            resp = await asyncio.to_thread(
                lambda: self._k8s.core().read_namespaced_pod_log(**kwargs)
            )
        except self._ApiException as exc:
            if exc.status == 404:
                yield f"[error] Pod not found: {pod_name}"
            else:
                yield f"[error] Failed to stream logs: {exc.reason}"
            return

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)

        def _read_lines() -> None:
            try:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    if line:
                        asyncio.run_coroutine_threadsafe(queue.put(line), loop)
            except Exception as exc:  # noqa: BLE001 - relay stream errors
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"[error] Log stream error: {exc}"), loop
                )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop)

        threading.Thread(target=_read_lines, daemon=True).start()

        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield item

    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None:
        # kubectl cp equivalent via exec tar. Simple implementation using exec.
        if to_runtime:
            from pathlib import Path

            data = Path(src_path).read_bytes()
            # Write file via exec sh -c with base64 to avoid binary issues.
            import base64

            encoded = base64.b64encode(data).decode("ascii")
            result = await self.exec(
                runtime_id,
                ["sh", "-c", f"echo {encoded} | base64 -d > {dest_path}"],
            )
            if result.exit_code != 0:
                raise RuntimeProvisionError(
                    f"copy_file to runtime failed: {result.stderr}"
                )
        else:
            result = await self.exec(runtime_id, ["cat", src_path])
            if result.exit_code != 0:
                raise RuntimeProvisionError(
                    f"copy_file from runtime failed: {result.stderr}"
                )
            from pathlib import Path

            Path(dest_path).write_text(result.stdout, encoding="utf-8")
