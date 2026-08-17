"""Canonical field type mapping used by workflows and entities."""

from __future__ import annotations

CANONICAL_FIELD_TYPES = frozenset({
    "string",
    "text",
    "number",
    "boolean",
    "time",
    "datetime",
    "json",
})

_UI_TO_CANONICAL = {
    "text": "text",
    "textarea": "text",
    "string": "string",
    "input": "string",
    "number": "number",
    "int": "number",
    "integer": "number",
    "float": "number",
    "decimal": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "time": "time",
    "date": "datetime",
    "datetime": "datetime",
    "timestamp": "datetime",
    "json": "json",
}


def validate_canonical_type(value: str) -> str:
    normalized = (value or "string").strip().lower()
    if normalized not in CANONICAL_FIELD_TYPES:
        raise ValueError(f"Invalid field type '{value}'. Allowed: {sorted(CANONICAL_FIELD_TYPES)}")
    return normalized


def map_form_field(field: dict | object) -> str:
    """Map a form field definition to a canonical entity field type."""
    if isinstance(field, dict):
        field_type = field.get("field_type") or field.get("type") or field.get("ui_type")
    else:
        field_type = getattr(field, "field_type", None) or getattr(field, "type", None) or getattr(field, "ui_type", None)
    normalized = str(field_type or "string").strip().lower()
    return _UI_TO_CANONICAL.get(normalized, validate_canonical_type(normalized))


def map_form_type(value: str) -> str:
    """Map a form/entity type alias to a canonical field type."""
    normalized = str(value or "string").strip().lower()
    return _UI_TO_CANONICAL.get(normalized, validate_canonical_type(normalized))
