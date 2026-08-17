"""Generates KernelSpec content for each runtime.

These are mounted as a ConfigMap into the EG pod so it knows how to
start kernels for each runtime type.

ConfigMap key naming: K8s ConfigMap keys cannot contain '/'.
Keys use double-dash as separator (e.g. spark_python--kernel.json).
The EG Deployment volume mount uses keyToPath items to map each flat
key to the correct directory path inside the container:
  spark_python--kernel.json -> spark_python/kernel.json
"""
import json

from kubernetes import client

from compassx.lookup import try_resolve_url_container

# Class lives inside the custom EG image (see Dockerfile.eg).
# Module path must be importable from within the EG container.
PROXY_CLASS_PATH = "compassx_process_proxy.CompassXProcessProxy"


def generate_kernel_json(
    runtime: str,
    proxy_class_path: str = PROXY_CLASS_PATH,
    session_token: str = None,
    catalog_api_url: str = None,
) -> dict:
    """Return kernel.json dict for the given runtime.

    Args:
        runtime: Runtime type (spark, ray, flink, duckdb)
        proxy_class_path: Process proxy class path
        session_token: Notebook session JWT token for volume access
        catalog_api_url: Catalog API base URL (e.g. http://catalog-service:5000/api/v1)
    """
    runtime_configs = {
        "spark": {
            "display_name": "Python (Spark)",
            "env": {
                "KERNEL_RUNTIME": "spark",
                "SPARK_HOME": "/opt/spark",
            },
        },
        "ray": {
            "display_name": "Python (Ray)",
            "env": {
                "KERNEL_RUNTIME": "ray",
            },
        },
        "flink": {
            "display_name": "Python (Flink)",
            "env": {
                "KERNEL_RUNTIME": "flink",
            },
        },
        "duckdb": {
            "display_name": "Python (DuckDB)",
            "env": {
                "KERNEL_RUNTIME": "duckdb",
            },
        },
    }

    cfg = runtime_configs.get(runtime)
    if cfg is None:
        raise ValueError(f"Unknown runtime: {runtime}")

    env = cfg["env"].copy()
    if session_token:
        env["NOTEBOOK_SESSION_TOKEN"] = session_token
        env["KERNEL_NOTEBOOK_SESSION_TOKEN"] = session_token
    if catalog_api_url:
        env["CATALOG_API_URL"] = catalog_api_url
        env["KERNEL_CATALOG_API_URL"] = catalog_api_url

    env.setdefault("NOTEBOOK_SESSION_TOKEN", session_token or "")
    env.setdefault("KERNEL_NOTEBOOK_SESSION_TOKEN", session_token or "")
    env.setdefault("CATALOG_API_URL", catalog_api_url or "")
    env.setdefault("KERNEL_CATALOG_API_URL", catalog_api_url or "")

    init_cmd = (
        "import sys; "
        "sys.argv = ['ipykernel_launcher', '--InteractiveShellApp.exec_lines', 'import services.compassx_sql as cx', '--InteractiveShellApp.exec_lines', '%load_ext services.compassx_sql', '-f', sys.argv[-1]]; "
        "import services.fsspec_cx; "
        "print('[CX] Volume protocol (cx://) registered'); "
        "from ipykernel import kernelapp; kernelapp.main()"
    )

    return {
        "display_name": cfg["display_name"],
        "language": "python",
        "metadata": {
            "process_proxy": {
                "class_name": proxy_class_path,
            }
        },
        "env": env,
        "argv": ["python", "-c", init_cmd, "{connection_file}"],
    }


RUNTIMES = ["spark", "ray", "flink", "duckdb"]


def configmap_key(runtime: str) -> str:
    return f"{runtime}_python--kernel.json"


def build_kernelspec_configmap(namespace: str, session_token: str = None, catalog_api_url: str = None) -> client.V1ConfigMap:
    """Build K8s ConfigMap containing all runtime kernel.json files."""
    import os

    if not session_token:
        session_token = os.environ.get("NOTEBOOK_SESSION_TOKEN") or os.environ.get("JUPYTER_TOKEN")
    if not catalog_api_url:
        catalog_api_url = try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"

    data = {}
    for runtime in RUNTIMES:
        data[configmap_key(runtime)] = json.dumps(
            generate_kernel_json(runtime, session_token=session_token, catalog_api_url=catalog_api_url),
            indent=2,
        )

    return client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(
            name="compassx-kernelspecs",
            namespace=namespace,
            labels={"app": "compassx", "compassx/component": "kernelspecs"},
        ),
        data=data,
    )
