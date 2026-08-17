"""Asset Hierarchy routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_asset_db
from app.asset_manager.models.asset_manager import AssetInstance, AssetStatus
from app.asset_manager.schemas.asset_manager import AssetInstanceListResponse, HierarchyNode
from app.asset_manager import services as svc

router = APIRouter(prefix="/api/v1/asset-hierarchy", tags=["Asset Hierarchy"])


def _to_node(
    instance: AssetInstance,
    db: Session,
    include_children: bool = False,
    max_depth: int = 3,
    include_deleted: bool = False,
) -> HierarchyNode:
    children_query = db.query(AssetInstance).filter(AssetInstance.parent_id == instance.id)
    if not include_deleted:
        children_query = children_query.filter(AssetInstance.status != AssetStatus.DECOMMISSIONED)
    children_count = children_query.count()
    node = HierarchyNode(
        id=instance.id,
        name=instance.name,
        code=instance.code,
        status=instance.status,
        asset_type_id=instance.asset_type_id,
        asset_type_name=instance.asset_type.name if instance.asset_type else None,
        asset_type_slug=instance.asset_type.slug if instance.asset_type else None,
        icon=instance.asset_type.icon if instance.asset_type else None,
        path=instance.path,
        depth=instance.depth,
        has_children=children_count > 0,
    )
    if include_children and instance.depth < max_depth:
        children = children_query.all()
        node.children = [
            _to_node(c, db, include_children=True, max_depth=max_depth, include_deleted=include_deleted)
            for c in children
        ]
    return node


@router.get("/roots", response_model=list[HierarchyNode])
def get_roots(
    include_deleted: bool = Query(False),
    db: Session = Depends(get_asset_db),
):
    roots = svc.get_roots(db, include_deleted=include_deleted)
    return [_to_node(r, db, include_children=False, include_deleted=include_deleted) for r in roots]


@router.get("", response_model=list[HierarchyNode])
def get_hierarchy(
    include_deleted: bool = Query(False),
    db: Session = Depends(get_asset_db),
):
    roots = svc.get_roots(db, include_deleted=include_deleted)
    return [_to_node(r, db, include_children=False, include_deleted=include_deleted) for r in roots]


@router.get("/{instance_id}/tree", response_model=HierarchyNode)
def get_tree(
    instance_id: int,
    max_depth: int = Query(3, ge=1, le=10),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_asset_db),
):
    obj = svc.get_instance(db, instance_id)
    return _to_node(obj, db, include_children=True, max_depth=obj.depth + max_depth, include_deleted=include_deleted)
