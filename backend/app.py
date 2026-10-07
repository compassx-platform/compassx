import os

import uvicorn

if __name__ == "__main__":
    env = os.environ.get("COMPASSX_ENV", "").strip().lower()
    profile = os.environ.get("COMPASSX_PLATFORM_PROFILE", "").strip().lower()
    runtime = os.environ.get("COMPASSX_BACKEND_RUNTIME", "").strip().lower()

    # Disable auto-reload by default in production, staging, cloud, and Kubernetes environments
    is_prod = (
        runtime == "pod"
        or env in {"production", "prod", "staging", "k8s", "kubernetes"}
        or profile in {"kubernetes-cloud", "kubernetes-local", "cloud", "production"}
    )
    reload_env = os.environ.get("UVICORN_RELOAD", "0" if is_prod else "1").strip().lower()
    reload_enabled = not is_prod and (reload_env in {"1", "true", "yes", "on"})

    uvicorn_kwargs = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": reload_enabled,
    }
    if reload_enabled:
        app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
        if os.path.exists(app_dir):
            uvicorn_kwargs["reload_dirs"] = [app_dir]
        uvicorn_kwargs["reload_excludes"] = [
            "**/storage/**",
            "**/workspaces/**",
            "**/node_modules/**",
            "**/.git/**",
            "**/.cache/**",
            "**/dist/**",
            "**/build/**",
            "**/.venv/**",
            "**/__pycache__/**",
        ]

    uvicorn.run(**uvicorn_kwargs)
