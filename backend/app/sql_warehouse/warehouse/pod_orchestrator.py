"""Warehouse Pod Orchestrator.

Manages the lifecycle of isolated containerized SQL Warehouse pods (DuckDB and ClickHouse)
across Docker and Kubernetes environments using CompassX platform drivers.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import httpx

from compassx.models.runtime import PortMapping, ResourceRequirements, RuntimePhase, RuntimeSpec
from compute.config import compute_settings

logger = logging.getLogger("warehouse_orchestrator")


class WarehousePodOrchestrator:
    """Orchestrates provisioning, starting, stopping, and deleting warehouse containers."""

    def __init__(self, platform=None):
        self._platform = platform

    def _get_platform(self):
        if self._platform is not None:
            return self._platform
        try:
            from compassx.container import PlatformContainer
            return PlatformContainer()
        except Exception as exc:
            logger.debug("PlatformContainer not available: %s", exc)
            return None

    def _get_driver(self):
        platform = self._get_platform()
        if not platform:
            return None
        try:
            driver_env = os.environ.get("COMPASSX_PLATFORM_DRIVER") or getattr(compute_settings, "COMPASSX_PLATFORM_DRIVER", None)
            is_k8s = compute_settings.is_k8s() if hasattr(compute_settings, "is_k8s") else not getattr(compute_settings, "is_local", lambda: True)()
            driver_name = driver_env or ("kubernetes" if is_k8s else "docker")
            return platform.driver_registry.get(driver_name)
        except Exception as exc:
            logger.debug("Driver unavailable in WarehousePodOrchestrator: %s", exc)
            return None

    def _build_runtime_id(self, warehouse_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]+", "", warehouse_id.lower())
        return f"wh-{clean[:16]}"

    def _build_spec(self, warehouse) -> RuntimeSpec:
        runtime_id = self._build_runtime_id(warehouse.id)
        engine = (warehouse.engine or "duckdb").lower()
        secret = os.environ.get("COMPASSX_INTERNAL_SECRET", "")

        env = {
            "COMPASSX_INTERNAL_SECRET": secret,
            "WAREHOUSE_ID": str(warehouse.id),
            "WAREHOUSE_NAME": str(warehouse.name),
            "WORKSPACE_ID": str(warehouse.workspace_id or ""),
            "AWS_ENDPOINT_URL": f"http://{compute_settings.MINIO_ENDPOINT}",
            "AWS_ACCESS_KEY_ID": compute_settings.MINIO_ACCESS_KEY,
            "AWS_SECRET_ACCESS_KEY": compute_settings.MINIO_SECRET_KEY,
            "AWS_DEFAULT_REGION": "us-east-1",
        }

        # Resource policy parameters (limits/requests)
        policy = warehouse.resource_policy or {}
        max_memory = policy.get("max_memory_mb")
        max_threads = policy.get("max_threads")
        memory_limit = f"{max_memory}Mi" if max_memory else "2Gi"
        cpu_limit = f"{max_threads}" if max_threads else "2"
        resources = ResourceRequirements(
            cpu_request="500m",
            cpu_limit=cpu_limit,
            memory_request="512Mi",
            memory_limit=memory_limit,
        )

        labels = {
            "compassx/resource-type": "warehouse",
            "compassx/warehouse-id": str(warehouse.id),
            "compassx/workspace-id": str(warehouse.workspace_id or ""),
            "compassx/engine": engine,
        }

        if engine == "duckdb":
            image = os.environ.get(
                "COMPASSX_DUCKDB_WAREHOUSE_IMAGE",
                "ghcr.io/compassx-platform/compute-duckdb:v0.15.4",
            )
            ports = [PortMapping(name="http", container_port=8080)]
            command = ["uvicorn", "services.warehouse_daemon.server:app", "--host", "0.0.0.0", "--port", "8080"]
        elif engine == "clickhouse":
            image = os.environ.get(
                "COMPASSX_CLICKHOUSE_WAREHOUSE_IMAGE",
                "clickhouse/clickhouse-server:24.3-alpine",
            )
            ports = [
                PortMapping(name="http", container_port=8123),
                PortMapping(name="native", container_port=9000),
            ]
            command = []
        else:
            image = "python:3.11-slim"
            ports = [PortMapping(name="http", container_port=8080)]
            command = []

        return RuntimeSpec(
            runtime_id=runtime_id,
            runtime_type=f"warehouse-{engine}",
            container_image=image,
            command=command,
            resources=resources,
            env=env,
            ports=ports,
            labels=labels,
            namespace=os.environ.get("COMPASSX_K8S_NAMESPACE", getattr(compute_settings, "COMPASSX_NAMESPACE", "compassx")),
            workspace_id=str(warehouse.workspace_id or ""),
            metadata={"warehouse_id": str(warehouse.id), "resource_name": f"wh-{warehouse.name}"},
        )

    def _resolve_endpoint(self, warehouse, runtime_id: str) -> str:
        engine = (warehouse.engine or "duckdb").lower()
        port = 8123 if engine == "clickhouse" else 8080

        # In Kubernetes, the deployment has a service: <deployment-name>.<namespace>.svc.cluster.local
        is_k8s = compute_settings.is_k8s() if hasattr(compute_settings, "is_k8s") else not getattr(compute_settings, "is_local", lambda: True)()
        if is_k8s:
            ns = os.environ.get("COMPASSX_K8S_NAMESPACE", getattr(compute_settings, "COMPASSX_NAMESPACE", "compassx"))
            return f"http://compassx-{runtime_id}.{ns}.svc.cluster.local:{port}"

        # In Docker Compose, the container name is accessible on the compose network
        platform = self._get_platform()
        proj = platform.profile.compose_project if platform and hasattr(platform, "profile") else "compassx"
        return f"http://{proj}-{runtime_id}:{port}"

    def _ensure_k8s_service(self, runtime_id: str, port: int, ns: str, warehouse):
        try:
            from kubernetes import client
            from app.compute.services.k8s_client import get_k8s_client
            k8s = get_k8s_client()
            core = k8s.core() if hasattr(k8s, "core") else client.CoreV1Api()
            svc_name = f"compassx-{runtime_id}"

            svc_ports = [
                client.V1ServicePort(
                    name="http",
                    port=port,
                    target_port=port,
                    protocol="TCP",
                )
            ]
            if (warehouse.engine or "").lower() == "clickhouse":
                svc_ports.append(
                    client.V1ServicePort(
                        name="native",
                        port=9000,
                        target_port=9000,
                        protocol="TCP",
                    )
                )

            labels = {
                "compassx/resource-type": "warehouse",
                "compassx/runtime-id": runtime_id,
                "compassx/warehouse-id": str(warehouse.id),
                "compassx/engine": (warehouse.engine or "duckdb").lower(),
            }

            body = client.V1Service(
                metadata=client.V1ObjectMeta(
                    name=svc_name,
                    namespace=ns,
                    labels=labels,
                ),
                spec=client.V1ServiceSpec(
                    selector={"compassx/runtime-id": runtime_id},
                    ports=svc_ports,
                    type="ClusterIP",
                ),
            )
            try:
                core.read_namespaced_service(name=svc_name, namespace=ns)
            except Exception:
                core.create_namespaced_service(namespace=ns, body=body)
                logger.info("Created K8s Service %s in namespace %s", svc_name, ns)
        except Exception as exc:
            logger.warning("Could not ensure K8s Service %s: %s", runtime_id, exc)

    def _delete_k8s_service(self, runtime_id: str, ns: str):
        try:
            from kubernetes import client
            from app.compute.services.k8s_client import get_k8s_client
            k8s = get_k8s_client()
            core = k8s.core() if hasattr(k8s, "core") else client.CoreV1Api()
            svc_name = f"compassx-{runtime_id}"
            core.delete_namespaced_service(name=svc_name, namespace=ns)
            logger.info("Deleted K8s Service %s in namespace %s", svc_name, ns)
        except Exception:
            pass

    async def start_pod(self, warehouse) -> tuple[str, str]:
        """Provisions and starts the warehouse pod/container.
        
        Returns (runtime_id, endpoint_url).
        """
        driver = self._get_driver()
        runtime_id = self._build_runtime_id(warehouse.id)
        endpoint = self._resolve_endpoint(warehouse, runtime_id)

        if not driver:
            logger.warning("No platform driver available to provision warehouse pod %s. Using default endpoint.", warehouse.id)
            return runtime_id, endpoint

        try:
            spec = self._build_spec(warehouse)
            # Create runtime
            await driver.create_runtime(spec)
            logger.info("Created warehouse runtime %s (engine=%s)", runtime_id, warehouse.engine)

            # If running on Kubernetes, ensure Service exists for cluster DNS routing
            is_k8s = compute_settings.is_k8s() if hasattr(compute_settings, "is_k8s") else not getattr(compute_settings, "is_local", lambda: True)()
            if is_k8s:
                ns = os.environ.get("COMPASSX_K8S_NAMESPACE", getattr(compute_settings, "COMPASSX_NAMESPACE", "compassx"))
                port = 8123 if (warehouse.engine or "").lower() == "clickhouse" else 8080
                self._ensure_k8s_service(runtime_id=runtime_id, port=port, ns=ns, warehouse=warehouse)

            # Wait briefly for readiness (up to 15s) so first query doesn't hit a booting container
            await self.poll_readiness(endpoint, warehouse.engine or "duckdb", timeout_sec=15)

            return runtime_id, endpoint
        except Exception as exc:
            logger.error("Failed to provision warehouse runtime %s: %s", runtime_id, exc)
            return runtime_id, endpoint

    async def stop_pod(self, warehouse) -> bool:
        """Stops the warehouse pod/container."""
        driver = self._get_driver()
        runtime_id = warehouse.runtime_id or self._build_runtime_id(warehouse.id)
        if not driver:
            return True
        try:
            await driver.stop_runtime(runtime_id)
            logger.info("Stopped warehouse runtime %s", runtime_id)
            return True
        except Exception as exc:
            logger.debug("Failed stopping warehouse runtime %s: %s", runtime_id, exc)
            return False

    async def delete_pod(self, warehouse) -> bool:
        """Deletes the warehouse pod/container."""
        driver = self._get_driver()
        runtime_id = warehouse.runtime_id or self._build_runtime_id(warehouse.id)
        is_k8s = compute_settings.is_k8s() if hasattr(compute_settings, "is_k8s") else not getattr(compute_settings, "is_local", lambda: True)()
        if is_k8s:
            ns = os.environ.get("COMPASSX_K8S_NAMESPACE", getattr(compute_settings, "COMPASSX_NAMESPACE", "compassx"))
            self._delete_k8s_service(runtime_id=runtime_id, ns=ns)

        if not driver:
            return True
        try:
            await driver.delete_runtime(runtime_id)
            logger.info("Deleted warehouse runtime %s", runtime_id)
            return True
        except Exception as exc:
            logger.debug("Failed deleting warehouse runtime %s: %s", runtime_id, exc)
            return False

    async def poll_readiness(self, endpoint_url: str, engine: str, timeout_sec: int = 15) -> bool:
        """Polls the warehouse HTTP endpoint until ready or timeout expires."""
        health_path = "/ping" if engine == "clickhouse" else "/healthz"
        url = f"{endpoint_url.rstrip('/')}{health_path}"

        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=2.0) as client:
            while (asyncio.get_event_loop().time() - start) < timeout_sec:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        return False
