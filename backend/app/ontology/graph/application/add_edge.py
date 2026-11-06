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


class AddEdge:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, data: GraphEdgeCreate) -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed, get_active_graph
        """Adds a directional edge between two nodes, validating metamodel rules."""
        ensure_default_seed(db)
        graph_id = data.graph_id or "default"

        src = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.source).first()
        if not src:
            raise ValueError(f"Source node '{data.source}' does not exist.")

        tgt = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.target).first()
        if not tgt:
            raise ValueError(f"Target node '{data.target}' does not exist.")

        clean_rel = data.type.strip().lower().replace(" ", "_")
        allowed_rel = db.query(OntologyTypeRelation).filter_by(
            source_type_id=src.type_id,
            relation_type=clean_rel,
            target_type_id=tgt.type_id,
        ).first()
        if not allowed_rel:
            raise ValueError(
                f"Disallowed relationship: '{src.type_id} --[{clean_rel}]--> {tgt.type_id}' "
                f"is not permitted by the metamodel schema."
            )

        edge_id = data.id or f"{data.source}->{data.target}"
        existing = db.query(OntologyEdge).filter_by(graph_id=graph_id, id=edge_id).first()
        if existing:
            raise ValueError(f"Edge with ID '{edge_id}' already exists.")

        edge_record = OntologyEdge(
            id=edge_id,
            graph_id=graph_id,
            source_id=data.source,
            target_id=data.target,
            relation_type=clean_rel,
            description=data.description,
            properties=data.properties or {},
        )
        db.add(edge_record)
        db.commit()
        return get_active_graph(db, graph_id=graph_id)

def add_edge(db: Session, data: GraphEdgeCreate) -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return AddEdge(ontology_log()).execute(db, data)
