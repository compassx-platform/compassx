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


class DeleteTypeRelation:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, rel_id: int) -> bool:
        record = db.query(OntologyTypeRelation).filter_by(id=rel_id).first()
        if not record:
            return False

        if record.is_system:
            raise ValueError("System relationship rule is protected and cannot be deleted.")

        db.delete(record)
        db.commit()
        return True

def delete_type_relation(db: Session, rel_id: int) -> bool:
    from app.ontology.composition import ontology_log
    return DeleteTypeRelation(ontology_log()).execute(db, rel_id)
