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


class ValidateGraph:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session, dataset: KnowledgeGraphDataset) -> GraphValidationResult:
        from app.ontology.runtime import ensure_default_seed
        """Enforces that all nodes, hierarchy links, and typed edges conform to the metamodel schema in DB."""
        ensure_default_seed(db)

        registered_types = {t.id: t for t in db.query(OntologyType).all()}
        registered_relations: Set[Tuple[str, str, str]] = {
            (r.source_type_id, r.relation_type.lower(), r.target_type_id)
            for r in db.query(OntologyTypeRelation).all()
        }

        errors: List[str] = []
        warnings: List[str] = []

        node_map: Dict[str, GraphNodeInstance] = {}

        # 1. Validate Node Types
        for node in dataset.nodes:
            node_map[node.id] = node
            if node.kind not in registered_types:
                errors.append(
                    f"Node '{node.id}' specifies unregistered entity type '{node.kind}'. "
                    f"Available types: {sorted(list(registered_types.keys()))}"
                )

        # 2. Validate Hierarchical Containment (parentId)
        for node in dataset.nodes:
            if node.parentId:
                parent = node_map.get(node.parentId)
                if not parent:
                    errors.append(f"Node '{node.id}' specifies non-existent parentId '{node.parentId}'.")
                else:
                    # Check if (parent.kind, 'contains', node.kind) is an allowed relation rule
                    rule_key = (parent.kind, "contains", node.kind)
                    if rule_key not in registered_relations:
                        errors.append(
                            f"Hierarchical containment violation: '{parent.kind}' cannot contain '{node.kind}' "
                            f"(for node '{node.id}' under parent '{parent.id}')."
                        )

        # 3. Validate Typed Edges
        for edge in dataset.edges:
            src = node_map.get(edge.source)
            tgt = node_map.get(edge.target)

            if not src:
                errors.append(f"Edge '{edge.id}' source node '{edge.source}' does not exist in graph nodes.")
            if not tgt:
                errors.append(f"Edge '{edge.id}' target node '{edge.target}' does not exist in graph nodes.")

            if src and tgt:
                clean_rel = edge.type.strip().lower().replace(" ", "_")
                rule_key = (src.kind, clean_rel, tgt.kind)
                if rule_key not in registered_relations:
                    errors.append(
                        f"Relationship violation on edge '{edge.id}': '{src.kind} --[{clean_rel}]--> {tgt.kind}' "
                        f"is not allowed by the ontology schema metamodel."
                    )

        return GraphValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            node_count=len(dataset.nodes),
            edge_count=len(dataset.edges),
        )

def validate_graph(db: Session, dataset: KnowledgeGraphDataset) -> GraphValidationResult:
    from app.ontology.composition import ontology_log
    return ValidateGraph(ontology_log()).execute(db, dataset)
