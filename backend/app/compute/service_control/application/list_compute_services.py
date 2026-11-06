from concurrent.futures import ThreadPoolExecutor, wait

from app.compute.shared.support import _STATUS_TIMEOUT_SECONDS, _service_info, logger
from services.airflow.manager import get_airflow_manager
from services.base import ServicePhase, ServiceStatus
from services.enterprise_gateway.manager import get_eg_manager
from services.minio.manager import get_minio_manager


class ListComputeServices:
    def execute(self):
        services = [
            ("minio", "MinIO", get_minio_manager().get_status),
            ("enterprise-gateway", "Enterprise Gateway", get_eg_manager().get_status),
            ("airflow", "Airflow", get_airflow_manager().get_status),
        ]

        executor = ThreadPoolExecutor(max_workers=len(services))
        try:
            futures = {
                executor.submit(status_fn): (service_id, label)
                for service_id, label, status_fn in services
            }
            done, pending = wait(futures, timeout=_STATUS_TIMEOUT_SECONDS)
            results = []

            for future in done:
                service_id, label = futures[future]
                try:
                    status = future.result()
                    results.append(_service_info(service_id, label, status))
                except Exception as exc:
                    logger.warning("compute-service: %s status failed: %s", service_id, exc)
                    results.append(
                        _service_info(
                            service_id,
                            label,
                            ServiceStatus(
                                phase=ServicePhase.ERROR,
                                message=f"{label} status check failed.",
                                details={"error": str(exc)},
                            ),
                        )
                    )

            for future in pending:
                service_id, label = futures[future]
                logger.warning("compute-service: %s status timed out", service_id)
                results.append(
                    _service_info(
                        service_id,
                        label,
                        ServiceStatus(
                            phase=ServicePhase.ERROR,
                            message=f"{label} status check timed out.",
                            details={"timeout_seconds": _STATUS_TIMEOUT_SECONDS},
                        ),
                    )
                )

            return results
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def list_compute_services():
    return ListComputeServices().execute()
