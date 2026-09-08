"""Tests for compute/profiles.py."""
import pytest

from compute.profiles import (
    ComputeProfile,
    ProfileNotAvailableError,
    get_available_profiles,
    get_profile,
)


class TestLocalProfiles:
    def test_local_profile_available(self):
        p = get_profile("local", "local")
        assert p.available is True
        assert p.id == "local"

    def test_cloud_s_available_locally(self):
        p = get_profile("cloud-s", "local")
        assert p.available is True

    def test_cloud_l_blocked_locally(self):
        with pytest.raises(ProfileNotAvailableError):
            get_profile("cloud-l", "local")

    def test_gpu_blocked_locally(self):
        with pytest.raises(ProfileNotAvailableError):
            get_profile("gpu", "local")

    def test_local_resource_limits(self):
        p = get_profile("local", "local")
        assert p.requests["cpu"] == "500m"
        assert p.requests["memory"] == "512Mi"
        assert p.limits["memory"] == "2Gi"

    def test_cloud_s_local_resource_limits(self):
        p = get_profile("cloud-s", "local")
        assert p.requests["cpu"] == "1"
        assert p.requests["memory"] == "1Gi"
        assert p.limits["memory"] == "4Gi"


class TestCloudProfiles:
    def test_cloud_s_available_in_cloud(self):
        p = get_profile("cloud-s", "cloud")
        assert p.available is True
        assert p.requests["cpu"] == "4"
        assert p.requests["memory"] == "16Gi"
        assert p.limits["memory"] == "32Gi"

    def test_cloud_l_available_in_cloud(self):
        p = get_profile("cloud-l", "cloud")
        assert p.available is True
        assert p.requests["cpu"] == "16"
        assert p.requests["memory"] == "64Gi"

    def test_gpu_available_in_cloud(self):
        p = get_profile("gpu", "cloud")
        assert p.available is True
        assert p.limits.get("nvidia.com/gpu") == "4"

    def test_local_profile_blocked_in_cloud(self):
        with pytest.raises(ProfileNotAvailableError):
            get_profile("local", "cloud")


class TestGetAvailableProfiles:
    def test_returns_all_four_profiles(self):
        profiles = get_available_profiles("local")
        ids = {p.id for p in profiles}
        assert ids == {"local", "cloud-xs", "cloud-s", "cloud-l", "gpu"}

    def test_unknown_profile_raises(self):
        with pytest.raises(ProfileNotAvailableError):
            get_profile("unknown-profile", "local")
