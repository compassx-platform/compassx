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


class ListTypeRelations:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session) -> List[OntologyTypeRelation]:
        from app.ontology.runtime import ensure_default_seed
        ensure_default_seed(db)
        return db.query(OntologyTypeRelation).order_by(OntologyTypeRelation.source_type_id.asc(), OntologyTypeRelation.relation_type.asc()).all()

def list_type_relations(db: Session) -> List[OntologyTypeRelation]:
    from app.ontology.composition import ontology_log
    return ListTypeRelations(ontology_log()).execute(db)
