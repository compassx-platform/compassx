from __future__ import annotations

import sqlite3
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from compassx.monitoring.models import MetricPoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricSample:
    profile: str
    resource_kind: str
    resource_id: str
    metric: str
    timestamp: datetime
    value: float


class MetricRepository(ABC):
    connected: bool = False

    @abstractmethod
    def record(self, samples: list[MetricSample]) -> None: ...

    @abstractmethod
    def query(
        self, profile: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> list[MetricPoint]: ...


def _aggregate(samples: list[MetricSample], start: int, end: int, step: int) -> list[MetricPoint]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for sample in samples:
        timestamp = int(sample.timestamp.timestamp())
        if start <= timestamp <= end:
            buckets[timestamp // step].append(sample.value)
    return [
        MetricPoint(
            datetime.fromtimestamp(bucket * step, timezone.utc),
            round(sum(values) / len(values), 2),
        )
        for bucket, values in sorted(buckets.items())
    ]


class InMemoryMetricRepository(MetricRepository):
    def __init__(self, max_samples: int = 100_000) -> None:
        self._samples: list[MetricSample] = []
        self._max_samples = max_samples

    def record(self, samples: list[MetricSample]) -> None:
        self._samples.extend(samples)
        if len(self._samples) > self._max_samples:
            del self._samples[:-self._max_samples]

    def query(
        self, profile: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> list[MetricPoint]:
        matching = [
            sample for sample in self._samples
            if sample.profile == profile
            and sample.resource_id == resource_id
            and sample.metric == metric
        ]
        return _aggregate(matching, start, end, max(1, step))


class SqliteMetricRepository(MetricRepository):
    """Durable five-minute aggregates for local profile monitoring."""

    def __init__(self, path: Path, *, bucket_seconds: int = 300, retention_days: int = 30) -> None:
        self._path = path
        self._bucket_seconds = bucket_seconds
        self._retention_seconds = retention_days * 86400
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metric_samples (
                    profile TEXT NOT NULL,
                    resource_kind TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    bucket_start INTEGER NOT NULL,
                    value_sum REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    last_value REAL NOT NULL,
                    PRIMARY KEY (profile, resource_id, metric, bucket_start)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_metric_samples_lookup "
                "ON metric_samples(profile, resource_id, metric, bucket_start)"
            )

    def record(self, samples: list[MetricSample]) -> None:
        if not samples:
            return
        rows = [
            (
                sample.profile, sample.resource_kind, sample.resource_id, sample.metric,
                int(sample.timestamp.timestamp()) // self._bucket_seconds * self._bucket_seconds,
                sample.value, 1, sample.value, sample.value, sample.value,
            )
            for sample in samples
        ]
        cutoff = int(datetime.now(timezone.utc).timestamp()) - self._retention_seconds
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO metric_samples (
                    profile, resource_kind, resource_id, metric, bucket_start,
                    value_sum, sample_count, min_value, max_value, last_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile, resource_id, metric, bucket_start) DO UPDATE SET
                    value_sum = value_sum + excluded.value_sum,
                    sample_count = sample_count + 1,
                    min_value = MIN(min_value, excluded.min_value),
                    max_value = MAX(max_value, excluded.max_value),
                    last_value = excluded.last_value
                """,
                rows,
            )
            connection.execute("DELETE FROM metric_samples WHERE bucket_start < ?", (cutoff,))

    def query(
        self, profile: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> list[MetricPoint]:
        effective_step = max(self._bucket_seconds, step)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT CAST(bucket_start / ? AS INTEGER) * ? AS period,
                       SUM(value_sum) / SUM(sample_count) AS average
                FROM metric_samples
                WHERE profile = ? AND resource_id = ? AND metric = ?
                  AND bucket_start BETWEEN ? AND ?
                GROUP BY period
                ORDER BY period
                """,
                (effective_step, effective_step, profile, resource_id, metric, start, end),
            ).fetchall()
        return [
            MetricPoint(datetime.fromtimestamp(row[0], timezone.utc), round(row[1], 2))
            for row in rows
        ]


def _prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class PrometheusMetricRepository(MetricRepository):
    """Prometheus query backend with a durable degraded-mode repository."""

    def __init__(
        self, url: str, fallback: MetricRepository, *, timeout_seconds: float = 3
    ) -> None:
        self._url = url.rstrip("/")
        self._fallback = fallback
        self._timeout = timeout_seconds
        self.connected = False

    def record(self, samples: list[MetricSample]) -> None:
        # Prometheus pulls live gauges from the monitoring exporter. The fallback
        # is written here so local history remains available during an outage.
        self._fallback.record(samples)

    def query(
        self, profile: str, resource_id: str, metric: str, start: int, end: int, step: int
    ) -> list[MetricPoint]:
        selector = (
            'compassx_resource_metric{'
            f'profile="{_prometheus_label(profile)}",'
            f'resource_id="{_prometheus_label(resource_id)}",'
            f'metric="{_prometheus_label(metric)}"'
            '}'
        )
        window = max(300, step)
        query = (
            "avg by (profile, resource_id, metric) "
            f"(avg_over_time({selector}[{window}s]))"
        )
        try:
            response = httpx.get(
                f"{self._url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": max(60, step),
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "success":
                raise RuntimeError(payload.get("error") or "Prometheus query failed")
            self.connected = True
            result = payload.get("data", {}).get("result", [])
            if result:
                return [
                    MetricPoint(
                        datetime.fromtimestamp(float(timestamp), timezone.utc),
                        round(float(value), 2),
                    )
                    for timestamp, value in result[0].get("values", [])
                    if value not in {"NaN", "Inf", "-Inf"}
                ]
        except Exception as exc:
            self.connected = False
            logger.warning("Prometheus history query unavailable: %s", exc)
        return self._fallback.query(profile, resource_id, metric, start, end, step)
