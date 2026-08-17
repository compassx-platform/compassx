from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.asset_manager import services as asset_service
from app.asset_manager.services import asset_import_service
from app.asset_manager.schemas.asset_manager import (
    AssetInstanceCreate,
    AssetInstanceListResponse,
    AssetInstanceResponse,
    AssetInstanceUpdate,
    AssetParentUpdate,
    AssetStatusUpdate,
    AssetTypeCreate,
    AssetTypeListResponse,
    AssetTypeResponse,
    AssetTypeUpdate,
    AssetVersionResponse,
    AssetTagResponse,
    AssetTypeTagResponse,
)

ASSET_MANAGER_OPERATIONS = [
    "list_asset_types",
    "get_asset_type",
    "create_asset_type",
    "update_asset_type",
    "list_assets",
    "get_asset",
    "create_asset",
    "update_asset",
    "update_asset_status",
    "reparent_asset",
    "get_asset_children",
    "get_asset_versions",
    "list_import_jobs",
    "create_import_job",
    "get_import_job",
    "list_uploaded_files",
    "set_import_file_status",
    "merge_import_files",
    "suggest_import_mapping",
    "apply_import_mapping",
    "run_import_dry_run",
    "get_import_error_report",
    "generate_pre_import_summary",
    "approve_and_run_import",
    "run_import_verification",
    "search_asset_tags",
    "search_asset_type_tags",
]


def execute_asset_manager_operation(
    operation: str,
    payload: dict[str, Any],
    db: Session,
    user: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handler = _OPERATION_HANDLERS.get(operation)
    if handler is None:
        raise ValueError(f"Unsupported asset_manager operation: {operation}")
    return handler(payload or {}, db, user, context or {})


def _model_dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [_model_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _model_dump(item) for key, item in value.items()}
    return value


def _asset_type_response(asset_type: Any, list_item: bool = False) -> dict[str, Any]:
    schema = AssetTypeListResponse if list_item else AssetTypeResponse
    return schema.model_validate(asset_type).model_dump(mode="json")


def _asset_response(asset: Any, list_item: bool = False) -> dict[str, Any]:
    schema = AssetInstanceListResponse if list_item else AssetInstanceResponse
    response = schema.model_validate(asset)
    if getattr(asset, "asset_type", None):
        response.asset_type_name = asset.asset_type.name
        response.asset_type_slug = asset.asset_type.slug
    return response.model_dump(mode="json")


def _version_response(version: Any) -> dict[str, Any]:
    return AssetVersionResponse.model_validate(version).model_dump(mode="json")


def _asset_tag_response(tag: Any) -> dict[str, Any]:
    return AssetTagResponse.model_validate(tag).model_dump(mode="json")


def _asset_type_tag_response(tag_def: Any) -> dict[str, Any]:
    return AssetTypeTagResponse.model_validate(tag_def).model_dump(mode="json")


def _require_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if value is None:
        raise ValueError(f"payload.{field} is required")
    return int(value)


def _require_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if value is None or str(value).strip() == "":
        raise ValueError(f"payload.{field} is required")
    return str(value)


def _success(
    operation: str,
    resource_type: str,
    data: Any,
    message: str,
    resource_id: int | str | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "operation": operation,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "data": data,
        "message": message,
        "error": None,
    }


def _import_job_response(job: Any) -> dict[str, Any]:
    return _model_dump(
        {
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
    )


def _list_asset_types(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    items = asset_service.list_asset_types(
        db,
        industry_tag=payload.get("industry_tag"),
        category=payload.get("category"),
    )
    data = [_asset_type_response(item, list_item=True) for item in items]
    return _success("list_asset_types", "asset_type", data, f"Found {len(data)} asset types.")


def _get_asset_type(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    type_id = _require_int(payload, "type_id")
    item = asset_service.get_asset_type(db, type_id)
    return _success("get_asset_type", "asset_type", _asset_type_response(item), "Asset type loaded.", type_id)


def _create_asset_type(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    item = asset_service.create_asset_type(db, AssetTypeCreate.model_validate(payload))
    return _success("create_asset_type", "asset_type", _asset_type_response(item), "Asset type created.", item.id)


def _update_asset_type(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    type_id = _require_int(payload, "type_id")
    body = {key: value for key, value in payload.items() if key != "type_id"}
    item = asset_service.update_asset_type(db, type_id, AssetTypeUpdate.model_validate(body))
    return _success("update_asset_type", "asset_type", _asset_type_response(item), "Asset type updated.", type_id)


def _list_assets(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    result = asset_service.list_instances(
        db,
        q=payload.get("q"),
        type_id=payload.get("type_id"),
        status=payload.get("status"),
        parent_id=payload.get("parent_id"),
        path_prefix=payload.get("path_prefix"),
        industry=payload.get("industry"),
        cursor=payload.get("cursor"),
        limit=int(payload.get("limit", 50)),
        sort=payload.get("sort", "-updated_at"),
    )
    data = [_asset_response(item, list_item=True) for item in result["data"]]
    return _success(
        "list_assets",
        "asset",
        {"data": data, "pagination": _model_dump(result["pagination"])},
        f"Found {len(data)} assets.",
    )


def _get_asset(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    item = asset_service.get_instance(db, asset_id)
    return _success("get_asset", "asset", _asset_response(item), "Asset loaded.", asset_id)


def _create_asset(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    item = asset_service.create_instance(db, AssetInstanceCreate.model_validate(payload), user)
    return _success("create_asset", "asset", _asset_response(item), "Asset created.", item.id)


def _update_asset(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    body = {key: value for key, value in payload.items() if key != "asset_id"}
    item = asset_service.update_instance(db, asset_id, AssetInstanceUpdate.model_validate(body), user)
    return _success("update_asset", "asset", _asset_response(item), "Asset updated.", asset_id)


def _update_asset_status(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    body = {key: value for key, value in payload.items() if key != "asset_id"}
    item = asset_service.update_instance_status(db, asset_id, AssetStatusUpdate.model_validate(body), user)
    return _success("update_asset_status", "asset", _asset_response(item), "Asset status updated.", asset_id)


def _reparent_asset(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    body = {key: value for key, value in payload.items() if key != "asset_id"}
    item = asset_service.reparent_instance(db, asset_id, AssetParentUpdate.model_validate(body), user)
    return _success("reparent_asset", "asset", _asset_response(item), "Asset parent updated.", asset_id)


def _get_asset_children(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    items = asset_service.get_children(db, asset_id, include_deleted=bool(payload.get("include_deleted", False)))
    data = [_asset_response(item, list_item=True) for item in items]
    return _success("get_asset_children", "asset", data, f"Found {len(data)} child assets.", asset_id)


def _get_asset_versions(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = _require_int(payload, "asset_id")
    items = asset_service.get_versions(db, asset_id)
    data = [_version_response(item) for item in items]
    return _success("get_asset_versions", "asset_version", data, f"Found {len(data)} asset versions.", asset_id)


def _list_import_jobs(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    jobs = asset_import_service.list_import_jobs(
        db,
        created_by=user if payload.get("created_by_current_user", True) else None,
        limit=int(payload.get("limit", 20)),
    )
    data = [_import_job_response(job) for job in jobs]
    return _success("list_import_jobs", "asset_import_job", data, f"Found {len(data)} import jobs.")


def _create_import_job(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    body = {
        "name": _require_str(payload, "name"),
        "industry_tag": payload.get("industry_tag") or "generic",
        "source_format": payload.get("source_format") or "csv",
        "created_by": payload.get("created_by") or user,
    }
    job = asset_import_service.create_import_job(db, body)
    return _success("create_import_job", "asset_import_job", _import_job_response(job), "Import job created.", job.id)


def _get_import_job(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    job = asset_import_service._job(db, import_job_id)
    return _success("get_import_job", "asset_import_job", _import_job_response(job), "Import job loaded.", import_job_id)


def _list_uploaded_files(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.list_uploaded_files(db, import_job_id)
    count = len(data.get("files", []))
    return _success("list_uploaded_files", "asset_import_file", _model_dump(data), f"Found {count} uploaded files.", import_job_id)


def _set_import_file_status(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    file_id = _require_str(payload, "file_id")
    status = _require_str(payload, "status")
    if status not in {"accepted", "rejected"}:
        raise ValueError("payload.status must be accepted or rejected")
    asset_import_service.set_file_status(db, import_job_id, file_id, status)
    return _success(
        "set_import_file_status",
        "asset_import_file",
        {"import_job_id": import_job_id, "file_id": file_id, "status": status},
        f"File marked {status}.",
        file_id,
    )


def _merge_import_files(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.merge_files(
        db,
        import_job_id,
        merge_strategy=payload.get("merge_strategy") or "append",
        dedup_key=payload.get("dedup_key"),
    )
    return _success("merge_import_files", "asset_import_dataset", _model_dump(data), "Accepted files merged.", data.get("merged_dataset_id"))


def _suggest_import_mapping(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.suggest_mapping(db, import_job_id)
    return _success("suggest_import_mapping", "asset_import_mapping", _model_dump(data), "Import mapping suggested.", import_job_id)


def _apply_import_mapping(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    if payload.get("confirmed_by_user") is not True:
        raise ValueError("payload.confirmed_by_user must be true before applying an import mapping")
    field_mappings = payload.get("field_mappings")
    if not isinstance(field_mappings, list):
        raise ValueError("payload.field_mappings must be a list")
    job = asset_import_service.apply_mapping(db, import_job_id, field_mappings)
    return _success("apply_import_mapping", "asset_import_job", _import_job_response(job), "Import mapping applied.", import_job_id)


def _run_import_dry_run(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.dry_run(db, import_job_id)
    return _success("run_import_dry_run", "asset_import_dry_run", _model_dump(data), "Dry run completed.", data.get("dry_run_id"))


def _get_import_error_report(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    page = int(payload.get("page", 1))
    page_size = int(payload.get("page_size", 100))
    severity_filter = payload.get("severity_filter", "all")
    job = asset_import_service._job(db, import_job_id)
    report = job.error_report or {"summary": {}, "errors": []}
    errors = report.get("errors", [])
    if severity_filter and severity_filter != "all":
        errors = [error for error in errors if error.get("severity") == severity_filter]
    error_type_filter = payload.get("error_type_filter")
    if error_type_filter:
        errors = [error for error in errors if error.get("error_type") == error_type_filter or error.get("error_code") == error_type_filter]
    start = (page - 1) * page_size
    data = {
        "summary": report.get("summary", {}),
        "errors": errors[start:start + page_size],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (len(errors) + page_size - 1) // page_size),
            "total_errors": len(errors),
        },
    }
    return _success("get_import_error_report", "asset_import_error_report", _model_dump(data), f"Found {len(errors)} import errors.", import_job_id)


def _generate_pre_import_summary(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.pre_import_summary(db, import_job_id)
    return _success("generate_pre_import_summary", "asset_import_summary", _model_dump(data), "Pre-import summary generated.", import_job_id)


def _approve_and_run_import(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    if payload.get("confirmed_by_user") is not True:
        raise ValueError("payload.confirmed_by_user must be true before approving an import")
    confirmation_statement = _require_str(payload, "confirmation_statement")
    data = asset_import_service.approve_and_import(db, import_job_id, payload.get("approved_by") or user, confirmation_statement)
    return _success("approve_and_run_import", "asset_import_job", _model_dump(data), "Import approved and completed.", import_job_id)


def _run_import_verification(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    import_job_id = _require_str(payload, "import_job_id")
    data = asset_import_service.verification(db, import_job_id)
    return _success("run_import_verification", "asset_import_verification", _model_dump(data), "Import verification completed.", import_job_id)


def _search_asset_tags(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    asset_id = payload.get("asset_id")
    if asset_id is not None:
        asset_id = int(asset_id)
    items = asset_service.list_asset_tags(db, asset_id=asset_id)
    q = payload.get("q")
    if q:
        q_lower = q.lower()
        items = [
            item for item in items
            if q_lower in item.tag_id.lower()
            or q_lower in item.tag_name.lower()
            or (item.parameter and q_lower in item.parameter.lower())
        ]
    data = [_asset_tag_response(item) for item in items]
    return _success("search_asset_tags", "asset_tag", data, f"Found {len(data)} asset tags.")


def _search_asset_type_tags(payload: dict[str, Any], db: Session, user: str | None, context: dict[str, Any]) -> dict[str, Any]:
    type_id = _require_int(payload, "type_id")
    items = asset_service.list_asset_type_tags(db, type_id=type_id)
    q = payload.get("q")
    if q:
        q_lower = q.lower()
        items = [
            item for item in items
            if q_lower in item.tag_key.lower()
            or q_lower in item.name.lower()
            or (item.description and q_lower in item.description.lower())
        ]
    data = [_asset_type_tag_response(item) for item in items]
    return _success("search_asset_type_tags", "asset_type_tag", data, f"Found {len(data)} asset type tags.")


_OPERATION_HANDLERS: dict[str, Callable[[dict[str, Any], Session, str | None, dict[str, Any]], dict[str, Any]]] = {
    "list_asset_types": _list_asset_types,
    "get_asset_type": _get_asset_type,
    "create_asset_type": _create_asset_type,
    "update_asset_type": _update_asset_type,
    "list_assets": _list_assets,
    "get_asset": _get_asset,
    "create_asset": _create_asset,
    "update_asset": _update_asset,
    "update_asset_status": _update_asset_status,
    "reparent_asset": _reparent_asset,
    "get_asset_children": _get_asset_children,
    "get_asset_versions": _get_asset_versions,
    "list_import_jobs": _list_import_jobs,
    "create_import_job": _create_import_job,
    "get_import_job": _get_import_job,
    "list_uploaded_files": _list_uploaded_files,
    "set_import_file_status": _set_import_file_status,
    "merge_import_files": _merge_import_files,
    "suggest_import_mapping": _suggest_import_mapping,
    "apply_import_mapping": _apply_import_mapping,
    "run_import_dry_run": _run_import_dry_run,
    "get_import_error_report": _get_import_error_report,
    "generate_pre_import_summary": _generate_pre_import_summary,
    "approve_and_run_import": _approve_and_run_import,
    "run_import_verification": _run_import_verification,
    "search_asset_tags": _search_asset_tags,
    "search_asset_type_tags": _search_asset_type_tags,
}
