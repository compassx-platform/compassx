from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from compassx.monitoring.repository import (
    InMemoryMetricRepository,
    MetricSample,
    PrometheusMetricRepository,
    SqliteMetricRepository,
)


def test_sqlite_repository_survives_reinstantiation(tmp_path):
    path = tmp_path / "metrics.db"
    timestamp = datetime.now(timezone.utc)
    repository = SqliteMetricRepository(path)
    repository.record([
        MetricSample("local-dev", "service", "docker:redis", "cpu", timestamp, 10),
        MetricSample("local-dev", "service", "docker:redis", "cpu", timestamp, 20),
        MetricSample("docker", "service", "docker:redis", "cpu", timestamp, 99),
    ])

    restarted_repository = SqliteMetricRepository(path)
    start = int((timestamp - timedelta(hours=1)).timestamp())
    end = int((timestamp + timedelta(hours=1)).timestamp())
    points = restarted_repository.query(
        "local-dev", "docker:redis", "cpu", start, end, 300
    )

    assert len(points) == 1
    assert points[0].value == 15


def test_sqlite_repository_rolls_five_minute_buckets_up(tmp_path):
    repository = SqliteMetricRepository(tmp_path / "metrics.db")
    base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    repository.record([
        MetricSample("local-dev", "service", "process:backend", "memory", base, 100),
        MetricSample(
            "local-dev", "service", "process:backend", "memory",
            base + timedelta(minutes=5), 300,
        ),
    ])
    start = int((base - timedelta(minutes=5)).timestamp())
    end = int((base + timedelta(minutes=10)).timestamp())

    points = repository.query(
        "local-dev", "process:backend", "memory", start, end, 600
    )

    assert len(points) <= 2
    assert sum(point.value for point in points) / len(points) == 200


def test_prometheus_repository_is_primary():
    fallback = InMemoryMetricRepository()
    repository = PrometheusMetricRepository("http://prometheus:9090", fallback)
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": "success",
        "data": {"result": [{"values": [[1_700_000_000, "12.5"]]}]},
    }

    with patch("compassx.monitoring.repository.httpx.get", return_value=response) as get:
        points = repository.query(
            "local-dev", "docker:redis", "cpu",
            1_699_999_000, 1_700_001_000, 300,
        )

    assert repository.connected is True
    assert points[0].value == 12.5
    assert "avg_over_time" in get.call_args.kwargs["params"]["query"]


def test_prometheus_repository_falls_back_when_unavailable():
    timestamp = datetime.now(timezone.utc)
    fallback = InMemoryMetricRepository()
    fallback.record([
        MetricSample(
            "local-dev", "service", "process:backend", "memory", timestamp, 256
        )
    ])
    repository = PrometheusMetricRepository("http://prometheus:9090", fallback)

    with patch(
        "compassx.monitoring.repository.httpx.get",
        side_effect=OSError("unreachable"),
    ):
        points = repository.query(
            "local-dev", "process:backend", "memory",
            int(timestamp.timestamp()) - 60,
            int(timestamp.timestamp()) + 60,
            300,
        )

    assert repository.connected is False
    assert points[0].value == 256


def test_prometheus_repository_without_fallback_returns_empty_when_unavailable():
    repository = PrometheusMetricRepository("http://prometheus:9090")
    with patch(
        "compassx.monitoring.repository.httpx.get",
        side_effect=OSError("unreachable"),
    ):
        points = repository.query(
            "local-dev", "docker:redis", "cpu",
            1_000_000, 2_000_000, 300,
        )
    assert repository.connected is False
    assert points == []
