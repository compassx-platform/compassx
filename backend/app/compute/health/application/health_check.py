from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from fastapi import Request
from fastapi.responses import JSONResponse

from app.compute.shared.support import _STATUS_TIMEOUT_SECONDS, _active_driver, logger
from compute.config import compute_settings
from compute.k8s_client import get_k8s_client


class HealthCheck:
    def execute(self, req_context: Request):
        driver = _active_driver(req_context)

        if driver == "docker":
            def check_docker() -> None:
                import docker

                client = docker.from_env()
                client.ping()

            try:
                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    executor.submit(check_docker).result(timeout=_STATUS_TIMEOUT_SECONDS)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                logger.debug("Docker: health check passed")
                return {"status": "ok", "driver": "docker", "docker": "reachable"}
            except Exception as exc:
                logger.warning("Docker: health check failed: %s", exc)
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "degraded",
                        "driver": "docker",
                        "docker": "unreachable",
                        "message": "Docker daemon not reachable. Ensure Docker Desktop is running.",
                    },
                )

        if driver == "local":
            return {"status": "ok", "driver": "local"}

        def check_kubernetes() -> None:
            k8s = get_k8s_client()
            ns = compute_settings.COMPASSX_NAMESPACE or "compassx"
            try:
                k8s.core().list_namespaced_pod(namespace=ns, limit=1, _request_timeout=_STATUS_TIMEOUT_SECONDS)
            except Exception:
                k8s.core().get_api_resources(_request_timeout=_STATUS_TIMEOUT_SECONDS)

        try:
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                executor.submit(check_kubernetes).result(timeout=_STATUS_TIMEOUT_SECONDS)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            logger.debug("K8s: health check passed")
            return {"status": "ok", "driver": "kubernetes", "kubernetes": "reachable"}
        except FutureTimeoutError:
            logger.warning("K8s: health check timed out")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "driver": "kubernetes",
                    "kubernetes": "unreachable",
                    "message": "Kubernetes health check timed out.",
                },
            )
        except Exception as exc:
            logger.warning("K8s: health check failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "driver": "kubernetes",
                    "kubernetes": "unreachable",
                    "message": "Kubernetes not reachable." if compute_settings.is_k8s() else "Kubernetes not connected. Start minikube.",
                },
            )


def health_check(req_context):
    return HealthCheck().execute(req_context)
