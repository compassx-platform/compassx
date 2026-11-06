"""Shared ontology type helpers."""
from __future__ import annotations

import re


def slugify_type_id(raw_id: str) -> str:
    """Normalize a type ID to a clean URL/slug string."""
    clean = raw_id.strip().lower()
    clean = re.sub(r"[^a-z0-9_-]", "-", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean or "custom-type"

