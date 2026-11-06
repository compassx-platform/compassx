from fastapi import Request

from compute.config import compute_settings


class RuntimeInfo:
    def execute(self, req_context: Request):
        from compassx.lookup import try_resolve_url

        backend_url = try_resolve_url("backend", "http://localhost:8000")
        profile_name = "unknown"
        try:
            platform = getattr(req_context.app.state, "platform", None)
            if platform:
                profile_name = platform.profile.name
        except Exception:
            pass
        return {
            "profile": profile_name,
            "backend_url": backend_url,
            "compassx_env": compute_settings.COMPASSX_ENV,
        }


def runtime_info(req_context):
    return RuntimeInfo().execute(req_context)
