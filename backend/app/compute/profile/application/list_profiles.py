from compute.config import compute_settings
from compute.profiles import get_available_profiles
from compute.schemas import ComputeProfileInfo


class ListProfiles:
    def execute(self, env: str | None):
        target_env = env or compute_settings.COMPASSX_ENV
        profiles = get_available_profiles(target_env)
        return [
            ComputeProfileInfo(
                id=profile.id,
                label=profile.label,
                description=profile.description,
                available=profile.available,
                reason=profile.unavailable_reason,
                resources={"requests": profile.requests, "limits": profile.limits},
            )
            for profile in profiles
        ]


def list_profiles(env=None):
    return ListProfiles().execute(env)
