"""AI Guardrails: PII Detection, Redaction, and Safety Filters."""

from __future__ import annotations

import re
from typing import Any

# Regex patterns for common PII
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
API_KEY_REGEX = re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z-_]{35})\b")


class AIGuardrails:
    """Detects and masks sensitive information in user messages."""

    @staticmethod
    def mask_pii(text: str) -> str:
        """Replace detected PII with masked tokens."""
        if not text:
            return text

        masked = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        masked = CREDIT_CARD_REGEX.sub("[REDACTED_CREDIT_CARD]", masked)
        masked = SSN_REGEX.sub("[REDACTED_SSN]", masked)
        masked = PHONE_REGEX.sub("[REDACTED_PHONE]", masked)
        masked = API_KEY_REGEX.sub("[REDACTED_SECRET]", masked)
        return masked

    @staticmethod
    def apply_guardrails_to_messages(
        messages: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply configured guardrail rules to message list."""
        if not config or not config.get("pii_masking", True):
            return messages

        sanitized_messages = []
        for msg in messages:
            msg_copy = dict(msg)
            if isinstance(msg_copy.get("content"), str):
                msg_copy["content"] = AIGuardrails.mask_pii(msg_copy["content"])
            sanitized_messages.append(msg_copy)
        return sanitized_messages
