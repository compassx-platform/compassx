"""Form schema routes."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.form import FormSchemaResponse, FormSchemaCreate, FormSchemaUpdate
from app.services.form_service import (
    get_form_schema,
    get_forms,
    create_form_schema,
    update_form_schema,
    delete_form_schema,
    generate_bulk_template_csv,
    generate_bulk_template_xlsx,
    parse_bulk_upload,
    commit_bulk_rows,
)

router = APIRouter(prefix="/api/v1/forms", tags=["Forms"])


# ── Schema CRUD ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[FormSchemaResponse])
def list_forms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all available forms."""
    return get_forms(db, skip=skip, limit=limit)


@router.post("", response_model=FormSchemaResponse)
def create_form(
    form_in: FormSchemaCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a new dynamically driven form schema."""
    existing = get_form_schema(db, form_in.form_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Form '{form_in.form_id}' already exists")
    return create_form_schema(db, form_in)


@router.put("/{form_id}", response_model=FormSchemaResponse)
def update_form(
    form_id: str,
    form_in: FormSchemaUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update an existing form schema."""
    try:
        updated = update_form_schema(db, form_id, form_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Form update failed: {exc}")
    if not updated:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")
    return updated


@router.get("/{form_id}")
def get_form(
    form_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    form = get_form_schema(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")
    return {
        "id": str(form.id),
        "form_id": form.form_id,
        "entity_name": form.entity_name,
        "schema": form.schema,
    }


# ── Bulk Upload ────────────────────────────────────────────────────────────────

@router.delete("/{form_id}", status_code=204)
def delete_form(
    form_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a form schema."""
    deleted = delete_form_schema(db, form_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")


@router.get("/{form_id}/bulk-template")
def download_bulk_template(
    form_id: str,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Download a CSV or Excel template pre-populated with the form's field headers."""
    form = get_form_schema(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")

    if format == "xlsx":
        content = generate_bulk_template_xlsx(form)
        filename = f"{form_id}_template.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = generate_bulk_template_csv(form)
        filename = f"{form_id}_template.csv"
        media_type = "text/csv"

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{form_id}/bulk-preview")
async def preview_bulk_upload(
    form_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Parse an uploaded CSV/Excel file and return the rows for preview.
    Returns: { fields, rows, errors }
    """
    form = get_form_schema(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")

    filename = file.filename or ""
    if not (filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .csv and .xlsx files are supported",
        )

    raw_bytes = await file.read()
    try:
        result = parse_bulk_upload(form, raw_bytes, filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return result


@router.post("/{form_id}/bulk-commit")
def commit_bulk_upload(
    form_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Commit previewed (and optionally edited) rows to the database.
    Body: { rows: [ { asset_id, ...field_values } ] }
    Returns: { created, errors }
    """
    form = get_form_schema(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found")

    rows: list[dict] = body.get("rows", [])
    if not rows:
        raise HTTPException(status_code=400, detail="No rows provided")

    result = commit_bulk_rows(
        db=db,
        form=form,
        rows=rows,
        user_email=user.get("email", "system"),
    )
    return result