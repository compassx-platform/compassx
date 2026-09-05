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

logger = logging.getLogger(__name__)


def slugify_type_id(raw_id: str) -> str:
    """Normalize a type ID to a clean URL/slug string."""
    clean = raw_id.strip().lower()
    clean = re.sub(r"[^a-z0-9_-]", "-", clean)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean or "custom-type"


class OntologyService:
    """Business logic for Ontology Metamodel and Graph Instances."""

    # ─── Seeding ─────────────────────────────────────────────────────────────

    @classmethod
    def ensure_default_seed(cls, db: Session) -> None:
        """Seed default types, metamodel relations, and default graph if not present or migrate legacy seed."""
        try:
            # Check if database has legacy seed (project / capability) or is missing org
            has_org = db.query(OntologyType).filter_by(id="org").first() is not None
            has_legacy = db.query(OntologyType).filter(OntologyType.id.in_(["project", "capability"])).first() is not None
            existing_type_count = db.query(OntologyType).count()

            if existing_type_count == 0 or (has_legacy and not has_org):
                logger.info("Migrating / Seeding default ontology schema (org -> domain -> subdomain -> element)...")
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
                cls._persist_dataset(db, dataset)
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
                cls._persist_dataset(db, dataset)

        except Exception as err:
            db.rollback()
            logger.warning("Ontology default seed warning (non-fatal): %s", err)

    # ─── Metamodel Types CRUD ────────────────────────────────────────────────

    @classmethod
    def list_types(cls, db: Session) -> List[OntologyType]:
        cls.ensure_default_seed(db)
        return db.query(OntologyType).order_by(OntologyType.tier.asc(), OntologyType.created_at.asc()).all()

    @classmethod
    def get_type(cls, db: Session, type_id: str) -> Optional[OntologyType]:
        return db.query(OntologyType).filter_by(id=type_id).first()

    @classmethod
    def create_type(cls, db: Session, data: TypeDefinitionCreate) -> OntologyType:
        clean_id = slugify_type_id(data.id)
        existing = db.query(OntologyType).filter_by(id=clean_id).first()
        if existing:
            raise ValueError(f"Entity type with ID '{clean_id}' already exists.")

        record = OntologyType(
            id=clean_id,
            label=data.label.strip(),
            description=data.description,
            shape=data.shape,
            base_radius=data.base_radius,
            tier=data.tier,
            color=data.color,
            icon=data.icon,
            is_system=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def update_type(cls, db: Session, type_id: str, data: TypeDefinitionUpdate) -> OntologyType:
        record = db.query(OntologyType).filter_by(id=type_id).first()
        if not record:
            raise KeyError(f"Entity type '{type_id}' not found.")

        if record.is_system and data.tier is not None and data.tier != record.tier:
            raise ValueError(f"System type '{type_id}' is protected and its hierarchy tier cannot be changed.")

        if data.label is not None:
            record.label = data.label.strip()
        if data.description is not None:
            record.description = data.description
        if data.shape is not None:
            record.shape = data.shape
        if data.base_radius is not None:
            record.base_radius = data.base_radius
        if data.tier is not None and not record.is_system:
            record.tier = data.tier
        if data.color is not None:
            record.color = data.color
        if data.icon is not None:
            record.icon = data.icon

        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def delete_type(cls, db: Session, type_id: str) -> bool:
        record = db.query(OntologyType).filter_by(id=type_id).first()
        if not record:
            return False

        if record.is_system:
            raise ValueError(f"System type '{type_id}' is protected and cannot be deleted.")

        # Cascade delete will remove related type relations automatically
        db.delete(record)
        db.commit()
        return True

    # ─── Metamodel Type Relations CRUD ───────────────────────────────────────

    @classmethod
    def list_type_relations(cls, db: Session) -> List[OntologyTypeRelation]:
        cls.ensure_default_seed(db)
        return db.query(OntologyTypeRelation).order_by(OntologyTypeRelation.source_type_id.asc(), OntologyTypeRelation.relation_type.asc()).all()

    @classmethod
    def create_type_relation(cls, db: Session, data: TypeRelationCreate) -> OntologyTypeRelation:
        # Validate that source and target types exist
        src = db.query(OntologyType).filter_by(id=data.source_type_id).first()
        if not src:
            raise ValueError(f"Source entity type '{data.source_type_id}' does not exist.")
        tgt = db.query(OntologyType).filter_by(id=data.target_type_id).first()
        if not tgt:
            raise ValueError(f"Target entity type '{data.target_type_id}' does not exist.")

        clean_rel = data.relation_type.strip().lower().replace(" ", "_")

        existing = (
            db.query(OntologyTypeRelation)
            .filter_by(
                source_type_id=data.source_type_id,
                relation_type=clean_rel,
                target_type_id=data.target_type_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Relationship rule '{data.source_type_id} --[{clean_rel}]--> {data.target_type_id}' already exists."
            )

        record = OntologyTypeRelation(
            source_type_id=data.source_type_id,
            relation_type=clean_rel,
            target_type_id=data.target_type_id,
            is_hierarchical=data.is_hierarchical or (clean_rel == "contains"),
            is_system=data.is_system if hasattr(data, "is_system") else False,
            description=data.description,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def update_type_relation(cls, db: Session, rel_id: int, data: TypeRelationUpdate) -> OntologyTypeRelation:
        record = db.query(OntologyTypeRelation).filter_by(id=rel_id).first()
        if not record:
            raise KeyError(f"Relationship rule with ID '{rel_id}' not found.")

        # Determine target values
        new_source = data.source_type_id if data.source_type_id is not None else record.source_type_id
        new_target = data.target_type_id if data.target_type_id is not None else record.target_type_id
        new_rel_type = (data.relation_type.strip().lower().replace(" ", "_")) if data.relation_type is not None else record.relation_type

        if record.is_system:
            raise ValueError("System relationship rule is protected and cannot be edited.")

        if data.source_type_id is not None:
            src = db.query(OntologyType).filter_by(id=new_source).first()
            if not src:
                raise ValueError(f"Source entity type '{new_source}' does not exist.")

        if data.target_type_id is not None:
            tgt = db.query(OntologyType).filter_by(id=new_target).first()
            if not tgt:
                raise ValueError(f"Target entity type '{new_target}' does not exist.")

        # Check uniqueness constraint if signature is changing
        if (
            new_source != record.source_type_id
            or new_rel_type != record.relation_type
            or new_target != record.target_type_id
        ):
            dup = (
                db.query(OntologyTypeRelation)
                .filter(
                    OntologyTypeRelation.id != rel_id,
                    OntologyTypeRelation.source_type_id == new_source,
                    OntologyTypeRelation.relation_type == new_rel_type,
                    OntologyTypeRelation.target_type_id == new_target,
                )
                .first()
            )
            if dup:
                raise ValueError(
                    f"Relationship rule '{new_source} --[{new_rel_type}]--> {new_target}' already exists."
                )

        record.source_type_id = new_source
        record.relation_type = new_rel_type
        record.target_type_id = new_target
        if data.is_hierarchical is not None:
            record.is_hierarchical = data.is_hierarchical or (new_rel_type == "contains")
        if data.description is not None:
            record.description = data.description

        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def delete_type_relation(cls, db: Session, rel_id: int) -> bool:
        record = db.query(OntologyTypeRelation).filter_by(id=rel_id).first()
        if not record:
            return False

        if record.is_system:
            raise ValueError("System relationship rule is protected and cannot be deleted.")

        db.delete(record)
        db.commit()
        return True

    # ─── Metamodel Graph Validation Engine ───────────────────────────────────

    @classmethod
    def validate_graph(cls, db: Session, dataset: KnowledgeGraphDataset) -> GraphValidationResult:
        """Enforces that all nodes, hierarchy links, and typed edges conform to the metamodel schema in DB."""
        cls.ensure_default_seed(db)

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

    # ─── YAML Parsing & Serialization ────────────────────────────────────────

    @classmethod
    def parse_yaml_to_dataset(cls, yaml_str: str) -> KnowledgeGraphDataset:
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

    # ─── Knowledge Graph Ingestion & Query ───────────────────────────────────

    @classmethod
    def get_active_graph(cls, db: Session, graph_id: str = "default") -> KnowledgeGraphDataset:
        cls.ensure_default_seed(db)

        graph_meta = db.query(OntologyGraph).filter_by(id=graph_id).first()
        if not graph_meta:
            # Fallback to default seed if missing
            cls.ensure_default_seed(db)
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

    @classmethod
    def _persist_dataset(cls, db: Session, dataset: KnowledgeGraphDataset, raw_yaml: Optional[str] = None) -> None:
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

    @classmethod
    def import_yaml_or_dataset(cls, db: Session, req: KnowledgeGraphImportRequest) -> KnowledgeGraphDataset:
        """Validates against metamodel in DB and persists the new Knowledge Graph to database."""
        cls.ensure_default_seed(db)

        raw_yaml_str: Optional[str] = None
        if req.yaml_content:
            raw_yaml_str = req.yaml_content
            dataset = cls.parse_yaml_to_dataset(req.yaml_content)
        elif req.dataset:
            dataset = req.dataset
        else:
            raise ValueError("Must provide either 'yaml_content' or 'dataset'.")

        if req.graph_id:
            dataset.id = req.graph_id
        if req.name:
            dataset.name = req.name
        if req.version:
            dataset.version = req.version
        if req.description:
            dataset.description = req.description

        # Enforce validation against DB Metamodel
        val_result = cls.validate_graph(db, dataset)
        if not val_result.valid:
            error_details = "\n• " + "\n• ".join(val_result.errors)
            raise ValueError(f"Schema metamodel validation failed with {len(val_result.errors)} errors:{error_details}")

        # Persist to database
        cls._persist_dataset(db, dataset, raw_yaml=raw_yaml_str)
        return cls.get_active_graph(db, graph_id=dataset.id or "default")

    # ─── Granular Node & Edge CRUD ───────────────────────────────────────────

    @classmethod
    def add_node(cls, db: Session, data: GraphNodeCreate) -> KnowledgeGraphDataset:
        """Adds a single node to the active graph, strictly enforcing metamodel rules."""
        cls.ensure_default_seed(db)
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
        return cls.get_active_graph(db, graph_id=graph_id)

    @classmethod
    def update_node(cls, db: Session, node_id: str, data: GraphNodeUpdate, graph_id: str = "default") -> KnowledgeGraphDataset:
        """Updates a node in the graph, enforcing metamodel validation if kind or parentId changes."""
        cls.ensure_default_seed(db)
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
        return cls.get_active_graph(db, graph_id=graph_id)

    @classmethod
    def delete_node(cls, db: Session, node_id: str, graph_id: str = "default") -> KnowledgeGraphDataset:
        """Deletes a node and any connected edges from the graph."""
        cls.ensure_default_seed(db)
        # Delete incident edges
        db.query(OntologyEdge).filter(
            OntologyEdge.graph_id == graph_id,
            (OntologyEdge.source_id == node_id) | (OntologyEdge.target_id == node_id),
        ).delete(synchronize_session=False)

        # Delete node
        db.query(OntologyNode).filter_by(graph_id=graph_id, id=node_id).delete()
        db.commit()
        return cls.get_active_graph(db, graph_id=graph_id)

    @classmethod
    def add_edge(cls, db: Session, data: GraphEdgeCreate) -> KnowledgeGraphDataset:
        """Adds a directional edge between two nodes, validating metamodel rules."""
        cls.ensure_default_seed(db)
        graph_id = data.graph_id or "default"

        src = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.source).first()
        if not src:
            raise ValueError(f"Source node '{data.source}' does not exist.")

        tgt = db.query(OntologyNode).filter_by(graph_id=graph_id, id=data.target).first()
        if not tgt:
            raise ValueError(f"Target node '{data.target}' does not exist.")

        clean_rel = data.type.strip().lower().replace(" ", "_")
        allowed_rel = db.query(OntologyTypeRelation).filter_by(
            source_type_id=src.type_id,
            relation_type=clean_rel,
            target_type_id=tgt.type_id,
        ).first()
        if not allowed_rel:
            raise ValueError(
                f"Disallowed relationship: '{src.type_id} --[{clean_rel}]--> {tgt.type_id}' "
                f"is not permitted by the metamodel schema."
            )

        edge_id = data.id or f"{data.source}->{data.target}"
        existing = db.query(OntologyEdge).filter_by(graph_id=graph_id, id=edge_id).first()
        if existing:
            raise ValueError(f"Edge with ID '{edge_id}' already exists.")

        edge_record = OntologyEdge(
            id=edge_id,
            graph_id=graph_id,
            source_id=data.source,
            target_id=data.target,
            relation_type=clean_rel,
            description=data.description,
            properties=data.properties or {},
        )
        db.add(edge_record)
        db.commit()
        return cls.get_active_graph(db, graph_id=graph_id)

    @classmethod
    def delete_edge(cls, db: Session, edge_id: str, graph_id: str = "default") -> KnowledgeGraphDataset:
        """Deletes an edge from the graph."""
        cls.ensure_default_seed(db)
        db.query(OntologyEdge).filter_by(graph_id=graph_id, id=edge_id).delete()
        db.commit()
        return cls.get_active_graph(db, graph_id=graph_id)
