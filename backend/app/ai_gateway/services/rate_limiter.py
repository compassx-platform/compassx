"""In-memory sliding-window Rate Limiter for AI Gateway."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple


class RateLimitExceededError(Exception):
    def __init__(self, message: str, retry_after_s: int = 60):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class SlidingWindowRateLimiter:
    """Tracks and throttles RPM (Requests Per Minute) and TPM (Tokens Per Minute)."""

    def __init__(self):
        # key -> list of timestamps (seconds)
        self._request_history: Dict[str, List[float]] = defaultdict(list)
        # key -> list of (timestamp, token_count)
        self._token_history: Dict[str, List[Tuple[float, int]]] = defaultdict(list)

    def check_and_record(
        self,
        key: str,
        limit_rpm: int | None = None,
        limit_tpm: int | None = None,
        estimated_tokens: int = 1,
    ) -> None:
        """Check if request conforms to rate limits and record usage."""
        now = time.time()
        window = 60.0  # 1 minute

        # 1. Clean old entries
        self._request_history[key] = [t for t in self._request_history[key] if now - t < window]
        self._token_history[key] = [(t, count) for (t, count) in self._token_history[key] if now - t < window]

        # 2. Check RPM
        if limit_rpm is not None:
            current_rpm = len(self._request_history[key])
            if current_rpm >= limit_rpm:
                oldest = self._request_history[key][0]
                retry_after = max(1, int(window - (now - oldest)))
                raise RateLimitExceededError(
                    f"Rate limit exceeded: {current_rpm}/{limit_rpm} requests per minute.",
                    retry_after_s=retry_after,
                )

        # 3. Check TPM
        if limit_tpm is not None:
            current_tpm = sum(count for (_, count) in self._token_history[key])
            if current_tpm + estimated_tokens > limit_tpm:
                oldest = self._token_history[key][0][0] if self._token_history[key] else now
                retry_after = max(1, int(window - (now - oldest)))
                raise RateLimitExceededError(
                    f"Token rate limit exceeded: {current_tpm}/{limit_tpm} tokens per minute.",
                    retry_after_s=retry_after,
                )

        # 4. Record
        self._request_history[key].append(now)
        self._token_history[key].append((now, estimated_tokens))


# Global rate limiter instance
gateway_rate_limiter = SlidingWindowRateLimiter()
