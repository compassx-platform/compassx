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


class EnsureDefaultSeed:
    def __init__(self, log):
        self.log = log

    def execute(self, db: Session) -> None:
        from app.ontology.runtime import persist_dataset
        """Seed default types, metamodel relations, and default graph if not present or migrate legacy seed."""
        try:
            # Check if database has legacy seed (project / capability) or is missing org
            has_org = db.query(OntologyType).filter_by(id="org").first() is not None
            has_legacy = db.query(OntologyType).filter(OntologyType.id.in_(["project", "capability"])).first() is not None
            existing_type_count = db.query(OntologyType).count()

            if existing_type_count == 0 or (has_legacy and not has_org):
                self.log.info("Migrating / Seeding default ontology schema (org -> domain -> subdomain -> element)...")
                # Clean legacy data
                db.query(OntologyEdge).delete()
                db.query(OntologyNode).delete()
                db.query(OntologyGraph).delete()
                db.query(OntologyTypeRelation).delete()
                db.query(OntologyType).delete()
                db.commit()

                # 1. Seed default types
                for t in DEFAULT_SEED_TYPES:
                    db.add(OntologyType(**t))
                db.commit()

                # 2. Seed default type relations
                for r in DEFAULT_SEED_RELATIONS:
                    db.add(OntologyTypeRelation(**r))
                db.commit()

                # 3. Seed default graph dataset
                nodes = [GraphNodeInstance(**n) for n in DEFAULT_SEED_NODES]
                edges = [GraphEdgeInstance(**e) for e in DEFAULT_SEED_EDGES]
                dataset = KnowledgeGraphDataset(
                    id=DEFAULT_SEED_GRAPH_META.get("id", "default"),
                    name=DEFAULT_SEED_GRAPH_META.get("name", "Enterprise Knowledge Graph"),
                    version=DEFAULT_SEED_GRAPH_META.get("version", "1.0.0"),
                    description=DEFAULT_SEED_GRAPH_META.get("description"),
                    nodes=nodes,
                    edges=edges,
                )
                persist_dataset(db, dataset)
                return

            # Ensure default type relations exist if missing
            if db.query(OntologyTypeRelation).count() == 0:
                for r in DEFAULT_SEED_RELATIONS:
                    db.add(OntologyTypeRelation(**r))
                db.commit()

            # Ensure default graph exists if types are already seeded
            default_graph = db.query(OntologyGraph).filter_by(id="default").first()
            if not default_graph or db.query(OntologyNode).filter_by(graph_id="default").count() == 0:
                nodes = [GraphNodeInstance(**n) for n in DEFAULT_SEED_NODES]
                edges = [GraphEdgeInstance(**e) for e in DEFAULT_SEED_EDGES]
                dataset = KnowledgeGraphDataset(
                    id=DEFAULT_SEED_GRAPH_META.get("id", "default"),
                    name=DEFAULT_SEED_GRAPH_META.get("name", "Enterprise Knowledge Graph"),
                    version=DEFAULT_SEED_GRAPH_META.get("version", "1.0.0"),
                    description=DEFAULT_SEED_GRAPH_META.get("description"),
                    nodes=nodes,
                    edges=edges,
                )
                persist_dataset(db, dataset)

        except Exception as err:
            db.rollback()
            self.log.warning("Ontology default seed warning (non-fatal): %s", err)

def ensure_default_seed(db: Session) -> None:
    from app.ontology.composition import ontology_log
    return EnsureDefaultSeed(ontology_log()).execute(db)
