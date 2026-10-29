"""Preview URL and Docker runtime selection."""
from types import SimpleNamespace

from app.config import settings
from app.services.ingress_service import IngressService, preview_url_from_endpoints


def test_preview_uses_the_published_gateway_port():
    url = preview_url_from_endpoints(
        {"8080": "http://localhost:56574", "9201": "http://localhost:56575"},
        "http://localhost:9201/",
    )
    assert url == "http://localhost:56574/"


def test_preview_falls_back_when_no_endpoint_is_published():
    assert preview_url_from_endpoints({}, "http://localhost:9201") == "http://localhost:9201/"


def test_docker_profile_does_not_need_the_docker_cli(monkeypatch):
    monkeypatch.setattr(settings, "APP_RUNNER_MODE", "")
    monkeypatch.delenv("APP_RUNNER_MODE", raising=False)
    monkeypatch.setenv("COMPASSX_PLATFORM_PROFILE", "docker")

    def _no_cli(*_args, **_kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr("app.services.ingress_service.subprocess.run", _no_cli)
    assert IngressService().get_active_mode() == "docker"


def test_explicit_local_mode_wins_over_the_docker_profile(monkeypatch):
    monkeypatch.setattr(settings, "APP_RUNNER_MODE", "local")
    monkeypatch.setenv("COMPASSX_PLATFORM_PROFILE", "docker")
    assert IngressService().get_active_mode() == "local"


def test_preview_for_app_reads_sandbox_endpoints(monkeypatch):
    app = SimpleNamespace(id="app_123", slug="demo")
    sandbox = SimpleNamespace(endpoints={"8080": "http://localhost:44000", "9201": "http://localhost:44001"})

    class _Service:
        def find_active_sandbox(self, **_kwargs):
            return sandbox

    monkeypatch.setattr("app.sandbox.service.sandbox_service", _Service())
    monkeypatch.setattr(settings, "APP_RUNNER_MODE", "docker")
    url = IngressService().preview_url_for_app(app)
    assert url == "http://localhost:44000/"
