"""Service layer for Ontology Metamodel and Knowledge Graph persistence & validation."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import yaml
from sqlalchemy.orm import Session

from app.ontology.models.ontology import (
    OntologyType,
    OntologyTypeRelation,
    OntologyGraph,
    OntologyNode,
    OntologyEdge,
)
from app.ontology.schemas.ontology import (
    TypeDefinitionCreate,
    TypeDefinitionUpdate,
    TypeRelationCreate,
    TypeRelationUpdate,
    GraphNodeInstance,
    GraphEdgeInstance,
    KnowledgeGraphDataset,
    GraphValidationResult,
    KnowledgeGraphImportRequest,
    GraphNodeCreate,
    GraphNodeUpdate,
    GraphEdgeCreate,
)
from app.ontology.services.default_seed import (
    DEFAULT_SEED_TYPES,
    DEFAULT_SEED_RELATIONS,
    DEFAULT_SEED_GRAPH_META,
    DEFAULT_SEED_NODES,
    DEFAULT_SEED_EDGES,
)

from app.ontology.types.repository import slugify_type_id


class UpdateTypeRelation:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, rel_id: int, data: TypeRelationUpdate) -> OntologyTypeRelation:
        record = db.query(OntologyTypeRelation).filter_by(id=rel_id).first()
        if not record:
            raise KeyError(f"Relationship rule with ID '{rel_id}' not found.")

        # Determine target values
        new_source = data.source_type_id if data.source_type_id is not None else record.source_type_id
        new_target = data.target_type_id if data.target_type_id is not None else record.target_type_id
        new_rel_type = (data.relation_type.strip().lower().replace(" ", "_")) if data.relation_type is not None else record.relation_type

        if record.is_system:
            raise ValueError("System relationship rule is protected and cannot be edited.")

        if data.source_type_id is not None:
            src = db.query(OntologyType).filter_by(id=new_source).first()
            if not src:
                raise ValueError(f"Source entity type '{new_source}' does not exist.")

        if data.target_type_id is not None:
            tgt = db.query(OntologyType).filter_by(id=new_target).first()
            if not tgt:
                raise ValueError(f"Target entity type '{new_target}' does not exist.")

        # Check uniqueness constraint if signature is changing
        if (
            new_source != record.source_type_id
            or new_rel_type != record.relation_type
            or new_target != record.target_type_id
        ):
            dup = (
                db.query(OntologyTypeRelation)
                .filter(
                    OntologyTypeRelation.id != rel_id,
                    OntologyTypeRelation.source_type_id == new_source,
                    OntologyTypeRelation.relation_type == new_rel_type,
                    OntologyTypeRelation.target_type_id == new_target,
                )
                .first()
            )
            if dup:
                raise ValueError(
                    f"Relationship rule '{new_source} --[{new_rel_type}]--> {new_target}' already exists."
                )

        record.source_type_id = new_source
        record.relation_type = new_rel_type
        record.target_type_id = new_target
        if data.is_hierarchical is not None:
            record.is_hierarchical = data.is_hierarchical or (new_rel_type == "contains")
        if data.description is not None:
            record.description = data.description

        db.commit()
        db.refresh(record)
        return record

def update_type_relation(db: Session, rel_id: int, data: TypeRelationUpdate) -> OntologyTypeRelation:
    from app.ontology.composition import ontology_log
    return UpdateTypeRelation(ontology_log()).execute(db, rel_id, data)
