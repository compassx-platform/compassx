import os
import shutil
import subprocess

import uvicorn


def _install_extra_cas() -> None:
    """Trust certificates mounted for a corporate TLS intercept proxy."""
    src = os.environ.get("COMPASSX_EXTRA_CA_DIR", "/usr/local/share/ca-certificates/extra")
    if not os.path.isdir(src):
        return
    dest_root = "/usr/local/share/ca-certificates"
    copied = False
    try:
        names = os.listdir(src)
    except OSError:
        return
    for name in names:
        if not name.endswith((".crt", ".pem")):
            continue
        target = os.path.join(dest_root, f"compassx-{name if name.endswith('.crt') else name + '.crt'}")
        try:
            shutil.copyfile(os.path.join(src, name), target)
            copied = True
        except OSError:
            continue
    if copied:
        subprocess.run(["update-ca-certificates"], check=False)


def _ensure_docker_cli() -> None:
    """The dev terminal execs with the docker CLI. The image ships the SDK only."""
    if shutil.which("docker"):
        return
    if not os.path.exists("/var/run/docker.sock") and not os.environ.get("DOCKER_HOST"):
        return
    archive = "/tmp/docker-cli.tgz"
    url = os.environ.get(
        "COMPASSX_DOCKER_CLI_URL",
        "https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz",
    )
    try:
        subprocess.run(["curl", "-fsSL", "--retry", "2", "-o", archive, url], check=True, timeout=120)
        subprocess.run(["tar", "-xzf", archive, "-C", "/tmp", "docker/docker"], check=True, timeout=60)
        shutil.copyfile("/tmp/docker/docker", "/usr/local/bin/docker")
        os.chmod("/usr/local/bin/docker", 0o755)
    except Exception as exc:
        print(f"Docker CLI install skipped: {exc}", flush=True)


if __name__ == "__main__":
    _install_extra_cas()
    _ensure_docker_cli()

    env = os.environ.get("COMPASSX_ENV", "").strip().lower()
    profile = os.environ.get("COMPASSX_PLATFORM_PROFILE", "").strip().lower()
    runtime = os.environ.get("COMPASSX_BACKEND_RUNTIME", "").strip().lower()

    # Disable auto-reload by default in production, staging, cloud, and Kubernetes environments.
    # Docker Compose sets COMPASSX_ENV=local, and a reload that watches cloned app
    # repos wedges the API. Reload there only when UVICORN_RELOAD is set explicitly.
    is_prod = (
        runtime == "pod"
        or env in {"production", "prod", "staging", "k8s", "kubernetes"}
        or profile in {"kubernetes-cloud", "kubernetes-local", "cloud", "production", "docker", "compose", "docker-compose"}
    )
    explicit_reload = os.environ.get("UVICORN_RELOAD")
    if explicit_reload is None:
        reload_enabled = not is_prod
    else:
        reload_enabled = explicit_reload.strip().lower() in {"1", "true", "yes", "on"}

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
