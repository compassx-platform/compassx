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


class DeleteEdge:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, edge_id: str, graph_id: str='default') -> KnowledgeGraphDataset:
        from app.ontology.runtime import ensure_default_seed, get_active_graph
        """Deletes an edge from the graph."""
        ensure_default_seed(db)
        db.query(OntologyEdge).filter_by(graph_id=graph_id, id=edge_id).delete()
        db.commit()
        return get_active_graph(db, graph_id=graph_id)

def delete_edge(db: Session, edge_id: str, graph_id: str='default') -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return DeleteEdge(ontology_log()).execute(db, edge_id, graph_id)
