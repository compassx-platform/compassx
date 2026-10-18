"""Databricks Omnigent platform service manager."""
import json
import logging
import os
import subprocess
import time
import urllib.request
from typing import Dict, Any, Optional, Tuple

from app.config import settings
from app.services.ingress_service import ingress_service
from services.base import BaseServiceManager, ServicePhase, ServiceResourceUsage, ServiceStatus
from services.omnigent.config import omnigent_settings
from services.omnigent.manifests import (
    build_omnigent_pvc,
    build_omnigent_deployment,
    build_omnigent_service,
    build_omnigent_ingress,
)

logger = logging.getLogger(__name__)


class OmnigentManager(BaseServiceManager):
    """Lifecycle manager for the Databricks Omnigent server service across Docker and Kubernetes."""

    def _get_k8s_client(self):
        try:
            from compute.k8s_client import get_k8s_client
            return get_k8s_client()
        except Exception:
            return None

    def _is_docker_available(self) -> bool:
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
            return res.returncode == 0
        except Exception:
            return False

    def _get_container_state(self) -> Tuple[bool, str]:
        if not self._is_docker_available():
            return False, "docker_unavailable"
        res = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", omnigent_settings.OMNIGENT_CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return False, "not_found"
        state = (res.stdout or "").strip().lower()
        return state == "running", state

    def _get_llm_env_vars(self) -> Dict[str, str]:
        from app.services.omnigent_dev_service import omnigent_dev_service
        return omnigent_dev_service.get_llm_env_vars()

    def start(self) -> ServiceStatus:
        """Start the Omnigent Server container or Kubernetes deployment on-demand."""
        if ingress_service.is_kubernetes():
            k8s = self._get_k8s_client()
            if k8s:
                ns = settings.K8S_NAMESPACE
                domain = ingress_service.get_omnigent_domain()
                llm_env = self._get_llm_env_vars()
                from kubernetes.client.exceptions import ApiException

                pvc = build_omnigent_pvc(ns)
                dep = build_omnigent_deployment(ns, "cloud", llm_env=llm_env)
                svc = build_omnigent_service(ns, "cloud")
                ing = build_omnigent_ingress(ns, "cloud", domain)

                # If already deployed in K8s but suspended with 0 replicas, scale up to 1
                try:
                    existing_dep = k8s.apps().read_namespaced_deployment(name=omnigent_settings.OMNIGENT_CONTAINER_NAME, namespace=ns)
                    if existing_dep and existing_dep.spec and existing_dep.spec.replicas == 0:
                        k8s.apps().patch_namespaced_deployment(
                            name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
                            namespace=ns,
                            body={"spec": {"replicas": 1}},
                        )
                        logger.info("Resumed suspended Omnigent server in Kubernetes (scaled replicas to 1)")
                        return ServiceStatus(
                            phase=ServicePhase.RUNNING,
                            message=f"Omnigent server resumed in Kubernetes (Ingress: {domain}).",
                            details=self._details(ready=True, suspended=False),
                        )
                except ApiException as check_err:
                    if check_err.status != 404:
                        pass
                except Exception:
                    pass

                try:
                    if pvc:
                        try:
                            k8s.core().create_namespaced_persistent_volume_claim(namespace=ns, body=pvc)
                        except ApiException as e:
                            if e.status != 409:
                                pass
                    try:
                        k8s.apps().replace_namespaced_deployment(name=omnigent_settings.OMNIGENT_CONTAINER_NAME, namespace=ns, body=dep)
                    except ApiException as e:
                        if e.status == 404:
                            k8s.apps().create_namespaced_deployment(namespace=ns, body=dep)
                    try:
                        k8s.core().replace_namespaced_service(name=omnigent_settings.OMNIGENT_CONTAINER_NAME, namespace=ns, body=svc)
                    except ApiException as e:
                        if e.status == 404:
                            k8s.core().create_namespaced_service(namespace=ns, body=svc)
                    try:
                        k8s.networking().replace_namespaced_ingress(name=f"{omnigent_settings.OMNIGENT_CONTAINER_NAME}-ingress", namespace=ns, body=ing)
                    except ApiException as e:
                        if e.status == 404:
                            k8s.networking().create_namespaced_ingress(namespace=ns, body=ing)

                    return ServiceStatus(
                        phase=ServicePhase.RUNNING,
                        message=f"Omnigent server deployed to Kubernetes (Ingress: {domain}).",
                        details=self._details(ready=True)
                    )
                except Exception as exc:
                    logger.warning("Kubernetes Omnigent deployment error: %s", exc)

        running, state = self._get_container_state()
        if running:
            return ServiceStatus(
                phase=ServicePhase.RUNNING,
                message="Omnigent server is already running.",
                details=self._details()
            )

        if not self._is_docker_available():
            return ServiceStatus(
                phase=ServicePhase.ERROR,
                message="Docker daemon is not available to start Omnigent server.",
                details=self._details()
            )

        try:
            if state in ("exited", "stopped", "created", "paused"):
                subprocess.run(["docker", "start", omnigent_settings.OMNIGENT_CONTAINER_NAME], capture_output=True, text=True, check=False)
            else:
                # Remove any leftover broken container
                subprocess.run(["docker", "rm", "-f", omnigent_settings.OMNIGENT_CONTAINER_NAME], capture_output=True, text=True, check=False)

                # Detect network
                net_check = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True, check=False)
                network = "compassx_default" if "compassx_default" in net_check.stdout else "bridge"
                db_host = "postgres" if network == "compassx_default" else "host.docker.internal:5433"

                cmd = [
                    "docker", "run", "-d",
                    "--name", omnigent_settings.OMNIGENT_CONTAINER_NAME,
                    "--network", network,
                    "-p", f"{omnigent_settings.OMNIGENT_PORT}:6767",
                    "-e", "PORT=6767",
                    "-e", "HOST=0.0.0.0",
                    "-e", f"DATABASE_URL=postgresql://postgres:postgres@{db_host}/omnigent",
                    "-e", "OMNIGENT_AUTH_PROVIDER=header",
                    "-e", "OMNIGENT_LOCAL_SINGLE_USER=1",
                    "-e", "ARTIFACT_DIR=/data/artifacts",
                ]

                # Pass LLM keys, CA certs & TLS configs
                llm_env = self._get_llm_env_vars()
                for k, v in llm_env.items():
                    cmd.extend(["-e", f"{k}={v}"])

                cmd.extend([
                    "-v", f"{omnigent_settings.OMNIGENT_VOLUME_NAME}:/data",
                    "--restart", "unless-stopped",
                    omnigent_settings.OMNIGENT_IMAGE
                ])

                subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Wait up to 5s for health endpoint to respond
            for _ in range(10):
                time.sleep(0.5)
                stat = self.get_status()
                if stat.phase == ServicePhase.RUNNING:
                    return stat

            return ServiceStatus(
                phase=ServicePhase.STARTING,
                message="Omnigent server starting in background.",
                details=self._details()
            )
        except Exception as exc:
            logger.exception("Failed to start Omnigent server: %s", exc)
            return ServiceStatus(
                phase=ServicePhase.ERROR,
                message=f"Failed to start Omnigent server: {exc}",
                details=self._details()
            )

    def suspend(self) -> ServiceStatus:
        """Suspend Omnigent Server compute (scale deployment to 0 replicas or stop Docker container) while keeping persistent data/PVC intact."""
        if ingress_service.is_kubernetes():
            k8s = self._get_k8s_client()
            if k8s:
                ns = settings.K8S_NAMESPACE
                try:
                    k8s.apps().patch_namespaced_deployment(
                        name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
                        namespace=ns,
                        body={"spec": {"replicas": 0}},
                    )
                    logger.info("Suspended Omnigent Server in Kubernetes (scaled replicas to 0)")
                    return ServiceStatus(
                        phase=ServicePhase.STOPPED,
                        message="Omnigent server suspended (scaled replicas to 0).",
                        details=self._details(ready=False, suspended=True),
                    )
                except Exception as e:
                    logger.warning("Could not scale down Omnigent deployment to 0: %s", e)

        if self._is_docker_available():
            subprocess.run(["docker", "stop", omnigent_settings.OMNIGENT_CONTAINER_NAME], capture_output=True, text=True, check=False)

        return ServiceStatus(
            phase=ServicePhase.STOPPED,
            message="Omnigent server suspended.",
            details=self._details(ready=False, suspended=True),
        )

    def stop(self) -> ServiceStatus:
        """Stop/suspend the Omnigent Server container or deployment without terminating data."""
        return self.suspend()

    def restart(self) -> ServiceStatus:
        """Restart the Omnigent Server container."""
        if self._is_docker_available():
            subprocess.run(["docker", "restart", omnigent_settings.OMNIGENT_CONTAINER_NAME], capture_output=True, text=True, check=False)
            time.sleep(1.5)
        return self.get_status()

    def get_status(self) -> ServiceStatus:
        """Probe HTTP health and container status for Omnigent Server."""
        url = omnigent_settings.OMNIGENT_SERVER_URL.rstrip("/")
        version_str = "Databricks Omnigent"

        try:
            req = urllib.request.Request(f"{url}/v1/info", headers={"User-Agent": "CompassX/1.0"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    ver = data.get("server_version") or "0.12.0"
                    version_str = f"v{ver} (Databricks Omnigent)"
                    return ServiceStatus(
                        phase=ServicePhase.RUNNING,
                        message="Omnigent server running.",
                        details=self._details(version=version_str, ready=True, suspended=False),
                    )
        except Exception:
            pass

        try:
            req = urllib.request.Request(f"{url}/health", headers={"User-Agent": "CompassX/1.0"})
            with urllib.request.urlopen(req, timeout=1.2) as resp:
                if resp.status in (200, 204):
                    return ServiceStatus(
                        phase=ServicePhase.RUNNING,
                        message="Omnigent server running.",
                        details=self._details(version=version_str, ready=True, suspended=False),
                    )
        except Exception:
            pass

        if ingress_service.is_kubernetes():
            k8s = self._get_k8s_client()
            if k8s:
                ns = settings.K8S_NAMESPACE
                try:
                    dep = k8s.apps().read_namespaced_deployment(name=omnigent_settings.OMNIGENT_CONTAINER_NAME, namespace=ns)
                    replicas = dep.spec.replicas if (dep and dep.spec) else 1
                    if replicas == 0:
                        return ServiceStatus(
                            phase=ServicePhase.STOPPED,
                            message="Omnigent server is suspended (0 replicas).",
                            details=self._details(version=version_str, ready=False, suspended=True),
                        )
                except Exception:
                    pass

        running, state = self._get_container_state()
        if running:
            return ServiceStatus(
                phase=ServicePhase.STARTING,
                message="Omnigent server container is running, waiting for HTTP readiness.",
                details=self._details(version=version_str, ready=False, suspended=False),
            )
        elif state == "not_found":
            return ServiceStatus(
                phase=ServicePhase.STOPPED,
                message="Omnigent server container not created (on-demand).",
                details=self._details(version=version_str, ready=False, suspended=False),
            )
        else:
            is_susp = state in ("exited", "stopped", "paused")
            return ServiceStatus(
                phase=ServicePhase.STOPPED,
                message=f"Omnigent server is suspended (container state: {state})." if is_susp else f"Omnigent server is stopped (container state: {state}).",
                details=self._details(version=version_str, ready=False, suspended=is_susp),
            )

    def get_resource_usage(self) -> ServiceResourceUsage:
        if not self._is_docker_available():
            return ServiceResourceUsage(metrics_available=False)
        try:
            res = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", omnigent_settings.OMNIGENT_CONTAINER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split("|")
                # Parse memory MiB if available
                mem_str = parts[1].split("/")[0].strip() if len(parts) > 1 else ""
                return ServiceResourceUsage(metrics_available=True)
        except Exception:
            pass
        return ServiceResourceUsage(metrics_available=False)

    def _details(self, version: str = "Databricks Omnigent", ready: bool = False, suspended: bool = False) -> Dict[str, Any]:
        pub_url = ingress_service.get_omnigent_public_url()
        int_url = ingress_service.get_omnigent_internal_url()
        return {
            "service_name": "omnigent-server",
            "container_name": omnigent_settings.OMNIGENT_CONTAINER_NAME,
            "port": omnigent_settings.OMNIGENT_PORT,
            "endpoint": pub_url,
            "internal_endpoint": int_url,
            "ui_url": pub_url,
            "version": version,
            "ready": ready,
            "suspended": suspended,
        }


_omnigent_manager: Optional[OmnigentManager] = None


def get_omnigent_manager() -> OmnigentManager:
    global _omnigent_manager
    if _omnigent_manager is None:
        _omnigent_manager = OmnigentManager()
    return _omnigent_manager
