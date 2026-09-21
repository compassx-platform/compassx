"""Unit tests for NodePoolManager and dedicated app node pool orchestration."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.node_pool_manager import NodePoolManager, AZURE_VM_SIZES


@pytest.fixture
def manager():
    return NodePoolManager()


def test_vm_sizes_catalog(manager):
    catalog = manager.get_vm_sizes_catalog()
    assert len(catalog) >= 5
    ids = [vm["id"] for vm in catalog]
    assert "Standard_B2s_v2" in ids
    assert "Standard_B2als_v2" in ids
    assert "Standard_D2s_v5" in ids

    for vm in catalog:
        assert "cpu" in vm and vm["cpu"] > 0
        assert "memory_gib" in vm and vm["memory_gib"] > 0
        assert "label" in vm
        assert "category" in vm


def test_get_app_node_selector_default_disabled(manager):
    with patch.object(manager, "get_account_pool_settings", return_value={"dedicated_pool_enabled": False, "default_pool_name": "userpoolv2"}):
        selector = manager.get_app_node_selector()
        assert selector == {"kubernetes.azure.com/agentpool": "userpoolv2"}


def test_get_app_node_selector_dedicated_enabled(manager):
    with patch.object(manager, "get_account_pool_settings", return_value={"dedicated_pool_enabled": True, "pool_name": "apppool"}):
        selector = manager.get_app_node_selector()
        assert selector == {"kubernetes.azure.com/agentpool": "apppool"}


def test_get_compute_node_selector_dedicated_default(manager):
    with patch.object(manager, "get_account_compute_settings", return_value={"dedicated_pool_enabled": True, "pool_name": "computepool"}):
        selector = manager.get_compute_node_selector()
        assert selector == {"kubernetes.azure.com/agentpool": "computepool"}


def test_get_compute_pool_status_scale_to_zero(manager):
    with patch.object(manager, "get_account_compute_settings", return_value={
        "dedicated_pool_enabled": True,
        "pool_name": "computepool",
        "vm_size": "Standard_D4s_v5",
        "min_count": 0,
        "max_count": 10,
        "auto_stop_minutes": 5,
    }), patch.object(manager, "list_cluster_node_pools", return_value=[]):
        status = manager.get_compute_pool_status()
        assert status["dedicated_pool_enabled"] is True
        assert status["pool_name"] == "computepool"
        assert status["vm_size"] == "Standard_D4s_v5"
        assert status["vm_capacity_gib"] == 16
        assert status["min_count"] == 0
        assert status["auto_stop_minutes"] == 5
        assert "Scale-to-Zero" in status["status_message"]


def test_switchover_app_workloads(manager):
    mock_core = MagicMock()
    mock_apps = MagicMock()

    # Mock two deployments: one prod app, one dev sandbox
    dep1 = MagicMock()
    dep1.metadata.name = "compassx-app-test1"
    dep1.metadata.labels = {"compassx/app-id": "test1", "compassx/role": "prod"}
    dep1.spec.template.spec.node_selector = {"kubernetes.azure.com/agentpool": "userpoolv2"}

    dep2 = MagicMock()
    dep2.metadata.name = "compassx-app-dev-test1"
    dep2.metadata.labels = {"compassx/app-id": "test1", "compassx/dev": "true"}
    dep2.spec.template.spec.node_selector = None

    # Other deployment (not an app)
    dep3 = MagicMock()
    dep3.metadata.name = "compassx-backend"
    dep3.metadata.labels = {"app": "backend"}
    dep3.spec.template.spec.node_selector = {}

    mock_apps.list_namespaced_deployment.return_value.items = [dep1, dep2, dep3]

    with patch.object(manager, "_get_k8s_clients", return_value=(mock_core, mock_apps)):
        res = manager.switchover_app_workloads(target_pool="apppool")

        assert res["status"] == "success"
        assert res["target_pool"] == "apppool"
        assert res["migrated_count"] == 2
        assert mock_apps.patch_namespaced_deployment.call_count == 2

        # Check patch call args
        called_names = [call[1]["name"] for call in mock_apps.patch_namespaced_deployment.call_args_list]
        assert "compassx-app-test1" in called_names
        assert "compassx-app-dev-test1" in called_names
        assert "compassx-backend" not in called_names


def test_list_cluster_node_pools(manager):
    mock_core = MagicMock()
    mock_apps = MagicMock()

    node1 = MagicMock()
    node1.metadata.name = "node-user-1"
    node1.metadata.labels = {
        "kubernetes.azure.com/agentpool": "userpoolv2",
        "node.kubernetes.io/instance-type": "Standard_B2als_v2",
        "kubernetes.io/arch": "amd64",
        "kubernetes.io/os": "linux",
    }
    cond1 = MagicMock()
    cond1.type = "Ready"
    cond1.status = "True"
    node1.status.conditions = [cond1]

    node2 = MagicMock()
    node2.metadata.name = "node-app-1"
    node2.metadata.labels = {
        "kubernetes.azure.com/agentpool": "apppool",
        "node.kubernetes.io/instance-type": "Standard_B2s_v2",
        "kubernetes.io/arch": "amd64",
        "kubernetes.io/os": "linux",
    }
    cond2 = MagicMock()
    cond2.type = "Ready"
    cond2.status = "True"
    node2.status.conditions = [cond2]

    mock_core.list_node.return_value.items = [node1, node2]

    with patch.object(manager, "_get_k8s_clients", return_value=(mock_core, mock_apps)):
        pools = manager.list_cluster_node_pools()
        pool_names = [p["name"] for p in pools]
        assert "userpoolv2" in pool_names
        assert "apppool" in pool_names
        app_pool = next(p for p in pools if p["name"] == "apppool")
        assert app_pool["ready_nodes"] == 1
        assert app_pool["vm_size"] == "Standard_B2s_v2"
