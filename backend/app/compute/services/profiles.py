"""Compute profiles — resource limits per environment."""
import logging
from dataclasses import dataclass, field

from compute.config import compute_settings

logger = logging.getLogger(__name__)


class ProfileNotAvailableError(Exception):
    """Raised when a compute profile is not available in the current environment."""


@dataclass
class ComputeProfile:
    """Represents a compute profile with resource requests/limits."""

    id: str
    label: str
    description: str
    requests: dict
    limits: dict
    available: bool
    unavailable_reason: str | None = None


# Profile definitions keyed by (profile_id, env)
_LOCAL_PROFILES: dict[str, ComputeProfile] = {
    "local": ComputeProfile(
        id="local",
        label="Local",
        description="Laptop-safe profile for local development",
        requests={"cpu": "500m", "memory": "512Mi"},
        limits={"cpu": "500m", "memory": "2Gi"},
        available=True,
    ),
    "cloud-xs": ComputeProfile(
        id="cloud-xs",
        label="Cloud XS",
        description="Extra-small cloud-compatible profile for constrained clusters",
        requests={"cpu": "250m", "memory": "512Mi"},
        limits={"cpu": "1", "memory": "2Gi"},
        available=True,
    ),
    "cloud-s": ComputeProfile(
        id="cloud-s",
        label="Cloud S",
        description="Small cloud profile",
        requests={"cpu": "1", "memory": "1Gi"},
        limits={"cpu": "1", "memory": "4Gi"},
        available=True,
    ),
    "cloud-l": ComputeProfile(
        id="cloud-l",
        label="Cloud L",
        description="Large cloud profile — not available locally",
        requests={"cpu": "2", "memory": "2Gi"},
        limits={"cpu": "2", "memory": "6Gi"},
        available=False,
        unavailable_reason="Cloud L requires a cloud environment",
    ),
    "gpu": ComputeProfile(
        id="gpu",
        label="GPU",
        description="GPU-accelerated profile — not available locally",
        requests={"cpu": "4", "memory": "32Gi"},
        limits={"cpu": "4", "memory": "64Gi", "nvidia.com/gpu": "4"},
        available=False,
        unavailable_reason="GPU profile is not available in local environment",
    ),
}

_CLOUD_PROFILES: dict[str, ComputeProfile] = {
    "local": ComputeProfile(
        id="local",
        label="Local",
        description="Local profile — only valid in local environment",
        requests={"cpu": "500m", "memory": "512Mi"},
        limits={"cpu": "500m", "memory": "2Gi"},
        available=False,
        unavailable_reason="Local profile is only valid in local environment",
    ),
    "cloud-xs": ComputeProfile(
        id="cloud-xs",
        label="Cloud XS",
        description="Extra-small cloud profile for constrained clusters",
        requests={"cpu": "250m", "memory": "512Mi"},
        limits={"cpu": "1", "memory": "2Gi"},
        available=True,
    ),
    "cloud-s": ComputeProfile(
        id="cloud-s",
        label="Cloud S",
        description="Small cloud profile",
        requests={"cpu": "4", "memory": "16Gi"},
        limits={"cpu": "4", "memory": "32Gi"},
        available=True,
    ),
    "cloud-l": ComputeProfile(
        id="cloud-l",
        label="Cloud L",
        description="Large cloud profile",
        requests={"cpu": "16", "memory": "64Gi"},
        limits={"cpu": "16", "memory": "128Gi"},
        available=True,
    ),
    "gpu": ComputeProfile(
        id="gpu",
        label="GPU",
        description="GPU-accelerated profile",
        requests={"cpu": "4", "memory": "32Gi"},
        limits={"cpu": "4", "memory": "64Gi", "nvidia.com/gpu": "4"},
        available=True,
    ),
}


def _profiles_for_env(env: str) -> dict[str, ComputeProfile]:
    """Return the profile map for the given environment."""
    return _LOCAL_PROFILES if env == "local" else _CLOUD_PROFILES


def get_profile(profile_id: str, env: str) -> ComputeProfile:
    """Return a ComputeProfile; raise ProfileNotAvailableError if unavailable."""
    profiles = _profiles_for_env(env)
    profile = profiles.get(profile_id)
    if profile is None:
        raise ProfileNotAvailableError(f"Unknown profile: {profile_id}")
    if not profile.available:
        raise ProfileNotAvailableError(
            profile.unavailable_reason or f"Profile {profile_id} not available in {env} environment"
        )
    logger.debug("Profile resolved: id=%s env=%s", profile_id, env)
    return profile


def get_available_profiles(env: str) -> list[ComputeProfile]:
    """Return all profiles (available and unavailable) for UI display."""
    return list(_profiles_for_env(env).values())
