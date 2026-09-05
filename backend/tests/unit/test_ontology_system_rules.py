import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import AccountBase as Base
from app.ontology.models.ontology import (
    OntologyType,
    OntologyTypeRelation,
    OntologyGraph,
    OntologyNode,
    OntologyEdge,
)
from app.ontology.services.ontology_service import OntologyService
from app.ontology.schemas.ontology import TypeDefinitionCreate, TypeDefinitionUpdate, TypeRelationCreate, TypeRelationUpdate


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_ensure_default_seed_creates_system_hierarchy(db_session):
    OntologyService.ensure_default_seed(db_session)

    types = OntologyService.list_types(db_session)
    type_ids = {t.id: t for t in types}

    # Verify 4 system types
    assert "org" in type_ids
    assert "domain" in type_ids
    assert "subdomain" in type_ids
    assert "element" in type_ids

    assert type_ids["org"].is_system is True
    assert type_ids["org"].tier == 0
    assert type_ids["domain"].is_system is True
    assert type_ids["domain"].tier == 1
    assert type_ids["subdomain"].is_system is True
    assert type_ids["subdomain"].tier == 2
    assert type_ids["element"].is_system is True
    assert type_ids["element"].tier == 3

    # Verify system containment rules
    relations = OntologyService.list_type_relations(db_session)
    system_containment_rules = [
        r for r in relations if r.is_system and r.relation_type == "contains"
    ]

    rule_signatures = {
        (r.source_type_id, r.relation_type, r.target_type_id): r
        for r in system_containment_rules
    }

    assert ("org", "contains", "domain") in rule_signatures
    assert ("domain", "contains", "subdomain") in rule_signatures
    assert ("subdomain", "contains", "element") in rule_signatures

    for rule in rule_signatures.values():
        assert rule.is_hierarchical is True
        assert rule.is_system is True


def test_system_types_cannot_be_deleted(db_session):
    OntologyService.ensure_default_seed(db_session)

    for sys_type in ["org", "domain", "subdomain", "element"]:
        with pytest.raises(ValueError, match="protected and cannot be deleted"):
            OntologyService.delete_type(db_session, sys_type)


def test_system_type_tier_cannot_be_mutated(db_session):
    OntologyService.ensure_default_seed(db_session)

    with pytest.raises(ValueError, match="hierarchy tier cannot be changed"):
        OntologyService.update_type(db_session, "org", TypeDefinitionUpdate(tier=2))


def test_system_relations_cannot_be_deleted(db_session):
    OntologyService.ensure_default_seed(db_session)

    relations = OntologyService.list_type_relations(db_session)
    org_contains_domain = next(
        r for r in relations if r.source_type_id == "org" and r.target_type_id == "domain"
    )

    with pytest.raises(ValueError, match="protected and cannot be deleted"):
        OntologyService.delete_type_relation(db_session, org_contains_domain.id)


def test_custom_types_and_relations_work_normally(db_session):
    OntologyService.ensure_default_seed(db_session)

    # User creates custom type
    custom_type = OntologyService.create_type(
        db_session,
        TypeDefinitionCreate(
            id="service",
            label="Microservice",
            shape="circle",
            baseRadius=14,
            tier=2,
            is_system=False,
        ),
    )
    assert custom_type.id == "service"
    assert custom_type.is_system is False

    # User creates custom relation
    custom_rel = OntologyService.create_type_relation(
        db_session,
        TypeRelationCreate(
            source_type_id="service",
            relation_type="calls",
            target_type_id="service",
            is_hierarchical=False,
            is_system=False,
        ),
    )
    assert custom_rel.id is not None
    assert custom_rel.is_system is False

    # User can delete custom relation and type
    assert OntologyService.delete_type_relation(db_session, custom_rel.id) is True
    assert OntologyService.delete_type(db_session, "service") is True


def test_update_type_relation_custom_and_system(db_session):
    OntologyService.ensure_default_seed(db_session)

    # 1. Updating custom relation works
    custom_type = OntologyService.create_type(
        db_session,
        TypeDefinitionCreate(
            id="service",
            label="Microservice",
            shape="circle",
            baseRadius=14,
            tier=2,
            is_system=False,
        ),
    )
    custom_rel = OntologyService.create_type_relation(
        db_session,
        TypeRelationCreate(
            source_type_id="service",
            relation_type="calls",
            target_type_id="element",
            is_hierarchical=False,
            is_system=False,
            description="Initial description",
        ),
    )

    updated = OntologyService.update_type_relation(
        db_session,
        custom_rel.id,
        TypeRelationUpdate(
            relation_type="invokes",
            description="Updated description",
        ),
    )
    assert updated.relation_type == "invokes"
    assert updated.description == "Updated description"

    # 2. Updating system rule raises error
    relations = OntologyService.list_type_relations(db_session)
    org_contains_domain = next(
        r for r in relations if r.source_type_id == "org" and r.target_type_id == "domain"
    )
    with pytest.raises(ValueError, match="protected and cannot be edited"):
        OntologyService.update_type_relation(
            db_session,
            org_contains_domain.id,
            TypeRelationUpdate(description="Custom explanation of org containment"),
        )

