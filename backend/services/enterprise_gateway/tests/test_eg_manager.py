"""Tests for EnterpriseGatewayManager."""
from unittest.mock import MagicMock, patch, call

import pytest
from kubernetes.client.exceptions import ApiException

from services.base import ServicePhase
from services.enterprise_gateway.manager import EnterpriseGatewayManager


def _make_manager():
    return EnterpriseGatewayManager()


def _api_exc(status: int) -> ApiException:
    exc = ApiException(status=status)
    exc.status = status
    return exc


class TestEGManagerStart:
    def test_start_creates_configmap_then_deployment_then_service(self):
        mgr = _make_manager()
        with (
            patch.object(mgr, "_ensure_namespace"),
            patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps,
            patch("services.enterprise_gateway.manager.get_k8s_client") as mock_k8s,
            patch("services.enterprise_gateway.manager.build_kernelspec_configmap", return_value=MagicMock()),
            patch("services.enterprise_gateway.manager.build_eg_deployment", return_value=MagicMock()),
            patch("services.enterprise_gateway.manager.build_eg_service", return_value=MagicMock()),
        ):
            # simulate Deployment not existing
            mock_apps.return_value.read_namespaced_deployment.side_effect = _api_exc(404)
            mock_k8s.return_value.core.return_value.create_namespaced_config_map.return_value = MagicMock()

            status = mgr.start()

        assert status.phase == ServicePhase.STARTING

        core = mock_k8s.return_value.core.return_value
        # ConfigMap created
        core.create_namespaced_config_map.assert_called_once()
        # Deployment created
        mock_apps.return_value.create_namespaced_deployment.assert_called_once()
        # Service created
        core.create_namespaced_service.assert_called_once()

    def test_start_returns_running_if_already_running(self):
        mgr = _make_manager()
        deploy = MagicMock()
        deploy.status.available_replicas = 1

        with (
            patch.object(mgr, "_ensure_namespace"),
            patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps,
            patch("services.enterprise_gateway.manager.get_k8s_client") as mock_k8s,
            patch("services.enterprise_gateway.manager.build_kernelspec_configmap", return_value=MagicMock()),
        ):
            mock_apps.return_value.read_namespaced_deployment.return_value = deploy
            mock_k8s.return_value.core.return_value.create_namespaced_config_map.return_value = MagicMock()

            status = mgr.start()

        assert status.phase == ServicePhase.RUNNING
        assert "already running" in status.message


class TestEGManagerStop:
    def test_stop_deletes_deployment_and_service(self):
        mgr = _make_manager()
        with (
            patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps,
            patch("services.enterprise_gateway.manager.get_k8s_client") as mock_k8s,
        ):
            status = mgr.stop()

        assert status.phase == ServicePhase.STOPPED
        mock_apps.return_value.delete_namespaced_deployment.assert_called_once()
        mock_k8s.return_value.core.return_value.delete_namespaced_service.assert_called_once()

    def test_stop_preserves_configmap(self):
        mgr = _make_manager()
        with (
            patch("services.enterprise_gateway.manager.client.AppsV1Api"),
            patch("services.enterprise_gateway.manager.get_k8s_client") as mock_k8s,
        ):
            mgr.stop()

        core = mock_k8s.return_value.core.return_value
        # ConfigMap delete should NOT be called
        core.delete_namespaced_config_map.assert_not_called()


class TestEGManagerGetStatus:
    def test_get_status_stopped_when_not_found(self):
        mgr = _make_manager()
        with patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps:
            mock_apps.return_value.read_namespaced_deployment.side_effect = _api_exc(404)
            status = mgr.get_status()

        assert status.phase == ServicePhase.STOPPED

    def test_get_status_running_when_replicas_available(self):
        mgr = _make_manager()
        deploy = MagicMock()
        deploy.status.available_replicas = 1
        with patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps:
            mock_apps.return_value.read_namespaced_deployment.return_value = deploy
            status = mgr.get_status()

        assert status.phase == ServicePhase.RUNNING

    def test_get_status_starting_when_zero_replicas(self):
        mgr = _make_manager()
        deploy = MagicMock()
        deploy.status.available_replicas = 0
        with patch("services.enterprise_gateway.manager.client.AppsV1Api") as mock_apps:
            mock_apps.return_value.read_namespaced_deployment.return_value = deploy
            status = mgr.get_status()

        assert status.phase == ServicePhase.STARTING
