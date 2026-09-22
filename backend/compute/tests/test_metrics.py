"""Tests for compute resource metrics endpoint."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.compute_resources import ComputeResource
from compute.schemas import ComputeMetricsResponse, ComputeResourceStatus


class TestComputeMetrics:
    def test_get_resource_metrics_returns_valid_structure(self):
        from compute.resource_service import ComputeResourceService

        mock_db = MagicMock()
        mock_resource = ComputeResource(
            id="res-12345678",
            name="Test Notebook Compute",
            runtime="duckdb",
            profile="local",
            user_id="user-1",
            workspace_id="ws-1",
            deployment_name="compassx-test-res-12345678",
            desired_status="running",
            is_default=False,
            created_at=datetime.now(timezone.utc),
        )

        mock_status = ComputeResourceStatus(
            id="res-12345678",
            name="Test Notebook Compute",
            runtime="duckdb",
            profile="local",
            user_id="user-1",
            created_by="user-1",
            created_at=datetime.now(timezone.utc),
            deployment_name="compassx-test-res-12345678",
            desired_status="running",
            phase="Running",
            pod_name="compassx-test-pod-abc",
        )

        with patch.object(ComputeResourceService, "_get_resource_row", return_value=mock_resource), \
             patch.object(ComputeResourceService, "get_resource_with_status", return_value=mock_status):
            service = ComputeResourceService(mock_db)
            metrics = service.get_resource_metrics(
                resource_id="res-12345678",
                user_id="user-1",
                workspace_id="ws-1",
                time_range="15m",
            )

            assert isinstance(metrics, ComputeMetricsResponse)
            assert metrics.resource_id == "res-12345678"
            assert metrics.runtime == "duckdb"
            assert metrics.profile == "local"
            assert metrics.cpu_cores_limit == 1.0
            assert metrics.cpu_cores_request == 0.25
            assert metrics.memory_limit_mb == 2048.0
            assert metrics.memory_request_mb == 512.0
            assert len(metrics.cpu_timeseries) > 0
            assert len(metrics.memory_timeseries) > 0

    def test_get_resource_metrics_stopped_resource(self):
        from compute.resource_service import ComputeResourceService

        mock_db = MagicMock()
        mock_resource = ComputeResource(
            id="res-stopped",
            name="Stopped Compute",
            runtime="duckdb",
            profile="cloud-s",
            user_id="user-1",
            workspace_id="ws-1",
            deployment_name="compassx-test-stopped",
            desired_status="stopped",
            is_default=False,
            created_at=datetime.now(timezone.utc),
        )

        mock_status = ComputeResourceStatus(
            id="res-stopped",
            name="Stopped Compute",
            runtime="duckdb",
            profile="cloud-s",
            user_id="user-1",
            created_by="user-1",
            created_at=datetime.now(timezone.utc),
            deployment_name="compassx-test-stopped",
            desired_status="stopped",
            phase="Stopped",
            pod_name=None,
        )

        with patch.object(ComputeResourceService, "_get_resource_row", return_value=mock_resource), \
             patch.object(ComputeResourceService, "get_resource_with_status", return_value=mock_status):
            service = ComputeResourceService(mock_db)
            metrics = service.get_resource_metrics(
                resource_id="res-stopped",
                user_id="user-1",
                workspace_id="ws-1",
                time_range="1h",
            )

            assert isinstance(metrics, ComputeMetricsResponse)
            assert metrics.status == "Stopped"
            assert metrics.cpu_cores_limit == 2.0
            assert metrics.memory_limit_mb == 4096.0
            assert metrics.cpu_percent == 0.0
            assert metrics.memory_mb == 0.0
