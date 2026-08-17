"""Tests for AirflowManager."""
from unittest.mock import MagicMock, patch

from services.airflow.manager import AirflowManager
from services.base import ServicePhase


def test_start_creates_deployment_and_service():
    manager = AirflowManager()
    apps = MagicMock()
    core = MagicMock()
    rbac = MagicMock()

    with (
        patch.object(manager, "_ensure_namespace"),
        patch.object(manager, "_run_init_job"),
        patch("services.airflow.manager.get_k8s_client") as mock_k8s,
    ):
        from kubernetes.client.exceptions import ApiException

        apps.replace_namespaced_deployment.side_effect = ApiException(status=404)
        core.replace_namespaced_service.side_effect = ApiException(status=404)
        mock_k8s.return_value.apps.return_value = apps
        mock_k8s.return_value.core.return_value = core
        mock_k8s.return_value.rbac.return_value = rbac
        status = manager.start()

    assert status.phase == ServicePhase.STARTING
    assert apps.create_namespaced_deployment.call_count == 4
    assert core.create_namespaced_service.call_count == 2


def test_get_status_running_when_available_replicas_present():
    manager = AirflowManager()
    apps = MagicMock()
    deploy = MagicMock()
    deploy.status.available_replicas = 1
    apps.read_namespaced_deployment.return_value = deploy

    with patch("services.airflow.manager.get_k8s_client") as mock_k8s:
        mock_k8s.return_value.apps.return_value = apps
        status = manager.get_status()

    assert status.phase == ServicePhase.RUNNING


def test_stop_deletes_resources():
    manager = AirflowManager()
    apps = MagicMock()
    core = MagicMock()

    with (
        patch("services.airflow.manager.get_k8s_client") as mock_k8s,
    ):
        mock_k8s.return_value.apps.return_value = apps
        mock_k8s.return_value.core.return_value = core
        status = manager.stop()

    assert status.phase == ServicePhase.STOPPED
    assert apps.delete_namespaced_deployment.call_count == 4
    assert core.delete_namespaced_service.call_count == 2
