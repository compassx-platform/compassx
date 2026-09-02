from time import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.dependencies import get_monitoring_resource_manager
from app.monitoring.schemas import (
    GroupedTimeseriesResponse,
    HealthResponse,
    Overview,
    Resource,
    TimeseriesResponse,
)
from app.monitoring.service import MonitoringService
from app.monitoring.exporter import render_prometheus_metrics

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


def get_monitoring_service(
    resource_manager=Depends(get_monitoring_resource_manager),
) -> MonitoringService:
    return MonitoringService(resource_manager)


@router.get("/export", include_in_schema=False)
def export_metrics(resource_manager=Depends(get_monitoring_resource_manager)):
    return Response(
        content=render_prometheus_metrics(resource_manager),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/overview", response_model=Overview)
def overview(service: MonitoringService = Depends(get_monitoring_service)):
    return service.overview()


@router.get("/nodes", response_model=list[Resource])
def nodes(service: MonitoringService = Depends(get_monitoring_service)):
    return service.resources("node")


@router.get("/platform", response_model=list[Resource])
def platform(service: MonitoringService = Depends(get_monitoring_service)):
    return service.resources("platform")


@router.get("/services", response_model=list[Resource])
def services(service: MonitoringService = Depends(get_monitoring_service)):
    return service.resources("service")


def _find_resource(resource_id: str, kind: str, service: MonitoringService) -> Resource:
    result = next((item for item in service.resources(kind) if item.id == resource_id), None)
    if not result:
        raise HTTPException(404, f"{kind.title()} not found")
    return result


@router.get("/services/{resource_id}", response_model=Resource)
def service_resource(
    resource_id: str, service: MonitoringService = Depends(get_monitoring_service)
):
    return _find_resource(resource_id, "service", service)


@router.get("/nodes/{resource_id}", response_model=Resource)
def node_resource(
    resource_id: str, service: MonitoringService = Depends(get_monitoring_service)
):
    return _find_resource(resource_id, "node", service)


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    resource_type: str = Query(..., pattern="^(platform|node|service)$"),
    resource_id: str = Query(..., min_length=1, max_length=120),
    metric: str = Query(..., pattern="^(cpu|memory|memory_limit|network_in|network_out|disk_read|disk_write)$"),
    start: int = Query(0, ge=0),
    end: int = Query(0, ge=0),
    resolution: int = Query(60, ge=1, le=86400),
    service: MonitoringService = Depends(get_monitoring_service),
):
    if end <= start:
        end = int(time())
        start = end - 8 * 3600
    return service.timeseries(resource_type, resource_id, metric, start, end, resolution)


@router.get("/timeseries/services", response_model=GroupedTimeseriesResponse)
def service_timeseries(
    metric: str = Query(..., pattern="^(cpu|memory|memory_limit|network_in|network_out|disk_read|disk_write)$"),
    start: int = Query(0, ge=0),
    end: int = Query(0, ge=0),
    resolution: int = Query(60, ge=60, le=86400),
    service: MonitoringService = Depends(get_monitoring_service),
):
    if end <= start:
        end = int(time())
        start = end - 8 * 3600
    return service.service_timeseries(metric, start, end, resolution)


@router.get("/timeseries/nodes", response_model=GroupedTimeseriesResponse)
def node_timeseries(
    metric: str = Query(..., pattern="^(cpu|memory|memory_limit|network_in|network_out|disk_read|disk_write)$"),
    start: int = Query(0, ge=0),
    end: int = Query(0, ge=0),
    resolution: int = Query(60, ge=60, le=86400),
    service: MonitoringService = Depends(get_monitoring_service),
):
    if end <= start:
        end = int(time())
        start = end - 8 * 3600
    return service.node_timeseries(metric, start, end, resolution)


@router.get("/health", response_model=HealthResponse)
def health(service: MonitoringService = Depends(get_monitoring_service)):
    return HealthResponse(
        status="Healthy",
        prometheus="Connected" if service.resource_manager.prometheus_connected else "Disconnected",
        runtime=service.resource_manager.source,
        message="Prometheus history is active" if service.resource_manager.prometheus_connected else "Prometheus is disconnected",
    )
