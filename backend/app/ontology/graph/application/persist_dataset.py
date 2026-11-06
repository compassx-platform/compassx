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


class PersistDataset:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, dataset: KnowledgeGraphDataset, raw_yaml: Optional[str]=None) -> None:
        """Internal helper to atomically insert/replace a knowledge graph in DB."""
        graph_id = dataset.id or "default"

        # 1. Upsert graph record
        graph_meta = db.query(OntologyGraph).filter_by(id=graph_id).first()
        if not graph_meta:
            graph_meta = OntologyGraph(
                id=graph_id,
                name=dataset.name,
                version=dataset.version,
                description=dataset.description,
                is_active=True,
                raw_yaml=raw_yaml,
            )
            db.add(graph_meta)
        else:
            graph_meta.name = dataset.name
            graph_meta.version = dataset.version
            graph_meta.description = dataset.description
            graph_meta.is_active = True
            if raw_yaml:
                graph_meta.raw_yaml = raw_yaml

        # 2. Clear old nodes and edges
        db.query(OntologyEdge).filter_by(graph_id=graph_id).delete()
        db.query(OntologyNode).filter_by(graph_id=graph_id).delete()

        # 3. Insert new nodes
        for node in dataset.nodes:
            node_record = OntologyNode(
                id=node.id,
                graph_id=graph_id,
                type_id=node.kind,
                uid=node.uid,
                title=node.title,
                description=node.description,
                parent_id=node.parentId,
                domain_id=node.domainId,
                path=node.path,
                tags=node.tags or [],
                status=node.status or "active",
                properties=node.properties or {},
            )
            db.add(node_record)

        # 4. Insert new edges
        for edge in dataset.edges:
            edge_record = OntologyEdge(
                id=edge.id,
                graph_id=graph_id,
                source_id=edge.source,
                target_id=edge.target,
                relation_type=edge.type,
                description=edge.description,
                properties=edge.properties or {},
            )
            db.add(edge_record)

        db.commit()

def persist_dataset(db: Session, dataset: KnowledgeGraphDataset, raw_yaml: Optional[str]=None) -> None:
    from app.ontology.composition import ontology_log
    return PersistDataset(ontology_log()).execute(db, dataset, raw_yaml)
