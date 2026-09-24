"""Node Pool Manager: handles AKS node pool discovery, provisioning, VM size catalog, and app pod switchovers."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Supported Azure VM Sizes Catalog with hardware specs and categorization
AZURE_VM_SIZES = [
    {
        "id": "Standard_D4ads_v5",
        "name": "Standard_D4ads_v5",
        "label": "Standard_D4ads_v5 (4 vCPU, 16 GiB RAM - AMD EPYC)",
        "cpu": 4,
        "memory_gib": 16,
        "architecture": "x86_64",
        "category": "High Performance Compute",
        "description": "Production compute tier for high concurrency, fast DuckDB analytics, and heavy notebook processing.",
        "recommended": True,
    },
    {
        "id": "Standard_D2ads_v5",
        "name": "Standard_D2ads_v5",
        "label": "Standard_D2ads_v5 (2 vCPU, 8 GiB RAM - AMD EPYC)",
        "cpu": 2,
        "memory_gib": 8,
        "architecture": "x86_64",
        "category": "General Purpose (Dedicated)",
        "description": "Consistent performance for medium workloads and development sessions.",
        "recommended": False,
    },
    {
        "id": "Standard_D4s_v4",
        "name": "Standard_D4s_v4",
        "label": "Standard_D4s_v4 (4 vCPU, 16 GiB RAM - Intel Xeon)",
        "cpu": 4,
        "memory_gib": 16,
        "architecture": "x86_64",
        "category": "High Performance Intel",
        "description": "Intel Xeon powered compute tier with high memory and stable compute.",
        "recommended": False,
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
        "id": "Standard_B2s_v2",
        "name": "Standard_B2s_v2",
        "label": "Standard_B2s_v2 (2 vCPU, 4 GiB RAM)",
        "cpu": 2,
        "memory_gib": 4,
        "architecture": "x86_64",
        "category": "Burstable (General Purpose)",
        "description": "Economical burstable VM ideal for lightweight apps, dev environments, and dashboards.",
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
        self._cache_lock = threading.Lock()
        self._is_provisioning = False
        self._provisioning_action = ""  # "provisioning", "deprovisioning", or ""
        self._last_provision_message = ""
        self._aks_nodepools_cache: Dict[str, Any] = {}

    def _get_aks_nodepool_raw(self, pool_name: str) -> Optional[Dict[str, Any]]:
        """Query AKS directly via az CLI to check if the nodepool exists (useful for scale-to-zero with 0 nodes)."""
        now = time.time()
        with self._cache_lock:
            cached = self._aks_nodepools_cache.get(pool_name)
            if cached and (now - cached.get("timestamp", 0) < 20):
                return cached.get("data")

        az_path = shutil.which("az")
        if not az_path:
            return None

        try:
            cmd = [
                az_path, "aks", "nodepool", "show",
                "--resource-group", settings.AZURE_RESOURCE_GROUP,
                "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                "--name", pool_name,
                "-o", "json",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout)
                with self._cache_lock:
                    self._aks_nodepools_cache[pool_name] = {"data": data, "timestamp": now}
                return data
            else:
                with self._cache_lock:
                    self._aks_nodepools_cache[pool_name] = {"data": None, "timestamp": now}
                return None
        except Exception as exc:
            logger.debug("Could not query AKS nodepool %s: %s", pool_name, exc)
            return None

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

    def get_account_compute_settings(self) -> Dict[str, Any]:
        """Read account settings for compute node pool from database."""
        try:
            from app.database import SessionLocalAccount
            from app.workspace.models import Account
            if SessionLocalAccount:
                db = SessionLocalAccount()
                try:
                    account = db.query(Account).first()
                    if account and account.settings:
                        return account.settings.get("compute") or {}
                finally:
                    db.close()
        except Exception as e:
            logger.debug("Could not read account settings for compute: %s", e)
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
            if default_pool in ("userpoolv2", "userpool", ""):
                default_pool = settings.AZURE_DEFAULT_USER_NODEPOOL
            return {"kubernetes.azure.com/agentpool": default_pool}

    def get_compute_node_selector(self) -> Dict[str, str]:
        """Resolve the target nodeSelector for compute / notebook pods based on account settings."""
        cfg = self.get_account_compute_settings()
        dedicated = bool(cfg.get("dedicated_pool_enabled", True))
        if dedicated:
            pool_name = cfg.get("pool_name") or "computepool"
            return {"kubernetes.azure.com/agentpool": pool_name}
        else:
            default_pool = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL
            if default_pool in ("userpoolv2", "userpool", ""):
                default_pool = settings.AZURE_DEFAULT_USER_NODEPOOL
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
                or labels.get("eks.amazonaws.com/nodegroup")
                or labels.get("karpenter.sh/nodepool")
                or labels.get("cloud.google.com/gke-nodepool")
                or labels.get("node.kubernetes.io/nodepool")
                or labels.get("compassx.io/nodepool")
                or labels.get("agentpool")
                or labels.get("nodepool")
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
                            "--node-count", str(min_count),
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

    def list_compute_deployments_summary(self) -> Dict[str, Any]:
        """List all compute and notebook runtime deployments in compassx namespace with their current node selector and target."""
        _, apps_v1 = self._get_k8s_clients()
        if not apps_v1:
            return {"total_compute": 0, "compute_pods": []}

        ns = settings.K8S_NAMESPACE
        try:
            deps = apps_v1.list_namespaced_deployment(namespace=ns).items
        except Exception as e:
            logger.warning("Failed to list deployments in namespace %s: %s", ns, e)
            return {"total_compute": 0, "compute_pods": []}

        compute_deps = []
        for dep in deps:
            name = dep.metadata.name
            labels = dep.metadata.labels or {}
            # Match compute/runtime deployments
            if (
                "compassx/runtime-id" in labels
                or "compassx/runtime-type" in labels
                or name.startswith("compassx-runtime-")
                or name.startswith("compassx-compute-")
                or "duckdb" in name
                or "serverless" in name
            ):
                spec = dep.spec.template.spec
                node_selector = spec.node_selector or {}
                assigned_pool = (
                    node_selector.get("kubernetes.azure.com/agentpool")
                    or node_selector.get("agentpool")
                    or "unspecified"
                )
                compute_deps.append({
                    "name": name,
                    "runtime_type": labels.get("compassx/runtime-type") or "runtime",
                    "replicas": dep.spec.replicas or 0,
                    "ready_replicas": dep.status.ready_replicas or 0,
                    "assigned_pool": assigned_pool,
                    "node_selector": node_selector,
                })

        return {
            "total_compute": len(compute_deps),
            "compute_pods": compute_deps,
        }

    def switchover_compute_workloads(self, target_pool: Optional[str] = None) -> Dict[str, Any]:
        """Update nodeSelector on all compassx compute and notebook deployments to gracefully roll over pods to the target pool."""
        _, apps_v1 = self._get_k8s_clients()
        if not apps_v1:
            return {"status": "error", "message": "Kubernetes client unavailable", "migrated_count": 0}

        ns = settings.K8S_NAMESPACE
        cfg = self.get_account_compute_settings()

        if target_pool is None:
            if bool(cfg.get("dedicated_pool_enabled", True)):
                target_pool = cfg.get("pool_name") or "computepool"
            else:
                target_pool = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL

        target_selector = {"kubernetes.azure.com/agentpool": target_pool}
        now_ts = datetime.now(timezone.utc).isoformat()

        try:
            deps = apps_v1.list_namespaced_deployment(namespace=ns).items
        except Exception as e:
            logger.error("Failed to list compute deployments for switchover: %s", e)
            return {"status": "error", "message": str(e), "migrated_count": 0}

        migrated = []
        for dep in deps:
            name = dep.metadata.name
            labels = dep.metadata.labels or {}
            if (
                "compassx/runtime-id" in labels
                or "compassx/runtime-type" in labels
                or name.startswith("compassx-runtime-")
                or name.startswith("compassx-compute-")
                or "duckdb" in name
                or "serverless" in name
            ):
                current_selector = dep.spec.template.spec.node_selector or {}
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
                            },
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
                    logger.info("Migrated compute deployment '%s' to node pool '%s'", name, target_pool)
                except Exception as exc:
                    logger.error("Failed to patch compute deployment '%s' during switchover: %s", name, exc)
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

    def get_compute_pool_status(self) -> Dict[str, Any]:
        """Aggregate account settings, live K8s nodes, Azure nodepool metadata, and provisioning state for compute pool."""
        cfg = self.get_account_compute_settings()
        dedicated_enabled = bool(cfg.get("dedicated_pool_enabled", True))
        pool_name = cfg.get("pool_name") or "computepool"
        default_pool_name = cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL
        selected_vm_size = cfg.get("vm_size") or "Standard_D4ads_v5"
        min_count = int(cfg.get("min_count", 0))
        max_count = int(cfg.get("max_count", 10))
        auto_scale = bool(cfg.get("auto_scale", True))
        auto_stop_enabled = bool(cfg.get("auto_stop_enabled", True))
        auto_stop_minutes = int(cfg.get("auto_stop_minutes", 5))

        cluster_pools = self.list_cluster_node_pools()
        compute_pool_info = next((p for p in cluster_pools if p["name"] == pool_name), None)

        # Check cloud nodepool directly (Scale-to-Zero pool may have 0 K8s node objects)
        aks_info = self._get_aks_nodepool_raw(pool_name) if not compute_pool_info else None
        is_provisioned = bool(
            compute_pool_info is not None
            or (aks_info and aks_info.get("provisioningState") in ("Succeeded", "Updating", "Creating"))
            or cfg.get("is_provisioned") is True
        )

        if not compute_pool_info and is_provisioned:
            if aks_info:
                selected_vm_size = aks_info.get("vmSize") or selected_vm_size
            compute_pool_info = {
                "name": pool_name,
                "vm_size": selected_vm_size,
                "architecture": "x86_64",
                "os": (aks_info.get("osType") if aks_info else None) or "Linux",
                "total_nodes": int((aks_info.get("count") if aks_info else None) or 0),
                "ready_nodes": 0,
                "nodes": [],
            }

        compute_workloads = self.list_compute_deployments_summary()

        status = "disabled"
        status_message = f"Compute pods scheduled on shared user node pool ('{default_pool_name}')."

        if self._is_provisioning:
            if self._provisioning_action == "deprovisioning":
                status = "deprovisioning"
                status_message = self._last_provision_message or f"Deprovisioning compute pool '{pool_name}'..."
            else:
                status = "provisioning"
                status_message = self._last_provision_message or f"Provisioning compute pool '{pool_name}'..."
        elif not dedicated_enabled:
            status = "disabled"
            status_message = f"Dedicated compute pool disabled. Workloads routed to '{default_pool_name}'."
        elif not is_provisioned:
            status = "not_provisioned"
            status_message = f"Compute pool '{pool_name}' is not provisioned on the cluster yet. Click 'Provision Compute Pool' to create it."
        else:
            # Provisioned
            if compute_pool_info and compute_pool_info["ready_nodes"] > 0:
                status = "active"
                status_message = f"Compute pool '{pool_name}' active with {compute_pool_info['ready_nodes']} ready node(s)."
            elif min_count == 0:
                status = "active"
                status_message = f"Scale-to-Zero active on '{pool_name}' (0 nodes idle - $0 cost, auto-scales on demand)."
            elif compute_pool_info and compute_pool_info["total_nodes"] > 0:
                status = "starting"
                status_message = f"Compute pool '{pool_name}' starting ({compute_pool_info['ready_nodes']}/{compute_pool_info['total_nodes']} ready)."
            else:
                status = "active"
                status_message = f"Compute pool '{pool_name}' active on cluster ({selected_vm_size})."

        vm_meta = next((v for v in AZURE_VM_SIZES if v["id"] == selected_vm_size), None)
        vm_capacity_gib = vm_meta["memory_gib"] if vm_meta else 16

        return {
            "dedicated_pool_enabled": dedicated_enabled,
            "pool_name": pool_name,
            "default_pool_name": default_pool_name,
            "vm_size": selected_vm_size,
            "vm_capacity_gib": vm_capacity_gib,
            "min_count": min_count,
            "max_count": max_count,
            "auto_scale": auto_scale,
            "auto_stop_enabled": auto_stop_enabled,
            "auto_stop_minutes": auto_stop_minutes,
            "status": status,
            "status_message": status_message,
            "is_provisioned": is_provisioned,
            "is_provisioning": self._is_provisioning,
            "provisioning_action": self._provisioning_action,
            "compute_pool": compute_pool_info,
            "aks_info": aks_info,
            "cluster_pools": cluster_pools,
            "compute_workloads": compute_workloads,
            "vm_sizes_catalog": self.get_vm_sizes_catalog(),
        }

    def trigger_provision_compute_nodepool_async(
        self,
        pool_name: str = "computepool",
        vm_size: str = "Standard_D4ads_v5",
        min_count: int = 0,
        max_count: int = 10,
        auto_scale: bool = True,
    ) -> None:
        """Asynchronously triggers AKS compute nodepool creation or update via az CLI in a background thread."""
        thread = threading.Thread(
            target=self._provision_compute_nodepool_worker,
            args=(pool_name, vm_size, min_count, max_count, auto_scale),
            daemon=True,
        )
        thread.start()

    def _provision_compute_nodepool_worker(
        self, pool_name: str, vm_size: str, min_count: int, max_count: int, auto_scale: bool
    ) -> None:
        """Worker thread executing compute nodepool create/update command."""
        with self._provisioning_lock:
            self._is_provisioning = True
            self._provisioning_action = "provisioning"
            self._last_provision_message = f"Provisioning compute pool '{pool_name}' ({vm_size}, Min: {min_count}, Max: {max_count})..."
            try:
                az_path = shutil.which("az")
                if not az_path:
                    logger.warning("Cloud CLI not found on system path; skipping live node pool creation command.")
                    self._last_provision_message = f"Compute pool '{pool_name}' enabled ({vm_size}, Min: {min_count}, Max: {max_count}). Workloads routed to '{pool_name}'."
                    return

                # Check if nodepool already exists
                check_cmd = [
                    az_path, "aks", "nodepool", "show",
                    "--resource-group", settings.AZURE_RESOURCE_GROUP,
                    "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                    "--name", pool_name,
                    "-o", "json",
                ]
                logger.info("Checking compute nodepool '%s'...", pool_name)
                res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=60)

                if res.returncode == 0:
                    logger.info("Compute node pool '%s' already exists on cluster. Updating parameters...", pool_name)
                    self._last_provision_message = f"Updating compute pool '{pool_name}' autoscaling (Min: {min_count}, Max: {max_count})..."
                    update_cmd = [
                        az_path, "aks", "nodepool", "update",
                        "--resource-group", settings.AZURE_RESOURCE_GROUP,
                        "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                        "--name", pool_name,
                        "--update-cluster-autoscaler",
                        "--min-count", str(min_count),
                        "--max-count", str(max_count),
                        "--no-wait",
                    ]
                    subprocess.run(update_cmd, capture_output=True, text=True, timeout=60)
                    self._last_provision_message = f"Compute node pool '{pool_name}' update initiated."
                else:
                    logger.info("Creating compute node pool '%s' with VM size %s (min=%d, max=%d)...", pool_name, vm_size, min_count, max_count)
                    self._last_provision_message = f"Creating compute node pool '{pool_name}' ({vm_size}, Min: {min_count}, Max: {max_count})..."
                    create_cmd = [
                        az_path, "aks", "nodepool", "add",
                        "--resource-group", settings.AZURE_RESOURCE_GROUP,
                        "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                        "--name", pool_name,
                        "--node-vm-size", vm_size,
                        "--mode", "User",
                    ]
                    if auto_scale:
                        create_cmd.extend([
                            "--enable-cluster-autoscaler",
                            "--min-count", str(min_count),
                            "--max-count", str(max_count),
                            "--node-count", str(min_count),
                        ])
                    else:
                        create_cmd.extend(["--node-count", str(min_count)])
                    create_cmd.append("--no-wait")

                    run_res = subprocess.run(create_cmd, capture_output=True, text=True, timeout=90)
                    if run_res.returncode == 0:
                        self._last_provision_message = f"Compute pool '{pool_name}' provisioning in progress."
                        logger.info("Compute nodepool add dispatched successfully.")
                    else:
                        self._last_provision_message = f"Provisioning failed: {run_res.stderr.strip()[:200]}"
                        logger.warning("Compute nodepool add returned error: %s", run_res.stderr)

                # Gracefully switchover compute workloads to computepool
                self.switchover_compute_workloads(target_pool=pool_name)
            except Exception as exc:
                logger.error("Error during compute node pool provisioning worker: %s", exc)
                self._last_provision_message = f"Provisioning error: {str(exc)}"
            finally:
                self._is_provisioning = False
                self._provisioning_action = ""
                with self._cache_lock:
                    self._aks_nodepools_cache.pop(pool_name, None)

    def trigger_deprovision_compute_nodepool_async(
        self,
        pool_name: str = "computepool",
        fallback_pool: str = "systempoolv2",
    ) -> None:
        """Asynchronously gracefully migrates compute pods to fallback pool and deprovisions nodepool."""
        thread = threading.Thread(
            target=self._deprovision_compute_nodepool_worker,
            args=(pool_name, fallback_pool),
            daemon=True,
        )
        thread.start()

    def _deprovision_compute_nodepool_worker(self, pool_name: str, fallback_pool: str) -> None:
        """Worker thread executing compute nodepool deprovisioning command."""
        with self._provisioning_lock:
            self._is_provisioning = True
            self._provisioning_action = "deprovisioning"
            self._last_provision_message = f"Gracefully migrating compute pods to '{fallback_pool}' and deprovisioning '{pool_name}'..."
            try:
                # 1. Gracefully migrate running compute pods to fallback pool
                logger.info("Switching over compute pods to fallback pool '%s'...", fallback_pool)
                self.switchover_compute_workloads(target_pool=fallback_pool)

                az_path = shutil.which("az")
                if not az_path:
                    logger.warning("Cloud CLI not found on system path; skipping live delete command.")
                    self._last_provision_message = f"Compute pods migrated to '{fallback_pool}'."
                    return

                # Check if pool exists
                check_cmd = [
                    az_path, "aks", "nodepool", "show",
                    "--resource-group", settings.AZURE_RESOURCE_GROUP,
                    "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                    "--name", pool_name,
                    "-o", "json",
                ]
                res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=60)
                if res.returncode != 0:
                    logger.info("Compute nodepool '%s' does not exist; nothing to delete.", pool_name)
                    self._last_provision_message = f"Compute pool '{pool_name}' not present. Workloads assigned to '{fallback_pool}'."
                    return

                logger.info("Deprovisioning compute node pool '%s'...", pool_name)
                del_cmd = [
                    az_path, "aks", "nodepool", "delete",
                    "--resource-group", settings.AZURE_RESOURCE_GROUP,
                    "--cluster-name", settings.AZURE_AKS_CLUSTER_NAME,
                    "--name", pool_name,
                    "--yes",
                    "--no-wait",
                ]
                del_res = subprocess.run(del_cmd, capture_output=True, text=True, timeout=90)
                if del_res.returncode == 0:
                    self._last_provision_message = f"Deprovisioning of compute pool '{pool_name}' initiated. Pods running on '{fallback_pool}'."
                    logger.info("Compute nodepool delete dispatched successfully.")
                else:
                    self._last_provision_message = f"Deprovisioning failed: {del_res.stderr.strip()[:200]}"
                    logger.warning("Compute nodepool delete returned error: %s", del_res.stderr)
            except Exception as exc:
                logger.error("Error during compute nodepool deprovision worker: %s", exc)
                self._last_provision_message = f"Deprovisioning error: {str(exc)}"
            finally:
                self._is_provisioning = False
                self._provisioning_action = ""
                with self._cache_lock:
                    self._aks_nodepools_cache.pop(pool_name, None)


# Singleton instance
node_pool_manager = NodePoolManager()
