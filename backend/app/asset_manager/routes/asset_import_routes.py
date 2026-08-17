from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.services import asset_import_service as svc

router = APIRouter(prefix="/api/v1/asset-imports", tags=["Asset Imports"])


def _current_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def _job_response(job: Any) -> dict[str, Any]:
    return {
        "import_job_id": job.id,
        "name": job.name,
        "status": job.status,
        "stage": job.stage,
        "industry_tag": job.industry_tag,
        "total_records": job.total_records,
        "parsed_records": job.parsed_records,
        "valid_records": job.valid_records,
        "failed_records": job.failed_records,
        "imported_records": job.imported_records,
        "error_report_url": None,
        "merged_dataset_id": job.merged_dataset_id,
        "mapping_config_id": job.mapping_config_id,
        "parent_job_id": job.parent_job_id,
        "approved_by": job.approved_by,
        "approved_at": job.approved_at,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "mapping": job.mapping,
    }


@router.post("")
def create_import_job(body: dict[str, Any], request: Request, db: Session = Depends(get_asset_db)):
    body.setdefault("created_by", _current_user(request))
    return _job_response(svc.create_import_job(db, body))


@router.get("")
def list_import_jobs(request: Request, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_asset_db)):
    user_id = _current_user(request)
    return {"jobs": [_job_response(job) for job in svc.list_import_jobs(db, user_id, limit)]}


@router.get("/{import_job_id}")
def get_import_job(import_job_id: str, db: Session = Depends(get_asset_db)):
    return _job_response(svc._job(db, import_job_id))


@router.post("/{import_job_id}/files")
async def upload_file(import_job_id: str, file: UploadFile = File(...), db: Session = Depends(get_asset_db)):
    return await svc.upload_import_file(db, import_job_id, file)


@router.get("/{import_job_id}/files")
def list_files(import_job_id: str, db: Session = Depends(get_asset_db)):
    return svc.list_uploaded_files(db, import_job_id)


@router.get("/{import_job_id}/files/{file_id}/preview")
def file_preview(import_job_id: str, file_id: str, db: Session = Depends(get_asset_db)):
    svc._job(db, import_job_id)
    return svc.parse_uploaded_file(db, file_id)


@router.get("/{import_job_id}/asset-type-match")
def asset_type_match(import_job_id: str, column: str = Query(..., min_length=1), db: Session = Depends(get_asset_db)):
    return svc.match_asset_type_column(db, import_job_id, column)


@router.get("/{import_job_id}/hierarchy-mapping")
def hierarchy_mapping(
    import_job_id: str,
    asset_type_column: str = Query(..., min_length=1),
    parent_column: str | None = Query(None),
    db: Session = Depends(get_asset_db),
):
    return svc.asset_hierarchy_mapping_summary(db, import_job_id, asset_type_column, parent_column)


@router.post("/{import_job_id}/files/{file_id}/status")
def set_file_status(import_job_id: str, file_id: str, body: dict[str, Any], db: Session = Depends(get_asset_db)):
    svc.set_file_status(db, import_job_id, file_id, body["status"])
    return {"ok": True}


@router.post("/{import_job_id}/merge")
def merge_files(import_job_id: str, body: dict[str, Any], db: Session = Depends(get_asset_db)):
    return svc.merge_files(db, import_job_id, body.get("merge_strategy", "append"), body.get("dedup_key"))


@router.post("/{import_job_id}/suggest-mapping")
def suggest_mapping(import_job_id: str, db: Session = Depends(get_asset_db)):
    return svc.suggest_mapping(db, import_job_id)


@router.post("/{import_job_id}/mapping")
def apply_mapping(import_job_id: str, body: dict[str, Any], db: Session = Depends(get_asset_db)):
    return _job_response(svc.apply_mapping(db, import_job_id, body["field_mappings"]))


@router.post("/{import_job_id}/dry-run")
def dry_run(import_job_id: str, db: Session = Depends(get_asset_db)):
    return svc.dry_run(db, import_job_id)


@router.get("/{import_job_id}/errors")
def error_report(import_job_id: str, page: int = Query(1), page_size: int = Query(100), db: Session = Depends(get_asset_db)):
    job = svc._job(db, import_job_id)
    report = job.error_report or {"summary": {}, "errors": []}
    errors = report.get("errors", [])
    start = (page - 1) * page_size
    return {
        "summary": report.get("summary", {}),
        "errors": errors[start:start + page_size],
        "pagination": {"page": page, "page_size": page_size, "total_pages": max(1, (len(errors) + page_size - 1) // page_size), "total_errors": len(errors)},
    }


@router.get("/{import_job_id}/summary")
def summary(import_job_id: str, db: Session = Depends(get_asset_db)):
    return svc.pre_import_summary(db, import_job_id)


@router.post("/{import_job_id}/approve")
def approve(import_job_id: str, body: dict[str, Any], request: Request, db: Session = Depends(get_asset_db)):
    return svc.approve_and_import(db, import_job_id, _current_user(request), body.get("confirmation_statement", "approved"))


@router.get("/{import_job_id}/verification")
def verification(import_job_id: str, db: Session = Depends(get_asset_db)):
    return svc.verification(db, import_job_id)
