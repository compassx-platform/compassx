"""Business logic for Asset Manager module."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.asset_manager.models.asset_manager import (
    AssetDocument,
    AssetEvent,
    AssetInstance,
    AssetRelationship,
    AssetStatus,
    AssetTag,
    AssetType,
    AssetTypeTag,
    AssetVersion,
    _utcnow,
)
from app.asset_manager.schemas.asset_manager import (
    AssetDocumentCreate,
    AssetEventCreate,
    AssetEventUpdate,
    AssetInstanceCreate,
    AssetInstanceUpdate,
    AssetParentUpdate,
    AssetRelationshipCreate,
    AssetStatusUpdate,
    AssetTagCreate,
    AssetTypeCreate,
    AssetTypeUpdate,
    AssetTypeTagCreate,
    AssetTypeTagUpdate,
    MetadataSchema,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_asset_type_or_404(db: Session, type_id: int) -> AssetType:
    obj = db.query(AssetType).filter(AssetType.id == type_id).first()
    if not obj:
        raise HTTPException(404, "Asset type not found")
    return obj


def _get_instance_or_404(db: Session, instance_id: int) -> AssetInstance:
    obj = db.query(AssetInstance).filter(AssetInstance.id == instance_id).first()
    if not obj:
        raise HTTPException(404, "Asset instance not found")
    return obj


def _build_path(db: Session, parent_id: int | None, code_or_name: str) -> tuple[str, int]:
    """Return (path, depth) for a new or reparented asset."""
    slug = code_or_name.lower().replace(" ", "-").replace("/", "-")
    if parent_id is None:
        return f"/{slug}", 0
    parent = _get_instance_or_404(db, parent_id)
    return f"{parent.path}/{slug}", parent.depth + 1


def _snapshot_asset(asset: AssetInstance) -> dict[str, Any]:
    return {
        "id": asset.id,
        "asset_type_id": asset.asset_type_id,
        "parent_id": asset.parent_id,
        "name": asset.name,
        "code": asset.code,
        "description": asset.description,
        "status": asset.status.value if asset.status else None,
        "latitude": asset.latitude,
        "longitude": asset.longitude,
        "altitude": asset.altitude,
        "address": asset.address,
        "commissioned_at": asset.commissioned_at.isoformat() if asset.commissioned_at else None,
        "decommissioned_at": asset.decommissioned_at.isoformat() if asset.decommissioned_at else None,
        "metadata": asset.extra_metadata,
        "metadata_schema_version": asset.metadata_schema_version,
        "path": asset.path,
        "depth": asset.depth,
    }


def _create_version(db: Session, asset: AssetInstance, summary: str | None, user: str | None) -> None:
    max_version = db.query(func.max(AssetVersion.version)).filter(
        AssetVersion.asset_id == asset.id
    ).scalar() or 0
    v = AssetVersion(
        asset_id=asset.id,
        version=max_version + 1,
        snapshot=_snapshot_asset(asset),
        change_summary=summary,
        changed_by=user,
    )
    db.add(v)


def _validate_parent_type(db: Session, asset_type: AssetType, parent_id: int | None) -> None:
    if parent_id is None:
        if asset_type.is_root is False and asset_type.allowed_parents:
            raise HTTPException(422, "INVALID_ROOT_TYPE: This asset type must be created under an allowed parent type")
        return
    parent = _get_instance_or_404(db, parent_id)
    parent_type = _get_asset_type_or_404(db, parent.asset_type_id)
    if parent_type.is_leaf:
        raise HTTPException(422, "INVALID_PARENT_TYPE: Leaf asset types cannot have child assets")
    if asset_type.allowed_parents and parent.asset_type_id not in asset_type.allowed_parents:
        raise HTTPException(422, "INVALID_PARENT_TYPE: Parent asset type not allowed for this type")
    if parent_type.allowed_children and asset_type.id not in parent_type.allowed_children:
        raise HTTPException(422, "INVALID_CHILD_TYPE: Child asset type not allowed under this parent type")


def _check_circular(db: Session, asset_id: int, new_parent_id: int | None) -> None:
    if new_parent_id is None:
        return
    node = db.query(AssetInstance).filter(AssetInstance.id == new_parent_id).first()
    visited = set()
    while node:
        if node.id == asset_id:
            raise HTTPException(422, "CIRCULAR_HIERARCHY: Reparent would create a circular reference")
        if node.id in visited:
            break
        visited.add(node.id)
        node = db.query(AssetInstance).filter(AssetInstance.id == node.parent_id).first() if node.parent_id else None


# ── Asset Type Service ────────────────────────────────────────────────────────

def list_asset_types(db: Session, industry_tag: str | None, category: str | None, include_deleted: bool = False) -> list[AssetType]:
    q = db.query(AssetType)
    if not include_deleted:
        q = q.filter(AssetType.is_deleted.is_(False))
    if category:
        q = q.filter(AssetType.category == category)
    if industry_tag:
        q = q.filter(AssetType.industry_tags.any(industry_tag))
    return q.order_by(AssetType.name).all()


def create_asset_type(db: Session, body: AssetTypeCreate) -> AssetType:
    existing = db.query(AssetType).filter(AssetType.slug == body.slug).first()
    if existing:
        raise HTTPException(409, "Asset type slug already exists")
    obj = AssetType(
        name=body.name,
        slug=body.slug,
        category=body.category,
        description=body.description,
        industry_tags=body.industry_tags,
        icon=body.icon,
        allowed_parents=body.allowed_parents,
        allowed_children=body.allowed_children,
        metadata_schema=body.metadata_schema.model_dump(),
        is_root=body.is_root,
        is_leaf=body.is_leaf,
        schema_version=1,
    )
    db.add(obj)
    db.flush()

    if body.tag_definitions:
        for t in body.tag_definitions:
            tag_def = AssetTypeTag(
                asset_type_id=obj.id,
                tag_key=t.tag_key,
                name=t.name,
                description=t.description,
                parameter=t.parameter,
                unit=t.unit,
                is_required=t.is_required,
            )
            db.add(tag_def)

    db.commit()
    db.refresh(obj)
    return obj


def get_asset_type(db: Session, type_id: int) -> AssetType:
    return _get_asset_type_or_404(db, type_id)


def update_asset_type(db: Session, type_id: int, body: AssetTypeUpdate) -> AssetType:
    obj = _get_asset_type_or_404(db, type_id)
    
    body_data = body.model_dump(exclude_none=True)
    tag_defs_data = body_data.pop("tag_definitions", None)
    
    for field, val in body_data.items():
        setattr(obj, field, val)
        
    if tag_defs_data is not None:
        current_tags = {t.id: t for t in obj.tag_definitions}
        incoming_tags = []
        for t_data in tag_defs_data:
            t_id = t_data.get("id")
            if t_id and t_id in current_tags:
                tag_def = current_tags[t_id]
                for k, v in t_data.items():
                    if k != "id":
                        setattr(tag_def, k, v)
                incoming_tags.append(t_id)
            else:
                tag_def = AssetTypeTag(
                    asset_type_id=obj.id,
                    tag_key=t_data["tag_key"],
                    name=t_data["name"],
                    description=t_data.get("description"),
                    parameter=t_data.get("parameter"),
                    unit=t_data.get("unit"),
                    is_required=t_data.get("is_required", False),
                )
                db.add(tag_def)
                db.flush()
                incoming_tags.append(tag_def.id)
                
        for t_id, tag_def in current_tags.items():
            if t_id not in incoming_tags:
                db.delete(tag_def)
                
    db.commit()
    db.refresh(obj)
    return obj


def delete_asset_type(db: Session, type_id: int) -> None:
    obj = _get_asset_type_or_404(db, type_id)
    count = db.query(AssetInstance).filter(
        AssetInstance.asset_type_id == type_id,
        AssetInstance.status != AssetStatus.DECOMMISSIONED,
    ).count()
    if count > 0:
        raise HTTPException(409, "ASSET_TYPE_HAS_INSTANCES: Cannot delete type with existing instances")
    obj.is_deleted = True
    obj.deleted_at = _utcnow()
    db.commit()


def purge_asset_type(db: Session, type_id: int) -> None:
    obj = _get_asset_type_or_404(db, type_id)
    count = db.query(AssetInstance).filter(AssetInstance.asset_type_id == type_id).count()
    if count > 0:
        raise HTTPException(409, "ASSET_TYPE_HAS_INSTANCES: Cannot permanently delete type with existing instances")
    db.delete(obj)
    db.commit()


def purge_deleted_asset_types(db: Session) -> int:
    items = db.query(AssetType).filter(AssetType.is_deleted.is_(True)).all()
    deleted = 0
    for obj in items:
        count = db.query(AssetInstance).filter(AssetInstance.asset_type_id == obj.id).count()
        if count > 0:
            continue
        db.delete(obj)
        deleted += 1
    db.commit()
    return deleted


def update_asset_type_schema(db: Session, type_id: int, schema: MetadataSchema) -> AssetType:
    obj = _get_asset_type_or_404(db, type_id)
    obj.metadata_schema = schema.model_dump()
    obj.schema_version = obj.schema_version + 1
    db.commit()
    db.refresh(obj)
    return obj


# ── Asset Type Tag Services ───────────────────────────────────────────────────

def create_asset_type_tag(db: Session, type_id: int, body: AssetTypeTagCreate) -> AssetTypeTag:
    _get_asset_type_or_404(db, type_id)
    
    existing = db.query(AssetTypeTag).filter(
        AssetTypeTag.asset_type_id == type_id,
        AssetTypeTag.tag_key == body.tag_key
    ).first()
    if existing:
        raise HTTPException(409, f"Tag definition with key '{body.tag_key}' already exists for this asset type")
        
    obj = AssetTypeTag(
        asset_type_id=type_id,
        tag_key=body.tag_key,
        name=body.name,
        description=body.description,
        parameter=body.parameter,
        unit=body.unit,
        is_required=body.is_required,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_asset_type_tags(db: Session, type_id: int) -> list[AssetTypeTag]:
    _get_asset_type_or_404(db, type_id)
    return db.query(AssetTypeTag).filter(AssetTypeTag.asset_type_id == type_id).order_by(AssetTypeTag.tag_key).all()


def update_asset_type_tag(db: Session, type_id: int, tag_def_id: int, body: AssetTypeTagUpdate) -> AssetTypeTag:
    _get_asset_type_or_404(db, type_id)
    obj = db.query(AssetTypeTag).filter(
        AssetTypeTag.asset_type_id == type_id,
        AssetTypeTag.id == tag_def_id
    ).first()
    if not obj:
        raise HTTPException(404, "Asset type tag definition not found")
        
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, field, val)
        
    db.commit()
    db.refresh(obj)
    return obj


def delete_asset_type_tag(db: Session, type_id: int, tag_def_id: int) -> None:
    _get_asset_type_or_404(db, type_id)
    obj = db.query(AssetTypeTag).filter(
        AssetTypeTag.asset_type_id == type_id,
        AssetTypeTag.id == tag_def_id
    ).first()
    if not obj:
        raise HTTPException(404, "Asset type tag definition not found")
        
    db.delete(obj)
    db.commit()


# ── Asset Instance Service ────────────────────────────────────────────────────

def list_instances(
    db: Session,
    q: str | None,
    type_id: int | None,
    status: list[str] | None,
    parent_id: int | None,
    path_prefix: str | None,
    industry: str | None,
    cursor: int | None,
    limit: int,
    sort: str,
) -> dict[str, Any]:
    query = db.query(AssetInstance)

    if type_id:
        query = query.filter(AssetInstance.asset_type_id == type_id)
    if status:
        query = query.filter(AssetInstance.status.in_(status))
    if parent_id is not None:
        query = query.filter(AssetInstance.parent_id == parent_id)
    if path_prefix:
        query = query.filter(AssetInstance.path.like(f"{path_prefix}%"))
    if q:
        query = query.filter(
            or_(
                AssetInstance.name.ilike(f"%{q}%"),
                AssetInstance.code.ilike(f"%{q}%"),
                AssetInstance.description.ilike(f"%{q}%"),
            )
        )
    if industry:
        query = query.join(AssetType, AssetInstance.asset_type_id == AssetType.id).filter(
            AssetType.industry_tags.any(industry)
        )

    desc = sort.startswith("-")
    sort_field = sort.lstrip("-")
    col = getattr(AssetInstance, sort_field, AssetInstance.updated_at)
    query = query.order_by(col.desc() if desc else col.asc(), AssetInstance.id.asc())

    if cursor:
        query = query.filter(AssetInstance.id > cursor)

    total = query.count()
    items = query.limit(limit).all()

    next_cursor = items[-1].id if len(items) == limit else None
    return {
        "data": items,
        "pagination": {
            "cursor": next_cursor,
            "limit": limit,
            "total": total,
            "has_more": next_cursor is not None,
        },
    }


def create_instance(db: Session, body: AssetInstanceCreate, user: str | None) -> AssetInstance:
    asset_type = _get_asset_type_or_404(db, body.asset_type_id)
    _validate_parent_type(db, asset_type, body.parent_id)

    if asset_type.is_leaf and body.parent_id is None:
        pass  # leaf can still be root in edge cases

    path, depth = _build_path(db, body.parent_id, body.code or body.name)

    obj = AssetInstance(
        asset_type_id=body.asset_type_id,
        parent_id=body.parent_id,
        name=body.name,
        code=body.code,
        description=body.description,
        status=body.status,
        latitude=body.latitude,
        longitude=body.longitude,
        altitude=body.altitude,
        address=body.address,
        commissioned_at=body.commissioned_at,
        extra_metadata=body.metadata,
        metadata_schema_version=asset_type.schema_version,
        path=path,
        depth=depth,
        created_by=user,
        updated_by=user,
    )
    db.add(obj)
    db.flush()
    _create_version(db, obj, "Initial creation", user)
    db.commit()
    db.refresh(obj)
    return obj


def get_instance(db: Session, instance_id: int) -> AssetInstance:
    return _get_instance_or_404(db, instance_id)


def update_instance(db: Session, instance_id: int, body: AssetInstanceUpdate, user: str | None) -> AssetInstance:
    obj = _get_instance_or_404(db, instance_id)
    _INSTANCE_FIELD_MAP = {"metadata": "extra_metadata"}
    for field, val in body.model_dump(exclude={"change_summary"}, exclude_none=True).items():
        setattr(obj, _INSTANCE_FIELD_MAP.get(field, field), val)
    obj.updated_by = user
    db.flush()
    _create_version(db, obj, body.change_summary, user)
    db.commit()
    db.refresh(obj)
    return obj


def update_instance_status(db: Session, instance_id: int, body: AssetStatusUpdate, user: str | None) -> AssetInstance:
    obj = _get_instance_or_404(db, instance_id)
    obj.status = body.status
    obj.updated_by = user
    db.flush()
    _create_version(db, obj, body.change_summary or f"Status changed to {body.status}", user)
    db.commit()
    db.refresh(obj)
    return obj


def reparent_instance(db: Session, instance_id: int, body: AssetParentUpdate, user: str | None) -> AssetInstance:
    obj = _get_instance_or_404(db, instance_id)
    _check_circular(db, instance_id, body.parent_id)
    asset_type = _get_asset_type_or_404(db, obj.asset_type_id)
    _validate_parent_type(db, asset_type, body.parent_id)

    old_path = obj.path
    new_path, new_depth = _build_path(db, body.parent_id, obj.code or obj.name)
    depth_delta = new_depth - obj.depth

    # Cascade update all descendants
    descendants = db.query(AssetInstance).filter(
        AssetInstance.path.like(f"{old_path}/%")
    ).all()
    for desc in descendants:
        desc.path = desc.path.replace(old_path, new_path, 1)
        desc.depth = desc.depth + depth_delta

    obj.parent_id = body.parent_id
    obj.path = new_path
    obj.depth = new_depth
    obj.updated_by = user
    db.flush()
    _create_version(db, obj, body.change_summary or "Reparented", user)
    db.commit()
    db.refresh(obj)
    return obj


def soft_delete_instance(db: Session, instance_id: int, user: str | None) -> None:
    obj = _get_instance_or_404(db, instance_id)
    children_count = db.query(AssetInstance).filter(
        AssetInstance.parent_id == instance_id,
        AssetInstance.status != AssetStatus.DECOMMISSIONED,
    ).count()
    if children_count > 0:
        raise HTTPException(409, "ASSET_HAS_CHILDREN: Cannot delete asset with child assets")
    obj.status = AssetStatus.DECOMMISSIONED
    obj.updated_by = user
    db.flush()
    _create_version(db, obj, "Soft deleted (decommissioned)", user)
    db.commit()


def purge_deleted_instances(db: Session) -> int:
    items = db.query(AssetInstance).filter(
        AssetInstance.status == AssetStatus.DECOMMISSIONED,
    ).order_by(AssetInstance.depth.desc()).all()
    deleted = 0
    for obj in items:
        children_count = db.query(AssetInstance).filter(AssetInstance.parent_id == obj.id).count()
        if children_count > 0:
            continue
        db.delete(obj)
        deleted += 1
    db.commit()
    return deleted


def get_children(db: Session, instance_id: int, include_deleted: bool = False) -> list[AssetInstance]:
    _get_instance_or_404(db, instance_id)
    query = db.query(AssetInstance).filter(AssetInstance.parent_id == instance_id)
    if not include_deleted:
        query = query.filter(AssetInstance.status != AssetStatus.DECOMMISSIONED)
    return query.all()


def get_subtree(db: Session, instance_id: int) -> list[AssetInstance]:
    obj = _get_instance_or_404(db, instance_id)
    return db.query(AssetInstance).filter(
        AssetInstance.path.like(f"{obj.path}%")
    ).order_by(AssetInstance.path).all()


def get_ancestors(db: Session, instance_id: int) -> list[AssetInstance]:
    obj = _get_instance_or_404(db, instance_id)
    parts = [p for p in obj.path.split("/") if p]
    ancestors: list[AssetInstance] = []
    current_path = ""
    for part in parts[:-1]:
        current_path = f"{current_path}/{part}"
        ancestor = db.query(AssetInstance).filter(AssetInstance.path == current_path).first()
        if ancestor:
            ancestors.append(ancestor)
    return ancestors


def get_roots(db: Session, include_deleted: bool = False) -> list[AssetInstance]:
    query = db.query(AssetInstance).filter(AssetInstance.parent_id.is_(None))
    if not include_deleted:
        query = query.filter(AssetInstance.status != AssetStatus.DECOMMISSIONED)
    return query.all()


def get_instance_by_path(db: Session, path: str) -> AssetInstance:
    # Normalize: ensure leading slash, strip trailing slash
    normalized = "/" + path.strip("/")
    obj = db.query(AssetInstance).filter(AssetInstance.path == normalized).first()
    if not obj:
        raise HTTPException(404, f"No asset found at path: {normalized}")
    return obj


# ── Version History ───────────────────────────────────────────────────────────

def get_versions(db: Session, instance_id: int) -> list[AssetVersion]:
    _get_instance_or_404(db, instance_id)
    return (
        db.query(AssetVersion)
        .filter(AssetVersion.asset_id == instance_id)
        .order_by(AssetVersion.version.desc())
        .all()
    )


def get_version(db: Session, instance_id: int, version: int) -> AssetVersion:
    _get_instance_or_404(db, instance_id)
    v = (
        db.query(AssetVersion)
        .filter(AssetVersion.asset_id == instance_id, AssetVersion.version == version)
        .first()
    )
    if not v:
        raise HTTPException(404, "Version not found")
    return v


# ── Asset Relationship Service ────────────────────────────────────────────────

def list_relationships(
    db: Session, from_asset_id: int | None, to_asset_id: int | None, rel_type: str | None
) -> list[AssetRelationship]:
    q = db.query(AssetRelationship)
    if from_asset_id:
        q = q.filter(AssetRelationship.from_asset_id == from_asset_id)
    if to_asset_id:
        q = q.filter(AssetRelationship.to_asset_id == to_asset_id)
    if rel_type:
        q = q.filter(AssetRelationship.type == rel_type)
    return q.all()


def create_relationship(db: Session, body: AssetRelationshipCreate, user: str | None) -> AssetRelationship:
    _get_instance_or_404(db, body.from_asset_id)
    _get_instance_or_404(db, body.to_asset_id)
    obj = AssetRelationship(
        from_asset_id=body.from_asset_id,
        to_asset_id=body.to_asset_id,
        type=body.type,
        direction=body.direction,
        extra_metadata=body.metadata,
        description=body.description,
        created_by=user,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_relationship(db: Session, rel_id: int) -> None:
    obj = db.query(AssetRelationship).filter(AssetRelationship.id == rel_id).first()
    if not obj:
        raise HTTPException(404, "Relationship not found")
    db.delete(obj)
    db.commit()


# ── Asset Event Service ───────────────────────────────────────────────────────

def list_events(
    db: Session,
    asset_id: int | None,
    event_type: str | None,
    severity: str | None,
    started_after: str | None,
    started_before: str | None,
) -> list[AssetEvent]:
    q = db.query(AssetEvent)
    if asset_id:
        q = q.filter(AssetEvent.asset_id == asset_id)
    if event_type:
        q = q.filter(AssetEvent.event_type == event_type)
    if severity:
        q = q.filter(AssetEvent.severity == severity)
    if started_after:
        q = q.filter(AssetEvent.started_at >= started_after)
    if started_before:
        q = q.filter(AssetEvent.started_at <= started_before)
    return q.order_by(AssetEvent.started_at.desc()).all()


def create_event(db: Session, body: AssetEventCreate, user: str | None) -> AssetEvent:
    _get_instance_or_404(db, body.asset_id)
    obj = AssetEvent(
        asset_id=body.asset_id,
        linked_assets=body.linked_assets,
        event_type=body.event_type,
        title=body.title,
        description=body.description,
        severity=body.severity,
        started_at=body.started_at,
        ended_at=body.ended_at,
        extra_metadata=body.metadata,
        source=body.source,
        external_ref=body.external_ref,
        created_by=user,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_event(db: Session, event_id: int) -> AssetEvent:
    obj = db.query(AssetEvent).filter(AssetEvent.id == event_id).first()
    if not obj:
        raise HTTPException(404, "Event not found")
    return obj


def update_event(db: Session, event_id: int, body: AssetEventUpdate) -> AssetEvent:
    obj = get_event(db, event_id)
    _EVENT_FIELD_MAP = {"metadata": "extra_metadata"}
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(obj, _EVENT_FIELD_MAP.get(field, field), val)
    db.commit()
    db.refresh(obj)
    return obj


def delete_event(db: Session, event_id: int) -> None:
    obj = get_event(db, event_id)
    db.delete(obj)
    db.commit()


# ── Asset Tag Service ──────────────────────────────────────────────────────────

def create_asset_tag(db: Session, body: AssetTagCreate, user: str | None) -> AssetTag:
    asset = _get_instance_or_404(db, body.asset_id)
    
    asset_type_tag_id = body.asset_type_tag_id
    param = body.parameter
    unit = body.unit
    
    if asset_type_tag_id is not None:
        tag_def = db.query(AssetTypeTag).filter(AssetTypeTag.id == asset_type_tag_id).first()
        if not tag_def:
            raise HTTPException(404, "Asset type tag definition not found")
        if tag_def.asset_type_id != asset.asset_type_id:
            raise HTTPException(422, "Tag definition does not belong to the asset's type")
            
        if not param:
            param = tag_def.parameter
        if not unit:
            unit = tag_def.unit

    existing = db.query(AssetTag).filter(
        AssetTag.asset_id == body.asset_id,
        AssetTag.tag_id == body.tag_id,
    ).first()
    if existing:
        raise HTTPException(409, "Tag link already exists for this asset and tag_id")
        
    obj = AssetTag(
        asset_id=body.asset_id,
        asset_type_tag_id=asset_type_tag_id,
        tag_id=body.tag_id,
        tag_name=body.tag_name,
        parameter=param,
        unit=unit,
        source=body.source,
        is_primary=body.is_primary,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_asset_tags(db: Session, asset_id: int | None = None) -> list[AssetTag]:
    q = db.query(AssetTag)
    if asset_id is not None:
        q = q.filter(AssetTag.asset_id == asset_id)
    return q.order_by(AssetTag.asset_id, AssetTag.tag_id).all()


def delete_asset_tag(db: Session, tag_id: int) -> None:
    obj = db.query(AssetTag).filter(AssetTag.id == tag_id).first()
    if not obj:
        raise HTTPException(404, "Tag link not found")
    db.delete(obj)
    db.commit()


# ── Document Service ──────────────────────────────────────────────────────────

def create_document(db: Session, body: AssetDocumentCreate, user: str | None) -> AssetDocument:
    _get_instance_or_404(db, body.asset_id)
    obj = AssetDocument(
        asset_id=body.asset_id,
        title=body.title,
        type=body.type,
        url=body.url,
        mime_type=body.mime_type,
        file_size=body.file_size,
        version=body.version,
        uploaded_by=user,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def delete_document(db: Session, doc_id: int) -> None:
    obj = db.query(AssetDocument).filter(AssetDocument.id == doc_id).first()
    if not obj:
        raise HTTPException(404, "Document not found")
    db.delete(obj)
    db.commit()
