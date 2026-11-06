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


class CreateType:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, data: TypeDefinitionCreate) -> OntologyType:
        clean_id = slugify_type_id(data.id)
        existing = db.query(OntologyType).filter_by(id=clean_id).first()
        if existing:
            raise ValueError(f"Entity type with ID '{clean_id}' already exists.")

        record = OntologyType(
            id=clean_id,
            label=data.label.strip(),
            description=data.description,
            shape=data.shape,
            base_radius=data.base_radius,
            tier=data.tier,
            color=data.color,
            icon=data.icon,
            is_system=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

def create_type(db: Session, data: TypeDefinitionCreate) -> OntologyType:
    from app.ontology.composition import ontology_log
    return CreateType(ontology_log()).execute(db, data)
