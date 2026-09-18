"""Node Pool Manager: handles AKS node pool discovery, provisioning, VM size catalog, and app pod switchovers."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Supported Azure VM Sizes Catalog with hardware specs and categorization
AZURE_VM_SIZES = [
    {
        "id": "Standard_B2s_v2",
        "name": "Standard_B2s_v2",
        "label": "Standard_B2s_v2 (2 vCPU, 4 GiB RAM)",
        "cpu": 2,
        "memory_gib": 4,
        "architecture": "x86_64",
        "category": "Burstable (General Purpose)",
        "description": "Economical burstable VM ideal for lightweight apps, dev environments, and dashboards.",
        "recommended": True,
    },
    {
        "id": "Standard_B2als_v2",
        "name": "Standard_B2als_v2",
        "label": "Standard_B2als_v2 (2 vCPU, 4 GiB RAM - ARM64)",
        "cpu": 2,
        "memory_gib": 4,
        "architecture": "arm64",
        "category": "ARM64 Ampere",
        "description": "Energy-efficient ARM64 architecture with high cost performance.",
        "recommended": False,
    },
    {
        "id": "Standard_B4ms",
        "name": "Standard_B4ms",
        "label": "Standard_B4ms (4 vCPU, 16 GiB RAM)",
        "cpu": 4,
        "memory_gib": 16,
        "architecture": "x86_64",
        "category": "Burstable Memory-Optimized",
        "description": "High memory-to-core ratio with burstable CPU for memory-heavy applications.",
        "recommended": False,
    },
    {
        "id": "Standard_D2s_v5",
        "name": "Standard_D2s_v5",
        "label": "Standard_D2s_v5 (2 vCPU, 8 GiB RAM)",
        "cpu": 2,
        "memory_gib": 8,
        "architecture": "x86_64",
        "category": "General Purpose (Dedicated)",
        "description": "Consistent performance on Intel Xeon processors for production web apps.",
        "recommended": False,
    },
    {
        "id": "Standard_D4s_v5",
        "name": "Standard_D4s_v5",
        "label": "Standard_D4s_v5 (4 vCPU, 16 GiB RAM)",
        "cpu": 4,
        "memory_gib": 16,
        "architecture": "x86_64",
        "category": "High Performance Compute",
        "description": "Production compute tier for high concurrency and heavy processing.",
        "recommended": False,
    },
    {
        "id": "Standard_D8s_v5",
        "name": "Standard_D8s_v5",
        "label": "Standard_D8s_v5 (8 vCPU, 32 GiB RAM)",
        "cpu": 8,
        "memory_gib": 32,
        "architecture": "x86_64",
        "category": "High Performance Intensive",
        "description": "Enterprise compute scale for high-load multi-tenant deployments.",
        "recommended": False,
    },
    {
        "id": "Standard_E2s_v5",
        "name": "Standard_E2s_v5",
        "label": "Standard_E2s_v5 (2 vCPU, 16 GiB RAM)",
        "cpu": 2,
        "memory_gib": 16,
        "architecture": "x86_64",
        "category": "Memory Optimized",
        "description": "Optimized for in-memory caching, analytics engines, and dataset processing.",
        "recommended": False,
    },
    {
        "id": "Standard_E4s_v5",
        "name": "Standard_E4s_v5",
        "label": "Standard_E4s_v5 (4 vCPU, 32 GiB RAM)",
        "cpu": 4,
        "memory_gib": 32,
        "architecture": "x86_64",
        "category": "Memory Optimized Enterprise",
        "description": "Large memory allocation for big data, machine learning, and cache-heavy apps.",
        "recommended": False,
    },
]


class NodePoolManager:
    """Manages Kubernetes / AKS node pool detection, provisioning, and app pod scheduling."""

    def __init__(self) -> None:
        self._provisioning_lock = threading.Lock()
        self._is_provisioning = False
        self._last_provision_message = ""

    def _get_k8s_clients(self):
        """Lazy load and return (core_v1, apps_v1) clients."""
        try:
            from app.compute.services.k8s_client import get_k8s_client
            client_wrapper = get_k8s_client()
            return client_wrapper.core(), client_wrapper.apps()
        except Exception:
            try:
                from kubernetes import client, config as k8s_config
                try:
                    k8s_config.load_incluster_config()
                except Exception:
                    k8s_config.load_kube_config()
                return client.CoreV1Api(), client.AppsV1Api()
            except Exception as e:
                logger.warning("Could not initialize Kubernetes client: %s", e)
                return None, None

    def get_vm_sizes_catalog(self) -> List[Dict[str, Any]]:
        """Return the catalog of supported VM sizes."""
        return AZURE_VM_SIZES

    def get_account_pool_settings(self) -> Dict[str, Any]:
        """Read account settings for app node pool from database."""
        try:
            from app.database import SessionLocalAccount
            from app.workspace.models import Account
            if SessionLocalAccount:
                db = SessionLocalAccount()
                try:
                    account = db.query(Account).first()
                    if account and account.settings:
                        return account.settings.get("app_node_pool") or {}
                finally:
                    db.close()
        except Exception as e:
            logger.debug("Could not read account settings for app node pool: %s", e)
        return {}

    def get_app_node_selector(self) -> Dict[str, str]:
        """Resolve the target nodeSelector for newly deployed app pods based on account settings."""
        cfg = self.get_account_pool_settings()
        dedicated = bool(cfg.get("dedicated_pool_enabled", False))
        if dedicated:
            pool_name = cfg.get("pool_name") or settings.AZURE_APP_NODEPOOL_NAME
            return {"kubernetes.azure.com/agentpool": pool_name}
        else:
            default_pool = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL
            # Route to default userpool
            return {"kubernetes.azure.com/agentpool": default_pool}

    def list_cluster_node_pools(self) -> List[Dict[str, Any]]:
        """Inspect all nodes in the cluster and group by node pool."""
        core_v1, _ = self._get_k8s_clients()
        if not core_v1:
            return []

        try:
            nodes = core_v1.list_node().items
        except Exception as e:
            logger.warning("Failed to list cluster nodes: %s", e)
            return []

        pools_map: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            labels = node.metadata.labels or {}
            pool_name = (
                labels.get("kubernetes.azure.com/agentpool")
                or labels.get("agentpool")
                or "default"
            )
            vm_size = (
                labels.get("node.kubernetes.io/instance-type")
                or labels.get("beta.kubernetes.io/instance-type")
                or "unknown"
            )
            arch = labels.get("kubernetes.io/arch") or "amd64"
            os_type = labels.get("kubernetes.io/os") or "linux"

            # Check ready status
            is_ready = False
            for cond in node.status.conditions or []:
                if cond.type == "Ready" and cond.status == "True":
                    is_ready = True
                    break

            if pool_name not in pools_map:
                pools_map[pool_name] = {
                    "name": pool_name,
                    "vm_size": vm_size,
                    "architecture": arch,
                    "os": os_type,
                    "total_nodes": 0,
                    "ready_nodes": 0,
                    "nodes": [],
                }

            pools_map[pool_name]["total_nodes"] += 1
            if is_ready:
                pools_map[pool_name]["ready_nodes"] += 1
            pools_map[pool_name]["nodes"].append({
                "name": node.metadata.name,
                "ready": is_ready,
                "vm_size": vm_size,
            })

        return list(pools_map.values())

    def get_node_pool_status(self) -> Dict[str, Any]:
        """Aggregate account settings, live K8s nodes, and provisioning state."""
        cfg = self.get_account_pool_settings()
        dedicated_enabled = bool(cfg.get("dedicated_pool_enabled", False))
        app_pool_name = cfg.get("pool_name") or settings.AZURE_APP_NODEPOOL_NAME
        default_pool_name = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL
        selected_vm_size = cfg.get("vm_size") or settings.AZURE_APP_NODEPOOL_DEFAULT_VM_SIZE
        min_count = int(cfg.get("min_count", 1))
        max_count = int(cfg.get("max_count", 5))
        auto_scale = bool(cfg.get("auto_scale", True))

        cluster_pools = self.list_cluster_node_pools()
        app_pool_info = next((p for p in cluster_pools if p["name"] == app_pool_name), None)
        user_pool_info = next((p for p in cluster_pools if p["name"] == default_pool_name), None)

        # Count currently running app workloads
        app_workloads = self.list_app_deployments_summary()

        status = "disabled"
        status_message = "App pods scheduled on shared user node pool."

        if dedicated_enabled:
            if app_pool_info and app_pool_info["ready_nodes"] > 0:
                status = "active"
                status_message = f"Dedicated pool '{app_pool_name}' active with {app_pool_info['ready_nodes']} ready node(s)."
            elif self._is_provisioning:
                status = "provisioning"
                status_message = self._last_provision_message or "Provisioning dedicated AKS node pool..."
            elif app_pool_info and app_pool_info["total_nodes"] > 0:
                status = "starting"
                status_message = f"Dedicated pool '{app_pool_name}' nodes starting ({app_pool_info['ready_nodes']}/{app_pool_info['total_nodes']} ready)."
            else:
                status = "pending"
                status_message = f"Dedicated pool '{app_pool_name}' not detected yet."

        return {
            "dedicated_pool_enabled": dedicated_enabled,
            "pool_name": app_pool_name,
            "default_pool_name": default_pool_name,
            "vm_size": selected_vm_size,
            "min_count": min_count,
            "max_count": max_count,
            "auto_scale": auto_scale,
            "status": status,
            "status_message": status_message,
            "is_provisioning": self._is_provisioning,
            "app_pool": app_pool_info,
            "user_pool": user_pool_info,
            "cluster_pools": cluster_pools,
            "app_workloads": app_workloads,
            "vm_sizes_catalog": self.get_vm_sizes_catalog(),
        }

    def list_app_deployments_summary(self) -> Dict[str, Any]:
        """List all application deployments in compassx namespace with their current node selector and target."""
        _, apps_v1 = self._get_k8s_clients()
        if not apps_v1:
            return {"total_apps": 0, "apps": []}

        ns = settings.K8S_NAMESPACE
        try:
            deps = apps_v1.list_namespaced_deployment(namespace=ns).items
        except Exception as e:
            logger.warning("Failed to list deployments in namespace %s: %s", ns, e)
            return {"total_apps": 0, "apps": []}

        app_deps = []
        for dep in deps:
            name = dep.metadata.name
            labels = dep.metadata.labels or {}
            # Match apps: either has compassx/app-id or starts with compassx-app-
            if "compassx/app-id" in labels or name.startswith("compassx-app-"):
                spec = dep.spec.template.spec
                node_selector = spec.node_selector or {}
                assigned_pool = node_selector.get("kubernetes.azure.com/agentpool") or node_selector.get("agentpool") or "unspecified"
                is_dev = labels.get("compassx/dev") == "true" or "-dev-" in name
                app_deps.append({
                    "name": name,
                    "is_dev": is_dev,
                    "replicas": dep.spec.replicas or 0,
                    "ready_replicas": dep.status.ready_replicas or 0,
                    "assigned_pool": assigned_pool,
                    "node_selector": node_selector,
                })

        return {
            "total_apps": len(app_deps),
            "apps": app_deps,
        }

    def switchover_app_workloads(self, target_pool: Optional[str] = None) -> Dict[str, Any]:
        """Update nodeSelector on all compassx app and dev deployments to roll over pods to the target pool."""
        _, apps_v1 = self._get_k8s_clients()
        if not apps_v1:
            return {"status": "error", "message": "Kubernetes client unavailable", "migrated_count": 0}

        ns = settings.K8S_NAMESPACE
        cfg = self.get_account_pool_settings()

        if target_pool is None:
            if bool(cfg.get("dedicated_pool_enabled", False)):
                target_pool = cfg.get("pool_name") or settings.AZURE_APP_NODEPOOL_NAME
            else:
                target_pool = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL

        target_selector = {"kubernetes.azure.com/agentpool": target_pool}
        now_ts = datetime.now(timezone.utc).isoformat()

        try:
            deps = apps_v1.list_namespaced_deployment(namespace=ns).items
        except Exception as e:
            logger.error("Failed to list deployments for switchover: %s", e)
            return {"status": "error", "message": str(e), "migrated_count": 0}

        migrated = []
        for dep in deps:
            name = dep.metadata.name
            labels = dep.metadata.labels or {}
            if "compassx/app-id" in labels or name.startswith("compassx-app-"):
                current_selector = dep.spec.template.spec.node_selector or {}
                # Update patch
                patch_body = {
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "compassx.io/switchover-at": now_ts,
                                }
                            },
                            "spec": {
                                "nodeSelector": target_selector,
                            }
                        }
                    }
                }
                try:
                    apps_v1.patch_namespaced_deployment(name=name, namespace=ns, body=patch_body)
                    migrated.append({
                        "name": name,
                        "previous_selector": current_selector,
                        "new_selector": target_selector,
                        "status": "patched",
                    })
                    logger.info("Migrated app deployment '%s' to node pool '%s'", name, target_pool)
                except Exception as exc:
                    logger.error("Failed to patch deployment '%s' during switchover: %s", name, exc)
                    migrated.append({
                        "name": name,
                        "error": str(exc),
                        "status": "failed",
                    })

        return {
            "status": "success",
            "target_pool": target_pool,
            "migrated_count": len([m for m in migrated if m.get("status") == "patched"]),
            "deployments": migrated,
            "timestamp": now_ts,
        }

    def trigger_provision_nodepool_async(self, vm_size: str, min_count: int = 1, max_count: int = 5, auto_scale: bool = True) -> None:
        """Asynchronously triggers AKS nodepool creation or update via az CLI in a background thread."""
        thread = threading.Thread(
            target=self._provision_nodepool_worker,
            args=(vm_size, min_count, max_count, auto_scale),
            daemon=True,
        )
        thread.start()

    def _provision_nodepool_worker(self, vm_size: str, min_count: int, max_count: int, auto_scale: bool) -> None:
        """Worker thread executing nodepool create/update command."""
        with self._provisioning_lock:
            self._is_provisioning = True
            self._last_provision_message = f"Provisioning node pool '{settings.AZURE_APP_NODEPOOL_NAME}' ({vm_size})..."
            try:
                az_path = shutil.which("az")
                if not az_path:
                    logger.warning("Azure CLI ('az') not found on system path; skipping live AKS nodepool command.")
                    self._last_provision_message = "Azure CLI not installed; nodeSelector updated for existing or external pool."
                    return

                # Check if nodepool already exists
                check_cmd = [
                    az_path, "aks", "nodepool", "show",
                    "--resource-group", settings.AZURE_RESOURCE_GROUP,
                    "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                    "--name", settings.AZURE_APP_NODEPOOL_NAME,
                    "-o", "json",
                ]
                logger.info("Checking AKS nodepool '%s'...", settings.AZURE_APP_NODEPOOL_NAME)
                res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=60)
                
                if res.returncode == 0:
                    # Node pool exists; update VM size or scaling if needed
                    logger.info("Node pool '%s' already exists on AKS. Updating parameters...", settings.AZURE_APP_NODEPOOL_NAME)
                    update_cmd = [
                        az_path, "aks", "nodepool", "update",
                        "--resource-group", settings.AZURE_RESOURCE_GROUP,
                        "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                        "--name", settings.AZURE_APP_NODEPOOL_NAME,
                        "--update-cluster-autoscaler",
                        "--min-count", str(min_count),
                        "--max-count", str(max_count),
                        "--no-wait",
                    ]
                    subprocess.run(update_cmd, capture_output=True, text=True, timeout=60)
                    self._last_provision_message = f"Node pool '{settings.AZURE_APP_NODEPOOL_NAME}' update initiated."
                else:
                    # Create nodepool
                    logger.info("Creating AKS node pool '%s' with VM size %s...", settings.AZURE_APP_NODEPOOL_NAME, vm_size)
                    create_cmd = [
                        az_path, "aks", "nodepool", "add",
                        "--resource-group", settings.AZURE_RESOURCE_GROUP,
                        "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                        "--name", settings.AZURE_APP_NODEPOOL_NAME,
                        "--node-vm-size", vm_size,
                        "--mode", "User",
                    ]
                    if auto_scale:
                        create_cmd.extend([
                            "--enable-cluster-autoscaler",
                            "--min-count", str(min_count),
                            "--max-count", str(max_count),
                        ])
                    else:
                        create_cmd.extend(["--node-count", str(min_count)])
                    create_cmd.append("--no-wait")

                    run_res = subprocess.run(create_cmd, capture_output=True, text=True, timeout=90)
                    if run_res.returncode == 0:
                        self._last_provision_message = f"Node pool '{settings.AZURE_APP_NODEPOOL_NAME}' provisioning in progress on Azure."
                        logger.info("AKS nodepool add dispatched successfully.")
                    else:
                        self._last_provision_message = f"Provisioning failed: {run_res.stderr.strip()[:200]}"
                        logger.warning("AKS nodepool add returned error: %s", run_res.stderr)
            except Exception as exc:
                logger.error("Error during node pool provisioning worker: %s", exc)
                self._last_provision_message = f"Provisioning error: {str(exc)}"
            finally:
                self._is_provisioning = False


# Singleton instance
node_pool_manager = NodePoolManager()
