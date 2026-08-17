#!/usr/bin/env python3
"""One-time migration: copy all fields from the breakdown_event form schema
into the breakdown_event entity_fields table.

Usage (from the backend/ directory):
    python scripts/migrate_form_fields_to_entity.py

What it does:
  1. Finds the form whose entity_name = 'breakdown_event'
  2. Reads form.schema["fields"]
  3. For each form field not already present in entity_fields,
     inserts a new row with field_source = 'form'
  4. Skips fields that already exist (idempotent)
  5. Prints a summary — does NOT modify any existing entity field

Field-type mapping (form → canonical):
  text / textarea / string  → string
  text / textarea / string  → string
  number / integer / float  → number
  date / datetime           → datetime
  boolean / checkbox        → boolean
  select / radio / multiselect → string  (stores selected value as text)
  json / object             → json
  anything else             → string
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Make sure we can import app config ────────────────────────────────────────
# Add the backend directory to sys.path so we can reuse app.config / .env
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env before importing config
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass  # dotenv not installed; rely on environment variables

from app.config import settings  # noqa: E402 — after sys.path fix

import sqlalchemy as sa  # noqa: E402
from sqlalchemy import text  # noqa: E402

# ── Type mapping ──────────────────────────────────────────────────────────────

_FORM_TO_CANONICAL: dict[str, str] = {
    "text":         "string",
    "textarea":     "text",
    "string":       "string",
    "number":       "number",
    "integer":      "number",
    "float":        "number",
    "numeric":      "number",
    "date":         "datetime",
    "datetime":     "datetime",
    "boolean":      "boolean",
    "checkbox":     "boolean",
    "select":       "string",
    "radio":        "string",
    "multiselect":  "string",
    "json":         "json",
    "object":       "json",
}


def canonical_type(form_type: str) -> str:
    return _FORM_TO_CANONICAL.get((form_type or "text").lower().strip(), "string")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    engine = sa.create_engine(settings.database_url, pool_pre_ping=True)

    with engine.connect() as conn:
        # ── 1. Find the breakdown_event entity ────────────────────────────────
        entity_row = conn.execute(
            text("SELECT id FROM entity_definitions WHERE name = 'breakdown_event'")
        ).fetchone()

        if not entity_row:
            print("ERROR: Entity 'breakdown_event' not found in entity_definitions.")
            print("       Create the entity first, then re-run this script.")
            sys.exit(1)

        entity_id = entity_row[0]
        print(f"Found entity 'breakdown_event'  id={entity_id}")

        # ── 2. Find the form ──────────────────────────────────────────────────
        form_row = conn.execute(
            text(
                "SELECT form_id, schema FROM forms "
                "WHERE entity_name = 'breakdown_event' "
                "ORDER BY created_at ASC LIMIT 1"
            )
        ).fetchone()

        if not form_row:
            print("ERROR: No form found with entity_name = 'breakdown_event'.")
            sys.exit(1)

        form_id, schema = form_row
        print(f"Found form  form_id={form_id}")

        form_fields: list[dict] = (schema or {}).get("fields", [])
        if not form_fields:
            print("Form schema has no fields. Nothing to migrate.")
            sys.exit(0)

        print(f"Form has {len(form_fields)} field(s).")

        # ── 3. Load existing entity field names ───────────────────────────────
        existing_rows = conn.execute(
            text("SELECT field_name FROM entity_fields WHERE entity_id = :eid"),
            {"eid": entity_id},
        ).fetchall()
        existing_names: set[str] = {r[0] for r in existing_rows}
        print(f"Entity already has {len(existing_names)} field(s): {sorted(existing_names)}")

        # ── 4. Insert missing fields ──────────────────────────────────────────
        added: list[str] = []
        skipped: list[str] = []

        for f in form_fields:
            # Form field id is used as the canonical field_name
            raw_id: str = (f.get("id") or f.get("label") or "").strip()
            if not raw_id:
                print(f"  SKIP (no id/label): {f}")
                continue

            # Normalise to snake_case-ish: replace spaces/hyphens with _
            field_name = raw_id.replace(" ", "_").replace("-", "_").lower()

            if field_name in existing_names:
                skipped.append(field_name)
                continue

            ftype = canonical_type(f.get("type", "text"))
            is_required = bool(f.get("required", False))

            conn.execute(
                text(
                    """
                    INSERT INTO entity_fields
                        (entity_id, field_name, field_type,
                         is_required, is_indexed, field_source,
                         is_system, system_generated)
                    VALUES
                        (:entity_id, :field_name, :field_type,
                         :is_required, false, 'form',
                         false, false)
                    """
                ),
                {
                    "entity_id":    entity_id,
                    "field_name":   field_name,
                    "field_type":   ftype,
                    "is_required":  is_required,
                },
            )
            existing_names.add(field_name)
            added.append(field_name)

        conn.commit()

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print(f"  Added   : {len(added)} field(s)")
    if added:
        for n in added:
            print(f"    + {n}")
    print(f"  Skipped : {len(skipped)} field(s) (already existed)")
    if skipped:
        for n in skipped:
            print(f"    = {n}")
    print("=" * 55)
    print("Migration complete.")


if __name__ == "__main__":
    main()