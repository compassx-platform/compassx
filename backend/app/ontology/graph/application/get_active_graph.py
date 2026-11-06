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


class GetActiveGraph:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, graph_id: str='default') -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed
        ensure_default_seed(db)

        graph_meta = db.query(OntologyGraph).filter_by(id=graph_id).first()
        if not graph_meta:
            # Fallback to default seed if missing
            ensure_default_seed(db)
            graph_meta = db.query(OntologyGraph).filter_by(id=graph_id).first()
            if not graph_meta:
                raise KeyError(f"Graph '{graph_id}' not found.")

        nodes_db = db.query(OntologyNode).filter_by(graph_id=graph_id).all()
        edges_db = db.query(OntologyEdge).filter_by(graph_id=graph_id).all()

        nodes: List[GraphNodeInstance] = [
            GraphNodeInstance(
                id=n.id,
                kind=n.type_id,
                uid=n.uid,
                title=n.title,
                description=n.description,
                parentId=n.parent_id,
                domainId=n.domain_id,
                path=n.path,
                tags=n.tags or [],
                status=n.status,
                properties=n.properties or {},
            )
            for n in nodes_db
        ]

        edges: List[GraphEdgeInstance] = [
            GraphEdgeInstance(
                id=e.id,
                source=e.source_id,
                target=e.target_id,
                type=e.relation_type,
                description=e.description,
                properties=e.properties or {},
            )
            for e in edges_db
        ]

        return KnowledgeGraphDataset(
            id=graph_meta.id,
            name=graph_meta.name,
            version=graph_meta.version,
            description=graph_meta.description,
            yaml_content=graph_meta.raw_yaml,
            nodes=nodes,
            edges=edges,
        )

def get_active_graph(db: Session, graph_id: str='default') -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return GetActiveGraph(ontology_log()).execute(db, graph_id)
