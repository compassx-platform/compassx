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


class AddNode:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, data: GraphNodeCreate) -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed, get_active_graph
        """Adds a single node to the active graph, strictly enforcing metamodel rules."""
        ensure_default_seed(db)
        graph_id = data.graph_id or "default"

        # 1. Validate entity type
        type_def = db.query(OntologyType).filter_by(id=data.kind).first()
        if not type_def:
            raise ValueError(f"Unknown entity type '{data.kind}'. Please register this type in the schema first.")

        # 2. Check if node ID already exists
        existing = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.id).first()
        if existing:
            raise ValueError(f"Node with ID '{data.id}' already exists in graph '{graph_id}'.")

        # 3. Validate parent containment if parentId provided
        if data.parentId:
            parent = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.parentId).first()
            if not parent:
                raise ValueError(f"Parent node '{data.parentId}' does not exist.")

            # Check metamodel containment rule
            allowed_rel = db.query(OntologyTypeRelation).filter_by(
                source_type_id=parent.type_id,
                relation_type="contains",
                target_type_id=data.kind,
            ).first()
            if not allowed_rel:
                raise ValueError(
                    f"Hierarchical containment violation: '{parent.type_id}' cannot contain '{data.kind}' "
                    f"according to metamodel rules."
                )

        # 4. Insert Node
        node_record = OntologyNode(
            id=data.id,
            graph_id=graph_id,
            type_id=data.kind,
            title=data.title,
            description=data.description,
            parent_id=data.parentId,
            domain_id=data.domainId,
            path=data.path,
            tags=data.tags or [],
            status=data.status or "active",
            properties=data.properties or {},
        )
        db.add(node_record)

        # 5. Insert containment edge if parentId provided
        if data.parentId:
            edge_id = f"{data.parentId}->{data.id}"
            existing_edge = db.query(OntologyEdge).filter_by(graph_id=graph_id, id=edge_id).first()
            if not existing_edge:
                edge_record = OntologyEdge(
                    id=edge_id,
                    graph_id=graph_id,
                    source_id=data.parentId,
                    target_id=data.id,
                    relation_type="contains",
                    description=f"{parent.title} contains {data.title}",
                )
                db.add(edge_record)

        db.commit()
        return get_active_graph(db, graph_id=graph_id)

def add_node(db: Session, data: GraphNodeCreate) -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return AddNode(ontology_log()).execute(db, data)
