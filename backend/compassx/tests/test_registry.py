import pytest

from compassx.models import ServiceEndpoint, ServiceMode, ServiceNotFoundError
from compassx.registry import (
    YamlServiceRegistry,
    load_profile,
    load_service_definitions,
)
from compassx.registry.profile import list_profiles

DEFS = {
    "backend": {
        "local": {"host": "localhost", "port": 8000},
        "docker": {"host": "backend", "port": 8000},
        "kubernetes": {
            "host": "compassx-backend-service.compassx-jobs.svc.cluster.local",
            "port": 8000,
        },
    },
    "postgres": {
        "local": {"host": "localhost", "port": 5432, "protocol": "postgresql"},
        "docker": {"host": "postgres", "port": 5432, "protocol": "postgresql"},
        "kubernetes": {
            "host": "compassx-postgres.compassx-jobs.svc.cluster.local",
            "port": 5432,
            "protocol": "postgresql",
        },
    },
}


class TestEndpointResolution:
    def test_local_mode(self):
        reg = YamlServiceRegistry(DEFS, {"backend": ServiceMode.LOCAL})
        ep = reg.get_service("backend")
        assert ep == ServiceEndpoint(host="localhost", port=8000, protocol="http")
        assert ep.base_url == "http://localhost:8000"

    def test_docker_mode(self):
        reg = YamlServiceRegistry(DEFS, {"backend": ServiceMode.DOCKER})
        assert reg.get_service("backend").host == "backend"

    def test_kubernetes_mode(self):
        reg = YamlServiceRegistry(DEFS, {"backend": ServiceMode.KUBERNETES})
        assert "svc.cluster.local" in reg.get_service("backend").host

    def test_hybrid_modes_resolve_independently(self):
        reg = YamlServiceRegistry(
            DEFS,
            {"backend": ServiceMode.LOCAL, "postgres": ServiceMode.DOCKER},
        )
        assert reg.get_service("backend").host == "localhost"
        assert reg.get_service("postgres").host == "postgres"

    def test_default_mode_used_when_service_not_in_profile(self):
        reg = YamlServiceRegistry(DEFS, {}, default_mode=ServiceMode.DOCKER)
        assert reg.get_service("postgres").host == "postgres"

    def test_protocol_passthrough(self):
        reg = YamlServiceRegistry(DEFS, {"postgres": ServiceMode.LOCAL})
        ep = reg.get_service("postgres")
        assert ep.protocol == "postgresql"
        assert ep.address == "localhost:5432"

    def test_unknown_service_raises(self):
        reg = YamlServiceRegistry(DEFS, {})
        with pytest.raises(ServiceNotFoundError):
            reg.get_service("nope")

    def test_missing_mode_entry_raises(self):
        defs = {"only-local": {"local": {"host": "localhost", "port": 1}}}
        reg = YamlServiceRegistry(defs, {"only-local": ServiceMode.DOCKER})
        with pytest.raises(ServiceNotFoundError):
            reg.get_service("only-local")

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("COMPASSX_SERVICE_BACKEND_LOCAL_HOST", "10.0.0.5")
        monkeypatch.setenv("COMPASSX_SERVICE_BACKEND_LOCAL_PORT", "18080")
        reg = YamlServiceRegistry(DEFS, {"backend": ServiceMode.LOCAL})
        ep = reg.get_service("backend")
        assert ep.host == "10.0.0.5"
        assert ep.port == 18080

    def test_list_services(self):
        reg = YamlServiceRegistry(DEFS, {})
        assert reg.list_services() == ["backend", "postgres"]


class TestBundledFiles:
    """Validate the real services.yaml + profiles ship consistent data."""

    def test_services_yaml_loads_all_modes(self):
        defs = load_service_definitions()
        assert defs, "services.yaml must define services"
        for name, definition in defs.items():
            for mode in ("local", "docker", "kubernetes"):
                assert mode in definition, f"{name} missing mode {mode}"
                assert "host" in definition[mode]
                assert "port" in definition[mode]

    @pytest.mark.parametrize("profile_name", ["local-dev", "docker", "kubernetes-local", "kubernetes-cloud"])
    def test_profiles_load_and_resolve(self, profile_name):
        profile = load_profile(profile_name)
        reg = YamlServiceRegistry.from_files(profile)
        for svc in reg.list_services():
            ep = reg.get_service(svc)
            assert ep.host and ep.port

    def test_local_dev_profile_hybrid(self):
        profile = load_profile("local-dev")
        assert profile.mode_for("backend") == ServiceMode.LOCAL
        assert profile.mode_for("postgres") == ServiceMode.DOCKER
        assert profile.docker_ensure_images is True
        # Backend runs on the host -> host perspective: docker services are
        # reached via published localhost ports.
        reg = YamlServiceRegistry.from_files(profile)
        assert reg.get_service("backend").host == "localhost"
        assert reg.get_service("postgres").host == "localhost"
        # Container perspective (e.g. backend inside compose) uses hostnames.
        reg_container = YamlServiceRegistry.from_files(profile, perspective="container")
        assert reg_container.get_service("postgres").host == "postgres"

    def test_profile_compute_driver(self):
        assert load_profile("local-dev").compute_driver == "docker"
        assert load_profile("kubernetes-local").compute_driver == "kubernetes"
        assert load_profile("kubernetes-cloud").compute_driver == "kubernetes"

    def test_profile_driver_override(self):
        profile = load_profile("kubernetes-local")
        profile.compute_overrides["duckdb"] = "local"
        assert profile.driver_for_runtime("duckdb") == "local"
        assert profile.driver_for_runtime("spark") == "kubernetes"

    def test_list_profiles(self):
        names = list_profiles()
        assert {"local-dev", "docker", "kubernetes-local", "kubernetes-cloud"} <= set(names)

    def test_unknown_profile_raises(self):
        from compassx.models import PlatformError

        with pytest.raises(PlatformError):
            load_profile("does-not-exist")

    def test_profile_env_var(self, monkeypatch):
        monkeypatch.setenv("COMPASSX_PLATFORM_PROFILE", "docker")
        assert load_profile().name == "docker"
