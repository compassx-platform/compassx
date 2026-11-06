"""Wires a request's resource manager into ``MonitoringService``."""
from app.monitoring.service import MonitoringService


def monitoring_service(resource_manager) -> MonitoringService:
    return MonitoringService(resource_manager)
