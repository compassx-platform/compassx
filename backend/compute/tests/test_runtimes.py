"""Tests for compute/runtimes.py."""
import pytest
from unittest.mock import patch

from compute.profiles import get_profile
from compute.runtimes import build_pod_spec, DUCKDB_VALID_PROFILES


def _make_pod(runtime: str, profile_id: str = "cloud-s", env: str = "local"):
    profile = get_profile(profile_id, env)
    return build_pod_spec(
        job_id="abc12345",
        user_id="user1",
        runtime=runtime,
        profile=profile,
        namespace="compassx-jobs",
        env=env,
    )


class TestPodImages:
    def test_spark_image(self):
        pod = _make_pod("spark")
        assert pod.spec.containers[0].image == "apache/spark:3.5.0"

    def test_flink_image(self):
        pod = _make_pod("flink")
        assert pod.spec.containers[0].image == "flink:1.18-scala_2.12"

    def test_ray_image(self):
        pod = _make_pod("ray")
        assert pod.spec.containers[0].image == "rayproject/ray:2.9.0"

    def test_duckdb_image(self):
        pod = _make_pod("duckdb", profile_id="local", env="local")
        assert pod.spec.containers[0].image == "compassx-compute-duckdb:latest"

    def test_acr_registry_prefix(self):
        with patch("app.compute.services.runtimes.compute_settings.COMPUTE_REGISTRY_PREFIX", "acrecgci.azurecr.io"):
            pod = _make_pod("duckdb", profile_id="local", env="local")
            assert pod.spec.containers[0].image == "acrecgci.azurecr.io/compassx-compute-duckdb:latest"

    def test_custom_image_override(self):
        profile = get_profile("cloud-s", "local")
        pod = build_pod_spec(
            job_id="abc12345",
            user_id="user1",
            runtime="spark",
            profile=profile,
            namespace="compassx-jobs",
            env="local",
            custom_image="my-registry/spark:custom",
        )
        assert pod.spec.containers[0].image == "my-registry/spark:custom"


class TestPodLabels:
    def test_required_labels(self):
        pod = _make_pod("ray")
        labels = pod.metadata.labels
        assert labels["app"] == "compassx"
        assert labels["runtime"] == "ray"
        assert labels["user"] == "user1"
        assert labels["compassx/job"] == "abc12345"


class TestMinioEnvVars:
    def _get_env_names(self, pod):
        return {e.name for e in pod.spec.containers[0].env}

    def test_spark_has_minio_vars(self):
        names = self._get_env_names(_make_pod("spark"))
        assert "AWS_ENDPOINT_URL" in names
        assert "AWS_ACCESS_KEY_ID" in names
        assert "AWS_SECRET_ACCESS_KEY" in names
        assert "AWS_DEFAULT_REGION" in names

    def test_flink_has_minio_vars(self):
        names = self._get_env_names(_make_pod("flink"))
        assert "AWS_ENDPOINT_URL" in names

    def test_ray_has_minio_vars(self):
        names = self._get_env_names(_make_pod("ray"))
        assert "AWS_ENDPOINT_URL" in names

    def test_duckdb_has_minio_vars(self):
        names = self._get_env_names(_make_pod("duckdb", profile_id="local", env="local"))
        assert "AWS_ENDPOINT_URL" in names


class TestImagePullPolicy:
    def test_local_env_uses_if_not_present(self):
        pod = _make_pod("spark", env="local")
        assert pod.spec.containers[0].image_pull_policy == "IfNotPresent"

    def test_cloud_env_uses_always(self):
        profile = get_profile("cloud-s", "cloud")
        pod = build_pod_spec(
            job_id="abc12345",
            user_id="user1",
            runtime="spark",
            profile=profile,
            namespace="compassx-jobs",
            env="cloud",
        )
        assert pod.spec.containers[0].image_pull_policy == "Always"


class TestGpuProfile:
    def test_gpu_profile_adds_nvidia_limit(self):
        profile = get_profile("gpu", "cloud")
        pod = build_pod_spec(
            job_id="abc12345",
            user_id="user1",
            runtime="spark",
            profile=profile,
            namespace="compassx-jobs",
            env="cloud",
        )
        limits = pod.spec.containers[0].resources.limits
        assert limits.get("nvidia.com/gpu") == "4"


class TestDuckDBValidation:
    def test_duckdb_invalid_with_cloud_l(self):
        profile = get_profile("cloud-l", "cloud")
        with pytest.raises(ValueError, match="DuckDB"):
            build_pod_spec(
                job_id="abc12345",
                user_id="user1",
                runtime="duckdb",
                profile=profile,
                namespace="compassx-jobs",
                env="cloud",
            )


class TestPodSpec:
    def test_restart_policy_never(self):
        pod = _make_pod("spark")
        assert pod.spec.restart_policy == "Never"
