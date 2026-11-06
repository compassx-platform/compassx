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


class ParseYamlToDataset:
    def __init__(self, log):
        self.log = log

    def execute(self, yaml_str: str) -> KnowledgeGraphDataset:
        """Parses a YAML ontology file into a KnowledgeGraphDataset model."""
        try:
            raw = yaml.safe_load(yaml_str)
        except Exception as err:
            raise ValueError(f"Invalid YAML format: {err}")

        if not raw or not isinstance(raw, dict):
            raise ValueError("YAML must contain a top-level dictionary with 'nodes' and 'edges'.")

        raw_nodes = raw.get("nodes", []) or []
        raw_edges = raw.get("edges", []) or []

        nodes: List[GraphNodeInstance] = []
        for n in raw_nodes:
            if not isinstance(n, dict) or "id" not in n:
                continue
            nodes.append(
                GraphNodeInstance(
                    id=str(n.get("id")),
                    kind=str(n.get("kind", "element")),
                    uid=n.get("uid"),
                    title=str(n.get("title") or n.get("id")),
                    description=n.get("description"),
                    parentId=n.get("parentId"),
                    domainId=n.get("domainId"),
                    path=n.get("path"),
                    tags=n.get("tags") if isinstance(n.get("tags"), list) else [],
                    status=n.get("status", "active"),
                    properties={k: v for k, v in n.items() if k not in ["id", "kind", "uid", "title", "description", "parentId", "domainId", "path", "tags", "status"]},
                )
            )

        edges: List[GraphEdgeInstance] = []
        for e in raw_edges:
            if not isinstance(e, dict) or "id" not in e or "source" not in e or "target" not in e:
                continue
            edges.append(
                GraphEdgeInstance(
                    id=str(e.get("id")),
                    source=str(e.get("source")),
                    target=str(e.get("target")),
                    type=str(e.get("type", "contains")),
                    description=e.get("description"),
                    properties={k: v for k, v in e.items() if k not in ["id", "source", "target", "type", "description"]},
                )
            )

        return KnowledgeGraphDataset(
            name=str(raw.get("name", "CompassX & Ontology Atlas")),
            version=str(raw.get("version", "1.0.0")),
            description=raw.get("description"),
            nodes=nodes,
            edges=edges,
        )

def parse_yaml_to_dataset(yaml_str: str) -> KnowledgeGraphDataset:
    from app.ontology.composition import ontology_log
    return ParseYamlToDataset(ontology_log()).execute(yaml_str)
