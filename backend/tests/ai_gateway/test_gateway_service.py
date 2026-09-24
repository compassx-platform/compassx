"""Unit tests for AI Gateway Core Services (Rate Limiter, Guardrails, Failover)."""

import pytest
import time

from app.ai_gateway.services.guardrails import AIGuardrails
from app.ai_gateway.services.rate_limiter import SlidingWindowRateLimiter, RateLimitExceededError


def test_guardrails_pii_masking():
    raw_text = "Contact me at alice@company.com or 555-123-4567. Key is sk-1234567890123456789012."
    masked = AIGuardrails.mask_pii(raw_text)

    assert "alice@company.com" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "555-123-4567" not in masked
    assert "[REDACTED_PHONE]" in masked
    assert "sk-1234567890123456789012" not in masked
    assert "[REDACTED_SECRET]" in masked


def test_rate_limiter_rpm_enforcement():
    limiter = SlidingWindowRateLimiter()
    key = "test_endpoint_1"

    # Allow 3 requests per minute
    limiter.check_and_record(key, limit_rpm=3)
    limiter.check_and_record(key, limit_rpm=3)
    limiter.check_and_record(key, limit_rpm=3)

    # 4th request should raise RateLimitExceededError
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check_and_record(key, limit_rpm=3)

    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.retry_after_s > 0


def test_rate_limiter_tpm_enforcement():
    limiter = SlidingWindowRateLimiter()
    key = "test_endpoint_2"

    # Allow 1000 tokens per minute
    limiter.check_and_record(key, limit_tpm=1000, estimated_tokens=600)

    # 2nd request with 500 tokens exceeds 1000 limit
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check_and_record(key, limit_tpm=1000, estimated_tokens=500)

    assert "Token rate limit exceeded" in str(exc_info.value)
