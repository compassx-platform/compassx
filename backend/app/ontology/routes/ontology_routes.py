"""FastAPI routes for Ontology Metamodel Schema, Validation, and Knowledge Graph persistence."""

from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.ontology.schemas.ontology import (
    TypeDefinitionCreate,
    TypeDefinitionUpdate,
    TypeDefinitionResponse,
    TypeRelationCreate,
    TypeRelationUpdate,
    TypeRelationResponse,
    KnowledgeGraphDataset,
    GraphValidationRequest,
    GraphValidationResult,
    KnowledgeGraphImportRequest,
    GraphNodeCreate,
    GraphNodeUpdate,
    GraphEdgeCreate,
)
from app.ontology.services.ontology_service import OntologyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ontology", tags=["Ontology & Knowledge Graph"])


# ─── Schema Entity Types ────────────────────────────────────────────────────────

@router.get("/schema/types", response_model=List[TypeDefinitionResponse])
def get_types(db: Session = Depends(get_account_db)):
    """List all entity types configured in the ontology metamodel."""
    return OntologyService.list_types(db)


@router.post("/schema/types", response_model=TypeDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_type(data: TypeDefinitionCreate, db: Session = Depends(get_account_db)):
    """Create a new entity type."""
    try:
        return OntologyService.create_type(db, data)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.put("/schema/types/{type_id}", response_model=TypeDefinitionResponse)
def update_type(type_id: str, data: TypeDefinitionUpdate, db: Session = Depends(get_account_db)):
    """Update an existing entity type's visual shape, radius, tier, or label."""
    try:
        return OntologyService.update_type(db, type_id, data)
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.delete("/schema/types/{type_id}")
def delete_type(type_id: str, db: Session = Depends(get_account_db)):
    """Delete a custom entity type and its cascade relations."""
    try:
        success = OntologyService.delete_type(db, type_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Entity type '{type_id}' not found.")
        return {"status": "deleted", "type_id": type_id}
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


# ─── Schema Type Relations (Metamodel) ──────────────────────────────────────────

@router.get("/schema/relations", response_model=List[TypeRelationResponse])
def get_type_relations(db: Session = Depends(get_account_db)):
    """List all allowed relationship rules between entity types."""
    return OntologyService.list_type_relations(db)


@router.post("/schema/relations", response_model=TypeRelationResponse, status_code=status.HTTP_201_CREATED)
def create_type_relation(data: TypeRelationCreate, db: Session = Depends(get_account_db)):
    """Define a new allowed relationship rule in the metamodel schema."""
    try:
        return OntologyService.create_type_relation(db, data)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.put("/schema/relations/{relation_id}", response_model=TypeRelationResponse)
def update_type_relation(relation_id: int, data: TypeRelationUpdate, db: Session = Depends(get_account_db)):
    """Update an existing allowed relationship rule in the metamodel schema."""
    try:
        return OntologyService.update_type_relation(db, relation_id, data)
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete("/schema/relations/{relation_id}")
def delete_type_relation(relation_id: int, db: Session = Depends(get_account_db)):
    """Delete an allowed relationship rule."""
    try:
        success = OntologyService.delete_type_relation(db, relation_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Relationship rule with ID '{relation_id}' not found.")
        return {"status": "deleted", "relation_id": relation_id}
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


# ─── Knowledge Graph Ingestion & Validation ─────────────────────────────────────

@router.get("/graph/active", response_model=KnowledgeGraphDataset)
def get_active_graph(graph_id: str = "default", db: Session = Depends(get_account_db)):
    """Fetch the active Knowledge Graph (nodes & edges) from database."""
    try:
        return OntologyService.get_active_graph(db, graph_id=graph_id)
    except Exception as err:
        logger.error("Failed to load active graph: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.post("/graph/validate", response_model=GraphValidationResult)
def validate_graph(payload: GraphValidationRequest, db: Session = Depends(get_account_db)):
    """Validate a YAML or Dataset payload against the database schema metamodel without persisting."""
    try:
        if payload.yaml_content:
            dataset = OntologyService.parse_yaml_to_dataset(payload.yaml_content)
        elif payload.dataset:
            dataset = payload.dataset
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must provide 'yaml_content' or 'dataset'.")

        return OntologyService.validate_graph(db, dataset)
    except ValueError as err:
        return GraphValidationResult(
            valid=False,
            errors=[str(err)],
            warnings=[],
            node_count=0,
            edge_count=0,
        )


@router.post("/graph/import-yaml", response_model=KnowledgeGraphDataset)
def import_yaml_graph(payload: KnowledgeGraphImportRequest, db: Session = Depends(get_account_db)):
    """Validate and persist a Knowledge Graph from YAML or dataset into the database."""
    try:
        return OntologyService.import_yaml_or_dataset(db, payload)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except Exception as err:
        logger.error("Failed to import knowledge graph: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.post("/graph/nodes", response_model=KnowledgeGraphDataset, status_code=status.HTTP_201_CREATED)
def add_graph_node(payload: GraphNodeCreate, db: Session = Depends(get_account_db)):
    """Add a new entity node to the knowledge graph with strict schema validation."""
    try:
        return OntologyService.add_node(db, payload)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except Exception as err:
        logger.error("Failed to add node: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.put("/graph/nodes/{node_id}", response_model=KnowledgeGraphDataset)
def update_graph_node(node_id: str, payload: GraphNodeUpdate, graph_id: str = "default", db: Session = Depends(get_account_db)):
    """Update an existing node with schema validation."""
    try:
        return OntologyService.update_node(db, node_id, payload, graph_id=graph_id)
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except Exception as err:
        logger.error("Failed to update node: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.delete("/graph/nodes/{node_id}", response_model=KnowledgeGraphDataset)
def delete_graph_node(node_id: str, graph_id: str = "default", db: Session = Depends(get_account_db)):
    """Delete a node and its connecting edges from the knowledge graph."""
    try:
        return OntologyService.delete_node(db, node_id, graph_id=graph_id)
    except Exception as err:
        logger.error("Failed to delete node: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.post("/graph/edges", response_model=KnowledgeGraphDataset, status_code=status.HTTP_201_CREATED)
def add_graph_edge(payload: GraphEdgeCreate, db: Session = Depends(get_account_db)):
    """Add a new relationship edge between two nodes with metamodel validation."""
    try:
        return OntologyService.add_edge(db, payload)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    except Exception as err:
        logger.error("Failed to add edge: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.delete("/graph/edges/{edge_id}", response_model=KnowledgeGraphDataset)
def delete_graph_edge(edge_id: str, graph_id: str = "default", db: Session = Depends(get_account_db)):
    """Delete an edge from the knowledge graph."""
    try:
        return OntologyService.delete_edge(db, edge_id, graph_id=graph_id)
    except Exception as err:
        logger.error("Failed to delete edge: %s", err)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))

