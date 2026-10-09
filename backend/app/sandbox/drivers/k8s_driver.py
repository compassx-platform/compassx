"""Kubernetes infrastructure driver for the Sandbox Module."""
import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional
import uuid

from app.sandbox.interfaces import BaseSandboxDriver
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus
from app.services.ingress_service import ingress_service
from compute.config import compute_settings
from compute.k8s_client import get_k8s_client

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_IMAGE = "ghcr.io/omnigent-ai/omnigent-host:latest"


def _sanitize_k8s_name(name: str) -> str:
    """Sanitize name to comply with RFC 1123 DNS subdomain format (max 50 chars)."""
    cleaned = re.sub(r"[^a-z0-9-]", "-", str(name).lower()).strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return (cleaned or "sandbox")[:50]


def _sanitize_k8s_label_value(val: any) -> str:
    """Sanitize a value to be a valid Kubernetes label value (max 63 chars)."""
    if val is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "-", str(val)).strip("-._")
    return cleaned[:63]


def _sanitize_k8s_label_key(key: str) -> str:
    """Sanitize a key to be a valid Kubernetes label key ([prefix/]name)."""
    if not key:
        return "label"
    if "/" in key:
        parts = key.split("/", 1)
        prefix = _sanitize_k8s_name(parts[0])
        name = re.sub(r"[^A-Za-z0-9_.-]", "-", parts[1]).strip("-._")[:63]
        return f"{prefix}/{name}"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", str(key)).strip("-._")[:63]


class KubernetesSandboxDriver(BaseSandboxDriver):
    """Manages isolated compute sandboxes as Kubernetes Pods and Services."""

    def __init__(self):
        from app.config import settings
        self.namespace = getattr(settings, "K8S_NAMESPACE", None) or compute_settings.COMPASSX_NAMESPACE or "compassx"

    def _ensure_namespace(self, k8s) -> None:
        """Ensure the target namespace exists in the Kubernetes cluster."""
        from kubernetes.client import V1Namespace, V1ObjectMeta
        from kubernetes.client.exceptions import ApiException
        try:
            k8s.core().read_namespace(name=self.namespace)
        except ApiException as exc:
            if exc.status == 404:
                try:
                    ns = V1Namespace(
                        metadata=V1ObjectMeta(
                            name=self.namespace,
                            labels={"compassx/managed": "true"},
                        )
                    )
                    k8s.core().create_namespace(body=ns)
                    logger.info("Created K8s namespace: %s", self.namespace)
                except Exception as create_err:
                    logger.debug("Namespace creation error (may exist): %s", create_err)
            else:
                logger.debug("Error checking namespace %s: %s", self.namespace, exc)

    def _resolve_image(self, requested_image: Optional[str]) -> str:
        """Resolve container image with fallback chain for Kubernetes."""
        if requested_image and requested_image.strip() and requested_image.strip() not in ("compassx-dev-host:latest", "compassx-dev-sandbox"):
            return requested_image.strip()
        return os.environ.get("COMPASSX_SANDBOX_IMAGE") or DEFAULT_SANDBOX_IMAGE

    def provision(self, spec: SandboxSpec) -> SandboxInstance:
        """Create and deploy a Kubernetes Pod and Service according to SandboxSpec."""
        from kubernetes.client import (
            V1Container,
            V1ContainerPort,
            V1EnvVar,
            V1HostPathVolumeSource,
            V1ObjectMeta,
            V1PersistentVolumeClaimVolumeSource,
            V1Pod,
            V1PodSpec,
            V1ResourceRequirements,
            V1Service,
            V1ServicePort,
            V1ServiceSpec,
            V1Volume,
            V1VolumeMount,
        )

        k8s = get_k8s_client()
        self._ensure_namespace(k8s)

        sandbox_id = spec.sandbox_id or f"sb-{uuid.uuid4().hex[:10]}"
        clean_sb_id = _sanitize_k8s_name(sandbox_id)
        pod_name = f"compassx-sb-{clean_sb_id}"
        svc_name = f"compassx-sb-{clean_sb_id}"
        image_name = self._resolve_image(spec.image)

        # 1. Environment variables
        env_list = [
            V1EnvVar(name="PORT", value="8080"),
            V1EnvVar(name="COMPASSX_SANDBOX_ID", value=sandbox_id),
            V1EnvVar(name="COMPASSX_CONSUMER_MODULE", value=spec.consumer_module or "generic"),
        ]
        for k, v in spec.env_vars.items():
            if k:
                env_list.append(V1EnvVar(name=str(k), value=str(v) if v is not None else ""))

        # 2. Ports
        container_ports = [
            V1ContainerPort(container_port=p, name=f"p-{p}"[:15]) for p in spec.ports
        ]

        # 3. Mounts & Volumes (HostPath with DirectoryOrCreate)
        volume_mounts = []
        volumes = []
        for idx, mount in enumerate(spec.storage_mounts):
            vol_name = f"vol-{idx}"
            source_p = mount.source_path.replace("\\", "/") if mount.source_path else f"/tmp/{vol_name}"
            # Ensure host directory exists locally if on same machine
            if os.path.exists(os.path.dirname(mount.source_path or "")):
                try:
                    os.makedirs(mount.source_path, exist_ok=True)
                except Exception:
                    pass

            volume_mounts.append(
                V1VolumeMount(
                    name=vol_name,
                    mount_path=mount.mount_path,
                    read_only=mount.read_only,
                )
            )
            volumes.append(
                V1Volume(
                    name=vol_name,
                    host_path=V1HostPathVolumeSource(path=source_p, type="DirectoryOrCreate"),
                )
            )

        # 3b. Check if cluster has shared-storage PVC for multi-app persistent auth/workspace sync
        shared_pvc = os.environ.get("COMPASSX_SHARED_STORAGE_PVC") or "compassx-shared-storage"
        if not any(m.mount_path == "/workspaces" for m in spec.storage_mounts):
            try:
                pvc_check = k8s.core().read_namespaced_persistent_volume_claim(name=shared_pvc, namespace=self.namespace)
                if pvc_check and pvc_check.status and pvc_check.status.phase in ("Bound", "Pending"):
                    volume_mounts.append(
                        V1VolumeMount(
                            name="shared-storage",
                            mount_path="/workspaces",
                            sub_path="workspaces",
                        )
                    )
                    volumes.append(
                        V1Volume(
                            name="shared-storage",
                            persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(claim_name=shared_pvc),
                        )
                    )
            except Exception:
                pass

        # 4. Resource limits
        requests = {"cpu": "100m", "memory": "256Mi"}
        limits = {}
        if spec.cpu_limit:
            limits["cpu"] = str(spec.cpu_limit)
        if spec.memory_limit:
            limits["memory"] = str(spec.memory_limit)

        resources = V1ResourceRequirements(
            limits=limits if limits else None,
            requests=requests if requests else None,
        )

        # 5. Labels & Annotations
        labels = {
            "app.kubernetes.io/managed-by": "compassx-sandbox",
            "compassx.sandbox": "true",
            "compassx.sandbox-id": clean_sb_id,
            "compassx.consumer-module": _sanitize_k8s_label_value(spec.consumer_module or "generic"),
        }
        if spec.consumer_key:
            labels["compassx.consumer-key"] = _sanitize_k8s_label_value(spec.consumer_key)
        if spec.workspace_id:
            labels["compassx.workspace-id"] = _sanitize_k8s_label_value(spec.workspace_id)
        if spec.labels:
            for k, v in spec.labels.items():
                clean_k = _sanitize_k8s_label_key(k)
                labels[clean_k] = _sanitize_k8s_label_value(v)

        annotations = {
            "compassx.sandbox.id": spec.sandbox_id or sandbox_id,
            "compassx.sandbox.name": spec.name or sandbox_id,
            "compassx.sandbox.consumer_key": spec.consumer_key or "",
            "compassx.sandbox.consumer_module": spec.consumer_module or "",
            "compassx.sandbox.workspace_id": str(spec.workspace_id or ""),
        }
        if spec.metadata:
            for mk, mv in spec.metadata.items():
                if mk and mv is not None:
                    annotations[f"compassx.metadata.{mk}"] = str(mv)

        # 6. Container definition
        container = V1Container(
            name="sandbox",
            image=image_name,
            image_pull_policy="IfNotPresent",
            command=["tail", "-f", "/dev/null"],
            env=env_list,
            ports=container_ports if container_ports else None,
            volume_mounts=volume_mounts if volume_mounts else None,
            resources=resources,
            working_dir=spec.working_dir or "/workspace",
        )

        pod = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels=labels,
                annotations=annotations,
            ),
            spec=V1PodSpec(
                containers=[container],
                volumes=volumes if volumes else None,
                restart_policy="Always",
            ),
        )

        # 7. Service definition (if ports are present)
        service = None
        if spec.ports:
            svc_ports = [
                V1ServicePort(
                    name=f"p-{port}"[:15],
                    port=port,
                    target_port=port,
                )
                for port in spec.ports
            ]
            service = V1Service(
                metadata=V1ObjectMeta(
                    name=svc_name,
                    namespace=self.namespace,
                    labels=labels,
                    annotations=annotations,
                ),
                spec=V1ServiceSpec(
                    selector={"compassx.sandbox-id": clean_sb_id},
                    ports=svc_ports,
                    type="ClusterIP",
                ),
            )

        # Check if existing Pod is already Running / Pending (reuse compute without recreating)
        try:
            existing_pod = k8s.core().read_namespaced_pod(name=pod_name, namespace=self.namespace)
            if existing_pod and existing_pod.status:
                phase = (existing_pod.status.phase or "").lower()
                deletion = existing_pod.metadata and existing_pod.metadata.deletion_timestamp
                if phase in ("running", "pending") and not deletion:
                    logger.info("K8s sandbox pod %s already exists in phase %s, reusing.", pod_name, phase)
                    if service:
                        try:
                            k8s.core().read_namespaced_service(name=svc_name, namespace=self.namespace)
                        except Exception:
                            try:
                                k8s.core().create_namespaced_service(namespace=self.namespace, body=service)
                            except Exception:
                                pass
                    endpoints = {
                        str(port): f"http://{svc_name}.{self.namespace}.svc.cluster.local:{port}"
                        for port in spec.ports
                    }
                    return SandboxInstance(
                        id=spec.sandbox_id or sandbox_id,
                        name=spec.name,
                        consumer_key=spec.consumer_key,
                        consumer_module=spec.consumer_module,
                        workspace_id=spec.workspace_id,
                        status=SandboxStatus.RUNNING if phase == "running" else SandboxStatus.PROVISIONING,
                        runtime_mode="kubernetes",
                        image=image_name,
                        pod_name=pod_name,
                        endpoints=endpoints,
                        ports=spec.ports,
                        working_dir=spec.working_dir or "/workspace",
                        created_at=existing_pod.metadata.creation_timestamp.isoformat() if existing_pod.metadata and existing_pod.metadata.creation_timestamp else datetime.now(timezone.utc).isoformat(),
                        started_at=datetime.now(timezone.utc).isoformat(),
                        labels=labels,
                        metadata=spec.metadata,
                    )
        except Exception:
            pass

        # Delete stale/failed Pod & Service if present
        try:
            k8s.core().delete_namespaced_pod(name=pod_name, namespace=self.namespace, grace_period_seconds=0)
            time.sleep(0.5)
        except Exception:
            pass

        if service:
            try:
                k8s.core().delete_namespaced_service(name=svc_name, namespace=self.namespace)
            except Exception:
                pass

        # Create Pod & Service
        k8s.core().create_namespaced_pod(namespace=self.namespace, body=pod)
        if service:
            try:
                k8s.core().create_namespaced_service(namespace=self.namespace, body=service)
            except Exception as svc_err:
                logger.debug("Could not create K8s service %s: %s", svc_name, svc_err)

        # Wait up to 10s for pod to reach Running phase
        pod_phase = "Pending"
        for _ in range(10):
            try:
                live_pod = k8s.core().read_namespaced_pod(name=pod_name, namespace=self.namespace)
                phase = (live_pod.status.phase or "") if live_pod.status else ""
                if phase:
                    pod_phase = phase
                if phase == "Running":
                    break
            except Exception:
                pass
            time.sleep(1)

        # Resolve status
        if pod_phase == "Running":
            sb_status = SandboxStatus.RUNNING
        elif pod_phase in ("Failed", "Unknown"):
            sb_status = SandboxStatus.FAILED
        else:
            sb_status = SandboxStatus.PROVISIONING

        # Resolve endpoints
        endpoints = {}
        for port in spec.ports:
            # Cluster internal URL
            endpoints[str(port)] = f"http://{svc_name}.{self.namespace}.svc.cluster.local:{port}"

        instance = SandboxInstance(
            id=spec.sandbox_id or sandbox_id,
            name=spec.name,
            consumer_key=spec.consumer_key,
            consumer_module=spec.consumer_module,
            workspace_id=spec.workspace_id,
            status=sb_status,
            runtime_mode="kubernetes",
            image=image_name,
            pod_name=pod_name,
            endpoints=endpoints,
            ports=spec.ports,
            working_dir=spec.working_dir or "/workspace",
            created_at=datetime.now(timezone.utc).isoformat(),
            started_at=datetime.now(timezone.utc).isoformat(),
            labels=labels,
            metadata=spec.metadata,
        )
        return instance

    def terminate(self, instance: SandboxInstance) -> bool:
        """Delete Pod and Service in Kubernetes."""
        try:
            k8s = get_k8s_client()
            clean_sb_id = _sanitize_k8s_name(instance.id)
            pod_name = instance.pod_name or f"compassx-sb-{clean_sb_id}"
            svc_name = f"compassx-sb-{clean_sb_id}"

            try:
                k8s.core().delete_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                    grace_period_seconds=0,
                )
            except Exception as pe:
                logger.debug("Error deleting pod %s: %s", pod_name, pe)

            try:
                k8s.core().delete_namespaced_service(
                    name=svc_name,
                    namespace=self.namespace,
                )
            except Exception:
                pass

            instance.status = SandboxStatus.TERMINATED
            instance.stopped_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as exc:
            logger.warning("Error deleting K8s sandbox %s: %s", instance.id, exc)
            return False

    def suspend(self, instance: SandboxInstance) -> bool:
        """Suspend compute by deleting the Pod while retaining metadata."""
        ok = self.terminate(instance)
        if ok:
            instance.status = SandboxStatus.SUSPENDED
        return ok

    def resume(self, instance: SandboxInstance) -> bool:
        """Re-create the Pod and Service."""
        spec = SandboxSpec(
            sandbox_id=instance.id,
            consumer_key=instance.consumer_key,
            name=instance.name,
            consumer_module=instance.consumer_module,
            workspace_id=instance.workspace_id,
            image=instance.image,
            ports=instance.ports,
            working_dir=instance.working_dir,
            labels=instance.labels,
            metadata=instance.metadata,
        )
        try:
            new_instance = self.provision(spec)
            instance.status = SandboxStatus.RUNNING
            instance.pod_name = new_instance.pod_name
            instance.endpoints = new_instance.endpoints
            return True
        except Exception as exc:
            logger.warning("Error resuming K8s sandbox %s: %s", instance.id, exc)
            return False

    def get_status(self, instance: SandboxInstance) -> SandboxStatus:
        """Query Kubernetes Pod status."""
        try:
            k8s = get_k8s_client()
            clean_sb_id = _sanitize_k8s_name(instance.id)
            pod_name = instance.pod_name or f"compassx-sb-{clean_sb_id}"
            pod = k8s.core().read_namespaced_pod(name=pod_name, namespace=self.namespace)
            if not pod or not pod.status:
                return SandboxStatus.TERMINATED

            if pod.metadata and pod.metadata.deletion_timestamp:
                return SandboxStatus.TERMINATED

            # Check container statuses
            for c_status in (pod.status.container_statuses or []):
                if c_status.state:
                    if c_status.state.waiting:
                        reason = c_status.state.waiting.reason or ""
                        if reason in ("CrashLoopBackOff", "ErrImagePull", "ImagePullBackOff", "Error"):
                            return SandboxStatus.FAILED
                    if c_status.state.terminated:
                        if c_status.state.terminated.exit_code != 0:
                            return SandboxStatus.FAILED

            phase = (pod.status.phase or "").lower()
            if phase == "running":
                return SandboxStatus.RUNNING
            elif phase == "pending":
                return SandboxStatus.PROVISIONING
            elif phase in ("failed", "unknown"):
                return SandboxStatus.FAILED
            elif phase == "succeeded":
                return SandboxStatus.STOPPED
        except Exception:
            return SandboxStatus.TERMINATED
        return SandboxStatus.RUNNING

    def exec_command(
        self,
        instance: SandboxInstance,
        command: str | List[str],
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute command inside Kubernetes pod via k8s_stream with exit code verification."""
        from kubernetes import stream as k8s_stream

        start_time = time.time()
        k8s = get_k8s_client()
        clean_sb_id = _sanitize_k8s_name(instance.id)
        pod_name = instance.pod_name or f"compassx-sb-{clean_sb_id}"

        # 1. Format shell command with environment exports and working directory
        if isinstance(command, list):
            import shlex
            cmd_str = " ".join(shlex.quote(c) for c in command)
        else:
            cmd_str = command

        env_parts = []
        if env:
            for k, v in env.items():
                if k:
                    env_parts.append(f"export {k}='{v}';")
        env_prefix = " ".join(env_parts) + (" " if env_parts else "")

        target_dir = working_dir or instance.working_dir or "/workspace"
        cd_prefix = f"cd '{target_dir}' && " if target_dir else ""

        # Wrap with explicit exit code marker
        wrapped_script = (
            f"{env_prefix}{cd_prefix}( {cmd_str} )\n"
            f"__CX_CODE__=$?\n"
            f"echo \"\n__CX_EXIT_CODE__:$__CX_CODE__\"\n"
            f"exit $__CX_CODE__"
        )
        exec_cmd = ["/bin/sh", "-c", wrapped_script]

        try:
            resp = k8s_stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                self.namespace,
                command=exec_cmd,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=timeout,
            )
            duration = round(time.time() - start_time, 3)
            raw_out = resp or ""

            # Parse exit code from marker
            exit_code = 0
            clean_stdout = raw_out
            if "__CX_EXIT_CODE__:" in raw_out:
                parts = raw_out.rsplit("__CX_EXIT_CODE__:", 1)
                clean_stdout = parts[0].rstrip("\r\n")
                try:
                    code_str = parts[1].strip().splitlines()[0]
                    exit_code = int(code_str)
                except Exception:
                    exit_code = 0

            return ExecResult(
                exit_code=exit_code,
                stdout=clean_stdout,
                stderr="" if exit_code == 0 else f"Command exited with code {exit_code}",
                duration_seconds=duration,
                success=(exit_code == 0),
            )
        except Exception as exc:
            duration = round(time.time() - start_time, 3)
            return ExecResult(
                exit_code=1,
                stderr=f"K8s exec failed: {exc}",
                duration_seconds=duration,
                success=False,
            )

    def get_logs(self, instance: SandboxInstance, max_lines: int = 200) -> str:
        """Fetch Pod logs and recent lifecycle events."""
        k8s = get_k8s_client()
        clean_sb_id = _sanitize_k8s_name(instance.id)
        pod_name = instance.pod_name or f"compassx-sb-{clean_sb_id}"
        logs = ""
        try:
            logs = k8s.core().read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                tail_lines=max_lines,
            ) or ""
        except Exception as exc:
            logs = f"[Error fetching K8s logs: {exc}]"

        # Check pod events if logs are empty
        if not logs or logs.startswith("[Error"):
            try:
                evs = k8s.core().list_namespaced_event(
                    namespace=self.namespace,
                    field_selector=f"involvedObject.name={pod_name}",
                )
                if evs and evs.items:
                    sorted_evs = sorted(
                        evs.items,
                        key=lambda ev: ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
                    )
                    ev_lines = []
                    for ev in sorted_evs:
                        ts = ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp
                        ts_str = ts.strftime("%H:%M:%S") if ts and hasattr(ts, "strftime") else "EVENT"
                        ev_lines.append(f"[{ts_str}] [{ev.reason or 'Event'}] {ev.message or ''}")
                    if ev_lines:
                        logs = "\n".join(ev_lines)
            except Exception:
                pass

        return logs

    async def stream_logs(self, instance: SandboxInstance, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        """Stream Pod logs."""
        from compute.logs import stream_pod_logs
        clean_sb_id = _sanitize_k8s_name(instance.id)
        pod_name = instance.pod_name or f"compassx-sb-{clean_sb_id}"
        try:
            async for line in stream_pod_logs(pod_name=pod_name, namespace=self.namespace, tail_lines=tail_lines):
                yield line
        except Exception as exc:
            yield f"[Log stream error: {exc}]\n"

    def get_endpoints(self, instance: SandboxInstance) -> Dict[str, str]:
        return instance.endpoints

    def discover_active_instances(self) -> List[SandboxInstance]:
        """Scan Kubernetes cluster for sandbox pods."""
        instances = []
        try:
            k8s = get_k8s_client()
            pod_list = k8s.core().list_namespaced_pod(
                namespace=self.namespace,
                label_selector="compassx.sandbox=true",
            )
            for pod in pod_list.items:
                if pod.metadata and pod.metadata.deletion_timestamp:
                    continue

                labels = pod.metadata.labels or {}
                annotations = pod.metadata.annotations or {}
                sb_id = (
                    annotations.get("compassx.sandbox.id")
                    or labels.get("compassx.sandbox-id")
                    or pod.metadata.name.replace("compassx-sb-", "")
                )
                sb_name = annotations.get("compassx.sandbox.name") or pod.metadata.name
                consumer = (
                    annotations.get("compassx.sandbox.consumer_module")
                    or labels.get("compassx.consumer-module")
                    or "generic"
                )
                consumer_key = annotations.get("compassx.sandbox.consumer_key") or labels.get("compassx.consumer-key")
                ws_id = annotations.get("compassx.sandbox.workspace_id") or labels.get("compassx.workspace-id")
                phase = (pod.status.phase or "").lower() if pod.status else "unknown"
                status = SandboxStatus.RUNNING if phase == "running" else (
                    SandboxStatus.PROVISIONING if phase == "pending" else SandboxStatus.FAILED
                )
                image = pod.spec.containers[0].image if pod.spec and pod.spec.containers else None
                created_at = pod.metadata.creation_timestamp.isoformat() if pod.metadata and pod.metadata.creation_timestamp else ""

                # Ports & Endpoints
                ports = []
                endpoints = {}
                svc_name = pod.metadata.name
                if pod.spec and pod.spec.containers:
                    for c in pod.spec.containers:
                        for p in (c.ports or []):
                            ports.append(p.container_port)
                            endpoints[str(p.container_port)] = f"http://{svc_name}.{self.namespace}.svc.cluster.local:{p.container_port}"

                instances.append(
                    SandboxInstance(
                        id=sb_id,
                        name=sb_name,
                        consumer_key=consumer_key,
                        consumer_module=consumer,
                        workspace_id=ws_id,
                        status=status,
                        runtime_mode="kubernetes",
                        image=image,
                        pod_name=pod.metadata.name,
                        endpoints=endpoints,
                        ports=ports,
                        created_at=created_at,
                        labels=labels,
                    )
                )
        except Exception as exc:
            logger.debug("K8s sandbox discovery failed: %s", exc)
        return instances

