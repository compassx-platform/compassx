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


class UpdateType:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, type_id: str, data: TypeDefinitionUpdate) -> OntologyType:
        record = db.query(OntologyType).filter_by(id=type_id).first()
        if not record:
            raise KeyError(f"Entity type '{type_id}' not found.")

        if record.is_system and data.tier is not None and data.tier != record.tier:
            raise ValueError(f"System type '{type_id}' is protected and its hierarchy tier cannot be changed.")

        if data.label is not None:
            record.label = data.label.strip()
        if data.description is not None:
            record.description = data.description
        if data.shape is not None:
            record.shape = data.shape
        if data.base_radius is not None:
            record.base_radius = data.base_radius
        if data.tier is not None and not record.is_system:
            record.tier = data.tier
        if data.color is not None:
            record.color = data.color
        if data.icon is not None:
            record.icon = data.icon

        db.commit()
        db.refresh(record)
        return record

def update_type(db: Session, type_id: str, data: TypeDefinitionUpdate) -> OntologyType:
    from app.ontology.composition import ontology_log
    return UpdateType(ontology_log()).execute(db, type_id, data)
