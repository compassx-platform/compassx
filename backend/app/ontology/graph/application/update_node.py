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


class UpdateNode:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, node_id: str, data: GraphNodeUpdate, graph_id: str='default') -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed, get_active_graph
        """Updates a node in the graph, enforcing metamodel validation if kind or parentId changes."""
        ensure_default_seed(db)
        node = db.query(OntologyNode).filter_by(graph_id=graph_id, id=node_id).first()
        if not node:
            raise KeyError(f"Node '{node_id}' not found in graph '{graph_id}'.")

        target_kind = data.kind or node.type_id
        target_parent_id = data.parentId if data.parentId is not None else node.parent_id

        # Validate kind
        if data.kind and data.kind != node.type_id:
            type_def = db.query(OntologyType).filter_by(id=data.kind).first()
            if not type_def:
                raise ValueError(f"Unknown entity type '{data.kind}'.")
            node.type_id = data.kind

        # Validate parent containment if parentId updated
        if data.parentId is not None:
            if target_parent_id:
                parent = db.query(OntologyNode).filter_by(graph_id=graph_id, id=target_parent_id).first()
                if not parent:
                    raise ValueError(f"Parent node '{target_parent_id}' does not exist.")
                allowed_rel = db.query(OntologyTypeRelation).filter_by(
                    source_type_id=parent.type_id,
                    relation_type="contains",
                    target_type_id=target_kind,
                ).first()
                if not allowed_rel:
                    raise ValueError(f"Metamodel violation: '{parent.type_id}' cannot contain '{target_kind}'.")

            # Remove old containment edge and add new one
            db.query(OntologyEdge).filter_by(
                graph_id=graph_id,
                target_id=node_id,
                relation_type="contains",
            ).delete()

            if target_parent_id:
                new_edge = OntologyEdge(
                    id=f"{target_parent_id}->{node_id}",
                    graph_id=graph_id,
                    source_id=target_parent_id,
                    target_id=node_id,
                    relation_type="contains",
                )
                db.add(new_edge)
            node.parent_id = target_parent_id

        if data.title is not None:
            node.title = data.title.strip()
        if data.description is not None:
            node.description = data.description
        if data.domainId is not None:
            node.domain_id = data.domainId
        if data.path is not None:
            node.path = data.path
        if data.tags is not None:
            node.tags = data.tags
        if data.status is not None:
            node.status = data.status
        if data.properties is not None:
            node.properties = data.properties

        db.commit()
        return get_active_graph(db, graph_id=graph_id)

def update_node(db: Session, node_id: str, data: GraphNodeUpdate, graph_id: str='default') -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return UpdateNode(ontology_log()).execute(db, node_id, data, graph_id)
