from __future__ import annotations

import io
import uuid
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.asset_manager.models.asset_manager import (
    AssetImportFile,
    AssetImportJob,
    AssetImportMappingConfig,
    AssetInstance,
    AssetStatus,
    AssetType,
    _utcnow,
)
from app.asset_manager.schemas.asset_manager import AssetInstanceCreate
from app.asset_manager.services import asset_manager_service as asset_service


REQUIRED_TARGETS = {"name", "asset_type"}


def _job(db: Session, job_id: str) -> AssetImportJob:
    obj = db.get(AssetImportJob, job_id)
    if not obj:
        raise HTTPException(404, "Import job not found")
    return obj


def _rows_for_job(db: Session, job_id: str) -> list[dict[str, Any]]:
    files = db.query(AssetImportFile).filter(
        AssetImportFile.import_job_id == job_id,
        AssetImportFile.status == "accepted",
    ).all()
    rows: list[dict[str, Any]] = []
    for f in files:
        rows.extend(f.rows or [])
    return rows


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def create_import_job(db: Session, body: dict[str, Any]) -> AssetImportJob:
    obj = AssetImportJob(
        id=str(uuid.uuid4()),
        name=body["name"],
        industry_tag=body.get("industry_tag") or "generic",
        source_format=body.get("source_format") or "csv",
        created_by=body.get("created_by"),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_import_jobs(db: Session, created_by: str | None = None, limit: int = 50) -> list[AssetImportJob]:
    q = db.query(AssetImportJob)
    if created_by:
        q = q.filter(AssetImportJob.created_by == created_by)
    return q.order_by(AssetImportJob.updated_at.desc()).limit(limit).all()


async def upload_import_file(db: Session, import_job_id: str, file: UploadFile, max_preview_rows: int = 10) -> dict[str, Any]:
    job = _job(db, import_job_id)
    raw = await file.read()
    name = file.filename or "upload.csv"
    fmt = name.rsplit(".", 1)[-1].lower()
    if fmt not in {"csv", "xlsx", "xls"}:
        raise HTTPException(422, "Unsupported file type. Upload CSV, XLS, or XLSX.")

    warnings: list[str] = []
    sheets: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    if fmt == "csv":
        df = pd.read_csv(io.BytesIO(raw)).fillna("")
        rows = [{str(k): _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
        sheets.append(_sheet_preview("CSV", df, max_preview_rows))
    else:
        book = pd.read_excel(io.BytesIO(raw), sheet_name=None).items()
        first = True
        for sheet_name, df in book:
            df = df.fillna("")
            sheets.append(_sheet_preview(sheet_name, df, max_preview_rows))
            if first:
                rows = [{str(k): _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
                first = False

    file_obj = AssetImportFile(
        id=str(uuid.uuid4()),
        import_job_id=job.id,
        file_name=name,
        file_size_kb=round(len(raw) / 1024, 2),
        format=fmt,
        status="previewed",
        active_sheet=sheets[0]["sheet_name"] if sheets else None,
        sheets=sheets,
        rows=rows,
        parse_warnings=warnings,
    )
    db.add(file_obj)
    job.status = "PREVIEWED"
    job.parsed_records = (job.parsed_records or 0) + len(rows)
    job.updated_at = _utcnow()
    db.commit()
    db.refresh(file_obj)
    return parse_uploaded_file(db, file_obj.id, max_preview_rows)


def _sheet_preview(sheet_name: str, df: pd.DataFrame, max_preview_rows: int) -> dict[str, Any]:
    return {
        "sheet_name": sheet_name,
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "detected_header": True,
        "column_names": [str(c) for c in df.columns],
        "preview_rows": [[_clean(v) for v in row] for row in df.head(max_preview_rows).values.tolist()],
        "empty_column_count": int(sum(1 for c in df.columns if df[c].replace("", pd.NA).isna().all())),
        "empty_row_count": int(df.replace("", pd.NA).isna().all(axis=1).sum()),
    }


def parse_uploaded_file(db: Session, file_id: str, max_preview_rows: int = 10) -> dict[str, Any]:
    obj = db.get(AssetImportFile, file_id)
    if not obj:
        raise HTTPException(404, "Import file not found")
    return {
        "file_id": obj.id,
        "file_name": obj.file_name,
        "file_size_kb": obj.file_size_kb,
        "format": obj.format,
        "sheet_count": len(obj.sheets or []),
        "sheets": obj.sheets or [],
        "parse_warnings": obj.parse_warnings or [],
    }


def list_uploaded_files(db: Session, import_job_id: str) -> dict[str, Any]:
    _job(db, import_job_id)
    files = db.query(AssetImportFile).filter(AssetImportFile.import_job_id == import_job_id).order_by(AssetImportFile.uploaded_at).all()
    return {"files": [{
        "file_id": f.id,
        "file_name": f.file_name,
        "file_size_kb": f.file_size_kb,
        "uploaded_at": f.uploaded_at,
        "status": f.status,
        "active_sheet": f.active_sheet,
        "column_names": ((f.sheets or [{}])[0].get("column_names") if f.sheets else []) or [],
    } for f in files]}


def match_asset_type_column(db: Session, import_job_id: str, column_name: str) -> dict[str, Any]:
    _job(db, import_job_id)
    files = db.query(AssetImportFile).filter(AssetImportFile.import_job_id == import_job_id).all()
    asset_types = db.query(AssetType).filter(AssetType.is_deleted.is_(False)).all()
    types_by_name = {t.name.strip().lower(): t for t in asset_types}
    types_by_id = {t.id: t for t in asset_types}
    child_ids = {child_id for t in asset_types for child_id in (t.allowed_children or [])}
    root_types = sorted([t for t in asset_types if t.is_root or t.id not in child_ids], key=lambda t: t.name.lower())
    ordered_ids: list[int] = []

    def visit(asset_type: AssetType, seen: set[int], depth: int) -> None:
        if asset_type.id in seen:
            return
        seen.add(asset_type.id)
        ordered_ids.append(asset_type.id)
        for child_id in asset_type.allowed_children or []:
            child = types_by_id.get(child_id)
            if child:
                visit(child, seen, depth + 1)

    seen_ids: set[int] = set()
    for root in root_types:
        visit(root, seen_ids, 0)
    for asset_type in sorted(asset_types, key=lambda t: t.name.lower()):
        visit(asset_type, seen_ids, 0)

    counts_by_type: dict[int, int] = defaultdict(int)
    unmatched_values: Counter[str] = Counter()
    total_rows = 0
    matched_rows = 0
    unmatched_rows = 0

    for file_obj in files:
        for row in file_obj.rows or []:
            total_rows += 1
            raw_value = row.get(column_name)
            value = "" if raw_value is None else str(raw_value).strip()
            asset_type = types_by_name.get(value.lower())
            if asset_type:
                matched_rows += 1
                counts_by_type[asset_type.id] += 1
            else:
                unmatched_rows += 1
                unmatched_values[value or "(blank)"] += 1

    matched_types = [
        {
            "asset_type_id": type_id,
            "name": types_by_id[type_id].name,
            "category": types_by_id[type_id].category.value if hasattr(types_by_id[type_id].category, "value") else types_by_id[type_id].category,
            "matched_rows": counts_by_type[type_id],
        }
        for type_id in ordered_ids
        if counts_by_type.get(type_id, 0) > 0
    ]
    return {
        "column_name": column_name,
        "total_rows": total_rows,
        "matched_rows": matched_rows,
        "unmatched_rows": unmatched_rows,
        "matched_types": matched_types,
        "unmatched_values": [{"value": value, "rows": count} for value, count in unmatched_values.most_common(10)],
    }


def _ordered_asset_types(asset_types: list[AssetType]) -> list[AssetType]:
    types_by_id = {t.id: t for t in asset_types}
    child_ids = {child_id for t in asset_types for child_id in (t.allowed_children or [])}
    roots = sorted([t for t in asset_types if t.is_root or t.id not in child_ids], key=lambda t: t.name.lower())
    ordered: list[AssetType] = []
    seen: set[int] = set()

    def visit(asset_type: AssetType) -> None:
        if asset_type.id in seen:
            return
        seen.add(asset_type.id)
        ordered.append(asset_type)
        for child_id in asset_type.allowed_children or []:
            child = types_by_id.get(child_id)
            if child:
                visit(child)

    for root in roots:
        visit(root)
    for asset_type in sorted(asset_types, key=lambda t: t.name.lower()):
        visit(asset_type)
    return ordered


def asset_hierarchy_mapping_summary(
    db: Session,
    import_job_id: str,
    asset_type_column: str,
    parent_column: str | None = None,
) -> dict[str, Any]:
    _job(db, import_job_id)
    files = db.query(AssetImportFile).filter(AssetImportFile.import_job_id == import_job_id).all()
    asset_types = db.query(AssetType).filter(AssetType.is_deleted.is_(False)).all()
    types_by_name = {t.name.strip().lower(): t for t in asset_types}
    ordered_types = _ordered_asset_types(asset_types)
    existing_assets = db.query(AssetInstance).filter(AssetInstance.status != AssetStatus.DECOMMISSIONED).all()
    assets_by_name = {asset.name.strip().lower(): asset for asset in existing_assets}
    assets_by_code = {asset.code.strip().lower(): asset for asset in existing_assets if asset.code}

    summary_by_type: dict[int, dict[str, Any]] = {
        asset_type.id: {
            "asset_type_id": asset_type.id,
            "name": asset_type.name,
            "category": asset_type.category.value if hasattr(asset_type.category, "value") else asset_type.category,
            "is_root": bool(asset_type.is_root),
            "rows": 0,
            "parent_matched_rows": 0,
            "parent_unmatched_rows": 0,
            "ready_to_add_rows": 0,
            "unmatched_parent_values": Counter(),
        }
        for asset_type in asset_types
    }

    total_matched_type_rows = 0
    for file_obj in files:
        for row in file_obj.rows or []:
            raw_type = row.get(asset_type_column)
            type_name = "" if raw_type is None else str(raw_type).strip()
            asset_type = types_by_name.get(type_name.lower())
            if not asset_type:
                continue
            total_matched_type_rows += 1
            item = summary_by_type[asset_type.id]
            item["rows"] += 1
            if asset_type.is_root:
                item["ready_to_add_rows"] += 1
                continue
            raw_parent = row.get(parent_column) if parent_column else None
            parent_value = "" if raw_parent is None else str(raw_parent).strip()
            parent_asset = assets_by_name.get(parent_value.lower()) or assets_by_code.get(parent_value.lower())
            if parent_asset:
                item["parent_matched_rows"] += 1
                item["ready_to_add_rows"] += 1
            else:
                item["parent_unmatched_rows"] += 1
                item["unmatched_parent_values"][parent_value or "(blank)"] += 1

    steps = []
    for asset_type in ordered_types:
        item = summary_by_type[asset_type.id]
        if item["rows"] == 0:
            continue
        unmatched_counter = item.pop("unmatched_parent_values")
        item["unmatched_parent_values"] = [
            {"value": value, "rows": count}
            for value, count in unmatched_counter.most_common(10)
        ]
        steps.append(item)

    return {
        "asset_type_column": asset_type_column,
        "parent_column": parent_column,
        "parent_column_required": any(not step["is_root"] for step in steps),
        "total_matched_type_rows": total_matched_type_rows,
        "steps": steps,
    }


def set_file_status(db: Session, import_job_id: str, file_id: str, status: str) -> None:
    _job(db, import_job_id)
    f = db.get(AssetImportFile, file_id)
    if not f or f.import_job_id != import_job_id:
        raise HTTPException(404, "Import file not found")
    f.status = status
    db.commit()


def merge_files(db: Session, import_job_id: str, merge_strategy: str = "append", dedup_key: str | None = None) -> dict[str, Any]:
    job = _job(db, import_job_id)
    files = db.query(AssetImportFile).filter(AssetImportFile.import_job_id == import_job_id, AssetImportFile.status == "accepted").all()
    rows: list[dict[str, Any]] = []
    per_file = {}
    seen = set()
    dupes = 0
    for f in files:
        per_file[f.id] = len(f.rows or [])
        for row in f.rows or []:
            if merge_strategy == "deduplicate" and dedup_key:
                key = row.get(dedup_key)
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)
            rows.append(row)
    cols = list(rows[0].keys()) if rows else []
    job.status = "FILES_ACCEPTED"
    job.stage = "MAPPING_CONFIGURATION"
    job.total_records = len(rows)
    job.merged_dataset_id = str(uuid.uuid4())
    job.updated_at = _utcnow()
    db.commit()
    return {
        "merged_dataset_id": job.merged_dataset_id,
        "total_rows": len(rows),
        "rows_per_file": per_file,
        "duplicate_rows_removed": dupes,
        "merged_preview": {"column_names": cols, "preview_rows": [[row.get(c, "") for c in cols] for row in rows[:10]], "total_columns": len(cols)},
    }


def suggest_mapping(db: Session, import_job_id: str) -> dict[str, Any]:
    job = _job(db, import_job_id)
    rows = _rows_for_job(db, import_job_id)
    cols = list(rows[0].keys()) if rows else []
    suggestions = []
    aliases = {
        "name": ["name", "asset_name", "description", "asset"],
        "code": ["code", "asset_code", "external_ref", "tag", "id"],
        "asset_type": ["asset_type", "type", "asset_type_slug", "category"],
        "parent_code": ["parent_code", "parent", "parent_ref", "parent_external_ref", "parent_id"],
        "status": ["status"],
        "description": ["description", "desc"],
    }
    used = set()
    for target, names in aliases.items():
        match = next((c for c in cols if c.lower().strip() in names), None)
        if match:
            suggestions.append({"source_column": match, "target_field": target, "transform": "string", "confidence": "high", "reasoning": "Matched by column name."})
            used.add(match)
    for c in cols:
        if c not in used:
            suggestions.append({"source_column": c, "target_field": f"metadata.{c}", "transform": "string", "confidence": "medium", "reasoning": "Imported as metadata."})
    mapped_targets = {s["target_field"] for s in suggestions}
    return {"suggested_mapping": suggestions, "unmapped_columns": [], "missing_required_fields": sorted(REQUIRED_TARGETS - mapped_targets)}


def apply_mapping(db: Session, import_job_id: str, mapping: list[dict[str, Any]]) -> AssetImportJob:
    job = _job(db, import_job_id)
    targets = {m.get("target_field") for m in mapping}
    missing = REQUIRED_TARGETS - targets
    if missing:
        raise HTTPException(422, f"Missing required mappings: {', '.join(sorted(missing))}")
    job.mapping = mapping
    job.status = "MAPPING_COMPLETE"
    job.stage = "DRY_RUN_VALIDATION"
    db.commit()
    db.refresh(job)
    return job


def dry_run(db: Session, import_job_id: str) -> dict[str, Any]:
    job = _job(db, import_job_id)
    rows = _mapped_rows(db, job)
    errors = _validate_rows(db, rows)
    blocking = sum(1 for e in errors if e["severity"] == "blocking")
    report = _report(errors, len(rows))
    job.error_report = report
    job.valid_records = len(rows) - blocking
    job.failed_records = blocking
    job.status = "AWAITING_APPROVAL" if blocking == 0 else "AWAITING_CORRECTION"
    job.stage = "AWAITING_APPROVAL" if blocking == 0 else "AWAITING_CORRECTION"
    db.commit()
    return {"dry_run_id": str(uuid.uuid4()), "status": "complete", "records_processed": len(rows), "total_records": len(rows), "progress_percent": 100, "error_report": report}


def _mapped_rows(db: Session, job: AssetImportJob) -> list[dict[str, Any]]:
    rows = _rows_for_job(db, job.id)
    mapping = job.mapping or []
    out = []
    for idx, row in enumerate(rows, start=2):
        item: dict[str, Any] = {"row_number": idx, "metadata": {}}
        for m in mapping:
            src = m.get("source_column")
            target = m.get("target_field")
            val = row.get(src)
            if target and target.startswith("metadata."):
                item["metadata"][target.split(".", 1)[1]] = val
            elif target:
                item[target] = val
        out.append(item)
    return out


def _validate_rows(db: Session, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    types = {t.slug: t for t in db.query(AssetType).filter(AssetType.is_deleted.is_(False)).all()}
    codes = {str(r.get("code")) for r in rows if r.get("code")}
    errors = []
    for r in rows:
        row_no = r["row_number"]
        if not r.get("name"):
            errors.append(_err(row_no, r, "MISSING_NAME", "Asset name is required.", "name"))
        if not r.get("asset_type") or str(r.get("asset_type")) not in types:
            errors.append(_err(row_no, r, "UNKNOWN_ASSET_TYPE", "Asset type must match an active asset type slug.", "asset_type"))
        parent_code = r.get("parent_code")
        if parent_code and parent_code not in codes and not db.query(AssetInstance).filter(AssetInstance.code == str(parent_code)).first():
            errors.append(_err(row_no, r, "UNKNOWN_PARENT", "Parent code was not found in this file or existing assets.", "parent_code"))
    duplicates = [code for code, count in Counter(str(r.get("code")) for r in rows if r.get("code")).items() if count > 1]
    for r in rows:
        if r.get("code") and str(r.get("code")) in duplicates:
            errors.append(_err(r["row_number"], r, "DUPLICATE_CODE", "Code appears more than once in the import file.", "code"))
    return errors


def _err(row: int, item: dict[str, Any], code: str, msg: str, field: str) -> dict[str, Any]:
    return {"row": row, "external_ref": item.get("code") or "", "asset_name": item.get("name") or "", "error_type": "validation", "error_code": code, "message": msg, "field": field, "suggestion": "Fix the value and rerun dry run.", "severity": "blocking"}


def _report(errors: list[dict[str, Any]], total: int) -> dict[str, Any]:
    counts = Counter(e["error_code"] for e in errors)
    return {
        "summary": {"total_errors": len(errors), "blocking_count": len(errors), "warning_count": 0, "info_count": 0, "error_types": [{"error_code": k, "count": v, "description": k.replace("_", " ").title()} for k, v in counts.items()], "clean_records": max(0, total - len({e["row"] for e in errors})), "affected_records": len({e["row"] for e in errors})},
        "errors": errors,
    }


def pre_import_summary(db: Session, import_job_id: str) -> dict[str, Any]:
    job = _job(db, import_job_id)
    rows = _mapped_rows(db, job)
    by_type = Counter(str(r.get("asset_type")) for r in rows)
    by_level = Counter(1 if r.get("parent_code") else 0 for r in rows)
    summary = {"total_assets": len(rows), "by_asset_type": [{"asset_type": k, "count": v} for k, v in by_type.items()], "by_hierarchy_level": [{"level": k, "label": "Root" if k == 0 else "Child", "count": v} for k, v in by_level.items()], "top_level_assets": [{"name": r.get("name"), "type": r.get("asset_type"), "child_count": 0} for r in rows if not r.get("parent_code")][:10], "events_to_create": 0, "tag_links_to_create": 0, "warnings": [], "narrative": f"This import will create or update {len(rows)} assets."}
    job.import_summary = summary
    db.commit()
    return summary


def approve_and_import(db: Session, import_job_id: str, approved_by: str | None, statement: str) -> dict[str, Any]:
    job = _job(db, import_job_id)
    if job.status != "AWAITING_APPROVAL":
        raise HTTPException(409, "Import is not awaiting approval")
    job.approved_by = approved_by
    job.approved_at = _utcnow()
    job.status = "IMPORTING"
    job.stage = "IMPORTING"
    db.flush()
    rows = sorted(_mapped_rows(db, job), key=lambda r: 1 if r.get("parent_code") else 0)
    type_by_slug = {t.slug: t for t in db.query(AssetType).filter(AssetType.is_deleted.is_(False)).all()}
    by_code: dict[str, AssetInstance] = {str(a.code): a for a in db.query(AssetInstance).filter(AssetInstance.code.isnot(None)).all()}
    imported = 0
    for r in rows:
        asset_type = type_by_slug[str(r["asset_type"])]
        parent = by_code.get(str(r.get("parent_code"))) if r.get("parent_code") else None
        existing = by_code.get(str(r.get("code"))) if r.get("code") else None
        body = AssetInstanceCreate(
            asset_type_id=asset_type.id,
            parent_id=parent.id if parent else None,
            name=str(r["name"]),
            code=str(r.get("code")) if r.get("code") else None,
            description=str(r.get("description")) if r.get("description") else None,
            status=AssetStatus(str(r.get("status") or "ACTIVE")) if str(r.get("status") or "ACTIVE") in AssetStatus.__members__ else AssetStatus.ACTIVE,
            metadata=r.get("metadata") or {},
        )
        if existing:
            existing.name = body.name
            existing.description = body.description
            existing.metadata = body.metadata
            obj = existing
        else:
            obj = asset_service.create_instance(db, body, approved_by)
        if obj.code:
            by_code[str(obj.code)] = obj
        imported += 1
    job.imported_records = imported
    job.status = "COMPLETED"
    job.stage = "COMPLETED"
    db.commit()
    return {"import_job_id": job.id, "status": "COMPLETED", "imported_records": imported, "confirmation_statement": statement}


def verification(db: Session, import_job_id: str) -> dict[str, Any]:
    job = _job(db, import_job_id)
    roots = db.query(AssetInstance).filter(AssetInstance.parent_id.is_(None), AssetInstance.status != AssetStatus.DECOMMISSIONED).limit(10).all()
    return {"checks": [{"check_name": "Import completed", "status": "passed", "expected": "COMPLETED", "actual": job.status, "detail": "Import job reached completed status."}], "overall_status": "passed" if job.status == "COMPLETED" else "warning", "imported_asset_count": job.imported_records, "hierarchy_root_assets": [{"id": str(r.id), "name": r.name, "type": r.asset_type.slug if r.asset_type else "", "child_count": len(r.children)} for r in roots], "anomalies": []}
