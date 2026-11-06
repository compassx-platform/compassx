"""Import shim. The implementation lives under ``app.monitoring.infrastructure``."""
from app.monitoring.infrastructure.prometheus_exporter import render_prometheus_metrics

__all__ = ["render_prometheus_metrics"]
