"""Ontology application facade.

``OntologyService`` stays importable from ``app.ontology.services.ontology_service``.
Each classmethod forwards to one application type.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.ontology.models.ontology import OntologyType, OntologyTypeRelation
from app.ontology.runtime import (
    ensure_default_seed,
    list_types,
    get_type,
    create_type,
    update_type,
    delete_type,
    list_type_relations,
    create_type_relation,
    update_type_relation,
    delete_type_relation,
    validate_graph,
    parse_yaml_to_dataset,
    get_active_graph,
    persist_dataset,
    import_yaml_or_dataset,
    add_node,
    update_node,
    delete_node,
    add_edge,
    delete_edge,
)
from app.ontology.schemas.ontology import (
    GraphEdgeCreate,
    GraphNodeCreate,
    GraphNodeUpdate,
    GraphValidationResult,
    KnowledgeGraphDataset,
    KnowledgeGraphImportRequest,
    TypeDefinitionCreate,
    TypeDefinitionUpdate,
    TypeRelationCreate,
    TypeRelationUpdate,
)
from app.ontology.types.repository import slugify_type_id

__all__ = ["OntologyService", "slugify_type_id"]


class OntologyService:
    @classmethod
    def ensure_default_seed(cls, db: Session) -> None:
        return ensure_default_seed(db)

    @classmethod
    def list_types(cls, db: Session) -> List[OntologyType]:
        return list_types(db)

    @classmethod
    def get_type(cls, db: Session, type_id: str) -> Optional[OntologyType]:
        return get_type(db, type_id)

    @classmethod
    def create_type(cls, db: Session, data: TypeDefinitionCreate) -> OntologyType:
        return create_type(db, data)

    @classmethod
    def update_type(cls, db: Session, type_id: str, data: TypeDefinitionUpdate) -> OntologyType:
        return update_type(db, type_id, data)

    @classmethod
    def delete_type(cls, db: Session, type_id: str) -> bool:
        return delete_type(db, type_id)

    @classmethod
    def list_type_relations(cls, db: Session) -> List[OntologyTypeRelation]:
        return list_type_relations(db)

    @classmethod
    def create_type_relation(cls, db: Session, data: TypeRelationCreate) -> OntologyTypeRelation:
        return create_type_relation(db, data)

    @classmethod
    def update_type_relation(cls, db: Session, rel_id: int, data: TypeRelationUpdate) -> OntologyTypeRelation:
        return update_type_relation(db, rel_id, data)

    @classmethod
    def delete_type_relation(cls, db: Session, rel_id: int) -> bool:
        return delete_type_relation(db, rel_id)

    @classmethod
    def validate_graph(cls, db: Session, dataset: KnowledgeGraphDataset) -> GraphValidationResult:
        return validate_graph(db, dataset)

    @classmethod
    def parse_yaml_to_dataset(cls, yaml_str: str) -> KnowledgeGraphDataset:
        return parse_yaml_to_dataset(yaml_str)

    @classmethod
    def get_active_graph(cls, db: Session, graph_id: str='default') -> KnowledgeGraphDataset:
        return get_active_graph(db, graph_id)

    @classmethod
    def _persist_dataset(cls, db: Session, dataset: KnowledgeGraphDataset, raw_yaml: Optional[str]=None) -> None:
        return persist_dataset(db, dataset, raw_yaml)

    @classmethod
    def import_yaml_or_dataset(cls, db: Session, req: KnowledgeGraphImportRequest) -> KnowledgeGraphDataset:
        return import_yaml_or_dataset(db, req)

    @classmethod
    def add_node(cls, db: Session, data: GraphNodeCreate) -> KnowledgeGraphDataset:
        return add_node(db, data)

    @classmethod
    def update_node(cls, db: Session, node_id: str, data: GraphNodeUpdate, graph_id: str='default') -> KnowledgeGraphDataset:
        return update_node(db, node_id, data, graph_id)

    @classmethod
    def delete_node(cls, db: Session, node_id: str, graph_id: str='default') -> KnowledgeGraphDataset:
        return delete_node(db, node_id, graph_id)

    @classmethod
    def add_edge(cls, db: Session, data: GraphEdgeCreate) -> KnowledgeGraphDataset:
        return add_edge(db, data)

    @classmethod
    def delete_edge(cls, db: Session, edge_id: str, graph_id: str='default') -> KnowledgeGraphDataset:
        return delete_edge(db, edge_id, graph_id)

