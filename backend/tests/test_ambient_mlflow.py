"""Tests for Phase 1: Ambient MLflow tracking in notebooks and compute kernels."""
import os
from unittest.mock import MagicMock, patch

from services.enterprise_gateway.kernelspecs import (
    generate_kernel_json,
    build_kernelspec_configmap,
    RUNTIMES,
)


def test_kernelspecs_ambient_mlflow_env_vars():
    """Verify generate_kernel_json includes ambient MLflow and MinIO environment variables."""
    for runtime in RUNTIMES:
        spec = generate_kernel_json(runtime)
        env = spec.get("env", {})
        assert "MLFLOW_TRACKING_URI" in env
        assert "KERNEL_MLFLOW_TRACKING_URI" in env
        assert "MLFLOW_S3_ENDPOINT_URL" in env
        assert "KERNEL_MLFLOW_S3_ENDPOINT_URL" in env
        assert "AWS_ACCESS_KEY_ID" in env
        assert "AWS_SECRET_ACCESS_KEY" in env
        assert "AWS_DEFAULT_REGION" in env
        assert env["MLFLOW_TRACKING_URI"].endswith(":5000")
        assert env["MLFLOW_S3_ENDPOINT_URL"].endswith(":9000")


def test_build_kernelspec_configmap_includes_mlflow():
    """Verify build_kernelspec_configmap generates JSON containing MLflow tracking env."""
    import json
    cm = build_kernelspec_configmap(
        namespace="compassx-test",
        mlflow_tracking_uri="http://compassx-mlflow.compassx-test.svc.cluster.local:5000",
        mlflow_s3_endpoint_url="http://minio.compassx-test.svc.cluster.local:9000",
    )
    assert cm.metadata.namespace == "compassx-test"
    for key, val in cm.data.items():
        data = json.loads(val)
        assert data["env"]["MLFLOW_TRACKING_URI"] == "http://compassx-mlflow.compassx-test.svc.cluster.local:5000"
        assert data["env"]["MLFLOW_S3_ENDPOINT_URL"] == "http://minio.compassx-test.svc.cluster.local:9000"


def test_compassx_sql_ambient_mlflow_binding(monkeypatch):
    """Verify importing services.compassx_sql automatically binds active notebook experiment."""
    monkeypatch.setenv("COMPASSX_NOTEBOOK_PATH", "users/admin/churn_prediction.ipynb")

    mock_mlflow = MagicMock()
    mock_mlflow.get_experiment_by_name.return_value = None

    with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
        import importlib
        import services.compassx_sql
        importlib.reload(services.compassx_sql)

        mock_mlflow.create_experiment.assert_called_with("/users/admin/churn_prediction.ipynb")
        mock_mlflow.set_experiment.assert_called_with("/users/admin/churn_prediction.ipynb")


import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_get_notebook_experiment_runs_disconnected():
    """Verify endpoint returns connected=False when MLflow is not reachable."""
    from app.notebooks.routes.notebook_routes import get_notebook_experiment_runs

    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        res = await get_notebook_experiment_runs(path="my_model.ipynb", guard=MagicMock())
        assert res["connected"] is False
        assert "not reachable" in res["message"]
        assert res["runs"] == []


@pytest.mark.asyncio
async def test_get_notebook_experiment_runs_no_experiment():
    """Verify endpoint handles notebook with no experiment created yet."""
    from app.notebooks.routes.notebook_routes import get_notebook_experiment_runs

    mock_health = MagicMock()
    mock_health.status_code = 200

    mock_not_found = MagicMock()
    mock_not_found.status_code = 404

    async def mock_get(self, url, **kwargs):
        if url.endswith("/health"):
            return mock_health
        return mock_not_found

    with patch("httpx.AsyncClient.get", new=mock_get):
        res = await get_notebook_experiment_runs(path="untracked_notebook.ipynb", guard=MagicMock())
        assert res["connected"] is True
        assert res["experiment"] is None
        assert res["runs"] == []
        assert "No MLflow experiment found" in res["message"]


@pytest.mark.asyncio
async def test_get_notebook_experiment_runs_success():
    """Verify endpoint parses experiment runs, metrics, params, and tags."""
    from app.notebooks.routes.notebook_routes import get_notebook_experiment_runs

    mock_health = MagicMock()
    mock_health.status_code = 200

    mock_exp = MagicMock()
    mock_exp.status_code = 200
    mock_exp.json.return_value = {
        "experiment": {
            "experiment_id": "exp_42",
            "name": "/churn_model.ipynb",
            "artifact_location": "s3://mlflow-artifacts/exp_42",
            "lifecycle_stage": "active",
        }
    }

    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.json.return_value = {
        "runs": [
            {
                "info": {
                    "run_id": "run_abc123",
                    "run_name": "xgboost_trial_1",
                    "status": "FINISHED",
                    "start_time": 1700000000000,
                    "end_time": 1700000045000,
                    "artifact_uri": "s3://mlflow-artifacts/exp_42/run_abc123/artifacts",
                },
                "data": {
                    "metrics": [{"key": "val_loss", "value": 0.23}, {"key": "accuracy", "value": 0.94}],
                    "params": [{"key": "learning_rate", "value": "0.05"}, {"key": "max_depth", "value": "6"}],
                    "tags": [{"key": "mlflow.user", "value": "alice"}],
                },
            }
        ]
    }

    async def mock_get(self, url, **kwargs):
        if url.endswith("/health"):
            return mock_health
        return mock_exp

    async def mock_post(self, url, **kwargs):
        return mock_search

    with patch("httpx.AsyncClient.get", new=mock_get), patch("httpx.AsyncClient.post", new=mock_post):
        res = await get_notebook_experiment_runs(path="churn_model.ipynb", guard=MagicMock())
        assert res["connected"] is True
        assert res["experiment"]["experiment_id"] == "exp_42"
        assert res["total_runs"] == 1
        run = res["runs"][0]
        assert run["run_id"] == "run_abc123"
        assert run["run_name"] == "xgboost_trial_1"
        assert run["status"] == "FINISHED"
        assert run["duration_ms"] == 45000
        assert run["metrics"]["accuracy"] == 0.94
        assert run["params"]["learning_rate"] == "0.05"
        assert run["tags"]["mlflow.user"] == "alice"
        assert "run_abc123" in run["ui_url"]


def test_catalog_model_asset_type():
    """Verify ModelAssetType is registered in Unified Catalog asset registry."""
    from app.catalog.asset_type import get_asset_type, ModelAssetType

    asset_type = get_asset_type("model")
    assert asset_type is not None
    assert isinstance(asset_type, ModelAssetType)
    assert asset_type.kind == "model"
    assert asset_type.storage_sub_path("fraud_detector") == "models/fraud_detector"


@pytest.mark.asyncio
async def test_get_run_artifacts():
    """Verify endpoint fetches and returns run artifacts list."""
    from app.notebooks.routes.notebook_routes import get_run_artifacts

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "root_uri": "s3://mlflow-artifacts/1/run_1/artifacts",
        "files": [
            {"path": "model", "is_dir": True},
            {"path": "model/MLmodel", "is_dir": False, "file_size": 420},
            {"path": "confusion_matrix.png", "is_dir": False, "file_size": 12450},
        ],
    }

    async def mock_get(self, url, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.get", new=mock_get):
        res = await get_run_artifacts(run_id="run_1", path="", guard=MagicMock())
        assert res["connected"] is True
        assert len(res["files"]) == 3
        assert res["files"][0]["path"] == "model"
        assert res["files"][0]["is_dir"] is True


@pytest.mark.asyncio
async def test_list_registered_models():
    """Verify endpoint lists registered models with latest versions and aliases."""
    from app.notebooks.routes.notebook_routes import list_registered_models

    mock_health = MagicMock()
    mock_health.status_code = 200

    mock_models_resp = MagicMock()
    mock_models_resp.status_code = 200
    mock_models_resp.json.return_value = {
        "registered_models": [
            {
                "name": "churn_classifier",
                "creation_timestamp": 1700000000000,
                "last_updated_timestamp": 1700000010000,
                "description": "Predicts customer churn",
                "latest_versions": [
                    {
                        "version": "2",
                        "creation_timestamp": 1700000010000,
                        "current_stage": "Production",
                        "aliases": ["champion"],
                        "status": "READY",
                        "run_id": "run_123",
                    }
                ],
                "tags": [{"key": "framework", "value": "xgboost"}],
            }
        ]
    }

    async def mock_get(self, url, **kwargs):
        if url.endswith("/health"):
            return mock_health
        return mock_models_resp

    with patch("httpx.AsyncClient.get", new=mock_get):
        res = await list_registered_models(max_results=50, guard=MagicMock())
        assert res["connected"] is True
        assert res["total_models"] == 1
        m = res["models"][0]
        assert m["name"] == "churn_classifier"
        assert m["latest_versions"][0]["current_stage"] == "Production"
        assert m["latest_versions"][0]["aliases"] == ["champion"]
        assert m["tags"]["framework"] == "xgboost"


@pytest.mark.asyncio
async def test_register_model_version():
    """Verify endpoint registers model version from a run."""
    from app.notebooks.routes.notebook_routes import register_model_version, RegisterModelRequest

    mock_create_model = MagicMock()
    mock_create_model.status_code = 200

    mock_create_version = MagicMock()
    mock_create_version.status_code = 200
    mock_create_version.json.return_value = {
        "model_version": {
            "name": "churn_classifier",
            "version": "1",
            "status": "READY",
            "run_id": "run_abc",
        }
    }

    async def mock_post(self, url, **kwargs):
        if "registered-models/create" in url:
            return mock_create_model
        return mock_create_version

    with patch("httpx.AsyncClient.post", new=mock_post):
        req = RegisterModelRequest(
            run_id="run_abc",
            model_name="churn_classifier",
            artifact_path="model",
            description="First release",
        )
        res = await register_model_version(payload=req, guard=MagicMock())
        assert res["success"] is True
        assert res["model_name"] == "churn_classifier"
        assert res["version"] == "1"
        assert "run_abc" in res["source"]


