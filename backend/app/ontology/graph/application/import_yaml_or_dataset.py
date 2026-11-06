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


class ImportYamlOrDataset:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, req: KnowledgeGraphImportRequest) -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed, persist_dataset, parse_yaml_to_dataset, validate_graph, get_active_graph
        """Validates against metamodel in DB and persists the new Knowledge Graph to database."""
        ensure_default_seed(db)

        raw_yaml_str: Optional[str] = None
        if req.yaml_content:
            raw_yaml_str = req.yaml_content
            dataset = parse_yaml_to_dataset(req.yaml_content)
        elif req.dataset:
            dataset = req.dataset
        else:
            raise ValueError("Must provide either 'yaml_content' or 'dataset'.")

        if req.graph_id:
            dataset.id = req.graph_id
        if req.name:
            dataset.name = req.name
        if req.version:
            dataset.version = req.version
        if req.description:
            dataset.description = req.description

        # Enforce validation against DB Metamodel
        val_result = validate_graph(db, dataset)
        if not val_result.valid:
            error_details = "\n• " + "\n• ".join(val_result.errors)
            raise ValueError(f"Schema metamodel validation failed with {len(val_result.errors)} errors:{error_details}")

        # Persist to database
        persist_dataset(db, dataset, raw_yaml=raw_yaml_str)
        return get_active_graph(db, graph_id=dataset.id or "default")

def import_yaml_or_dataset(db: Session, req: KnowledgeGraphImportRequest) -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return ImportYamlOrDataset(ontology_log()).execute(db, req)
