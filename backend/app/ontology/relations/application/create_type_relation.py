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


class CreateTypeRelation:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, data: TypeRelationCreate) -> OntologyTypeRelation:
        src = db.query(OntologyType).filter_by(id=data.source_type_id).first()
        if not src:
            raise ValueError(f"Source entity type '{data.source_type_id}' does not exist.")
        tgt = db.query(OntologyType).filter_by(id=data.target_type_id).first()
        if not tgt:
            raise ValueError(f"Target entity type '{data.target_type_id}' does not exist.")

        clean_rel = data.relation_type.strip().lower().replace(" ", "_")

        existing = (
            db.query(OntologyTypeRelation)
            .filter_by(
                source_type_id=data.source_type_id,
                relation_type=clean_rel,
                target_type_id=data.target_type_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Relationship rule '{data.source_type_id} --[{clean_rel}]--> {data.target_type_id}' already exists."
            )

        record = OntologyTypeRelation(
            source_type_id=data.source_type_id,
            relation_type=clean_rel,
            target_type_id=data.target_type_id,
            is_hierarchical=data.is_hierarchical or (clean_rel == "contains"),
            is_system=data.is_system if hasattr(data, "is_system") else False,
            description=data.description,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

def create_type_relation(db: Session, data: TypeRelationCreate) -> OntologyTypeRelation:
    from app.ontology.composition import ontology_log
    return CreateTypeRelation(ontology_log()).execute(db, data)
