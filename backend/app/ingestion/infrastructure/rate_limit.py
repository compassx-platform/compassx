"""Per-connection token bucket. One registry for the process."""
from __future__ import annotations

import threading
import time
from typing import Dict


class _TokenBucket:
    """Thread-safe token bucket — refilled at `rate_rps` tokens/second."""

    def __init__(self, rate_rps: float):
        self._rate = max(rate_rps, 0.1)
        self._tokens = self._rate
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
        # Sleep outside the lock for the fractional amount needed
        sleep_for = (1.0 - self._tokens) / self._rate
        time.sleep(sleep_for)
        with self._lock:
            self._tokens = 0.0


# Cache buckets per connection_id so concurrent workers for the same connection share one.
_bucket_registry: Dict[str, _TokenBucket] = {}
_bucket_lock = threading.Lock()


def _get_bucket(connection_id: str, rate_rps: float) -> _TokenBucket:
    with _bucket_lock:
        if connection_id not in _bucket_registry:
            _bucket_registry[connection_id] = _TokenBucket(rate_rps)
        return _bucket_registry[connection_id]
