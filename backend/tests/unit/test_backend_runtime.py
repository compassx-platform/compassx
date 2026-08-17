import pytest

from services import backend_runtime


@pytest.fixture()
def restore_runtime():
    original = backend_runtime.compute_settings.COMPASSX_BACKEND_RUNTIME
    yield
    backend_runtime.compute_settings.COMPASSX_BACKEND_RUNTIME = original


def test_backend_service_url_host_mode(restore_runtime):
    backend_runtime.compute_settings.COMPASSX_BACKEND_RUNTIME = "host"
    assert backend_runtime.backend_service_url() == "http://127.0.0.1:8000"
    assert backend_runtime.backend_catalog_url() == "http://127.0.0.1:8000/api/v1/catalog"


def test_backend_service_url_pod_mode(restore_runtime, monkeypatch):
    backend_runtime.compute_settings.COMPASSX_BACKEND_RUNTIME = "pod"
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    assert backend_runtime.backend_service_url("compassx-jobs") == (
        "http://compassx-backend-service.compassx-jobs.svc.cluster.local:8000"
    )
    assert backend_runtime.backend_catalog_url("compassx-jobs") == (
        "http://compassx-backend-service.compassx-jobs.svc.cluster.local:8000/api/v1/catalog"
    )


def test_runtime_info_reports_mode(restore_runtime, monkeypatch):
    backend_runtime.compute_settings.COMPASSX_BACKEND_RUNTIME = "pod"
    monkeypatch.setattr(backend_runtime, "_backend_is_ready", lambda namespace: True)
    info = backend_runtime.get_runtime_info()
    assert info.mode == "pod"
    assert info.ready is True

