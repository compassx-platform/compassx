"""Unit tests for Unified Catalog Queries."""

from __future__ import annotations

import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import AccountBase as Base
from app.catalog.models import (
    UnifiedCatalog,
    UnifiedCatalogSchema,
    UnifiedCatalogQuery,
    UnifiedCatalogQueryVersion,
)
from app.catalog.schemas import QueryCreate, QueryUpdate, QueryMove, QueryCreateVersion
from app.catalog.service import (
    create_query,
    list_queries,
    get_query,
    update_query,
    move_query,
    delete_query,
    create_query_version,
    list_query_versions,
    get_query_version,
    restore_query_version,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed catalog and schema
    cat = UnifiedCatalog(name="main_cat", created_by="test_user")
    session.add(cat)
    session.commit()
    session.refresh(cat)

    sch = UnifiedCatalogSchema(catalog_id=cat.id, name="analytics", created_by="test_user")
    session.add(sch)
    session.commit()
    session.refresh(sch)

    yield session
    session.close()


def test_create_and_get_query(db_session):
    user = {"email": "alice@company.com"}
    create_body = QueryCreate(
        name="Daily_Active_Users",
        sql_text="SELECT date, count(distinct user_id) FROM events GROUP BY 1;",
        description="Calculates DAU metric",
    )

    created = asyncio.run(create_query(db_session, "main_cat", "analytics", create_body, user))
    assert created.id is not None
    assert created.name == "Daily_Active_Users"
    assert created.catalog_name == "main_cat"
    assert created.schema_name == "analytics"
    assert created.sql_text == "SELECT date, count(distinct user_id) FROM events GROUP BY 1;"
    assert created.description == "Calculates DAU metric"
    assert created.owner == "alice@company.com"

    fetched = get_query(db_session, "main_cat", "analytics", "Daily_Active_Users")
    assert fetched.id == created.id
    assert fetched.name == "Daily_Active_Users"


def test_list_queries(db_session):
    user = {"email": "alice@company.com"}
    asyncio.run(create_query(
        db_session,
        "main_cat",
        "analytics",
        QueryCreate(name="Q1", sql_text="SELECT 1;"),
        user,
    ))
    asyncio.run(create_query(
        db_session,
        "main_cat",
        "analytics",
        QueryCreate(name="Q2", sql_text="SELECT 2;"),
        user,
    ))

    queries = list_queries(db_session, "main_cat", "analytics")
    assert len(queries) == 2
    names = {q.name for q in queries}
    assert names == {"Q1", "Q2"}


def test_update_query(db_session):
    user = {"email": "alice@company.com"}
    asyncio.run(create_query(
        db_session,
        "main_cat",
        "analytics",
        QueryCreate(name="Revenue_Query", sql_text="SELECT sum(amount) FROM sales;"),
        user,
    ))

    update_body = QueryUpdate(
        name="Total_Revenue",
        sql_text="SELECT sum(amount) AS total FROM sales WHERE status = 'completed';",
        description="Updated revenue formula",
    )
    updated = update_query(db_session, "main_cat", "analytics", "Revenue_Query", update_body, user)
    assert updated.name == "Total_Revenue"
    assert "WHERE status = 'completed'" in updated.sql_text
    assert updated.description == "Updated revenue formula"


def test_delete_query(db_session):
    user = {"email": "alice@company.com"}
    asyncio.run(create_query(
        db_session,
        "main_cat",
        "analytics",
        QueryCreate(name="To_Delete", sql_text="SELECT 999;"),
        user,
    ))

    asyncio.run(delete_query(db_session, "main_cat", "analytics", "To_Delete"))

    with pytest.raises(ValueError, match="not found"):
        get_query(db_session, "main_cat", "analytics", "To_Delete")


def test_query_versioning_and_restore(db_session):
    user = {"email": "alice@company.com"}
    created = asyncio.run(create_query(
        db_session,
        "main_cat",
        "analytics",
        QueryCreate(name="Versioned_Query", sql_text="SELECT 1;", description="Initial query"),
        user,
    ))
    assert created.current_version == 1

    # Check v1 was created
    versions = list_query_versions(db_session, "main_cat", "analytics", "Versioned_Query")
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].sql_text == "SELECT 1;"
    assert versions[0].change_summary == "Initial version"

    # Create v2 via create_query_version
    v2 = create_query_version(
        db_session,
        "main_cat",
        "analytics",
        "Versioned_Query",
        QueryCreateVersion(sql_text="SELECT 1, 2;", change_summary="Added second column"),
        user,
    )
    assert v2.version == 2
    assert v2.sql_text == "SELECT 1, 2;"

    # Verify query updated to v2
    q = get_query(db_session, "main_cat", "analytics", "Versioned_Query")
    assert q.current_version == 2
    assert q.sql_text == "SELECT 1, 2;"

    # Create v3 via update_query with new SQL
    updated = update_query(
        db_session,
        "main_cat",
        "analytics",
        "Versioned_Query",
        QueryUpdate(sql_text="SELECT 1, 2, 3;", change_summary="Added third column"),
        user,
    )
    assert updated.current_version == 3
    assert updated.sql_text == "SELECT 1, 2, 3;"

    # List all versions
    all_versions = list_query_versions(db_session, "main_cat", "analytics", "Versioned_Query")
    assert len(all_versions) == 3
    assert [v.version for v in all_versions] == [3, 2, 1]

    # Restore v1 -> creates v4 with v1's SQL
    restored = restore_query_version(db_session, "main_cat", "analytics", "Versioned_Query", 1, user)
    assert restored.current_version == 4
    assert restored.sql_text == "SELECT 1;"

    v4 = get_query_version(db_session, "main_cat", "analytics", "Versioned_Query", 4)
    assert v4.change_summary == "Restored from version 1"


def test_duckdb_resolver_handles_reserved_catalog_names(db_session, monkeypatch):
    """Ensure catalogs named 'main', 'temp', 'system', or 'memory' do not produce invalid ATTACH statements."""
    from app.sql_warehouse.catalog.duckdb_resolver import build_duckdb_catalog_plan

    # Seed catalog named 'main'
    main_cat = UnifiedCatalog(name="main", created_by="test_user")
    db_session.add(main_cat)
    db_session.commit()
    db_session.refresh(main_cat)

    sch = UnifiedCatalogSchema(catalog_id=main_cat.id, name="default", created_by="test_user")
    db_session.add(sch)
    db_session.commit()

    # Monkeypatch AccountSessionLocal to return db_session
    monkeypatch.setattr("app.sql_warehouse.catalog.duckdb_resolver.AccountSessionLocal", lambda: db_session)

    plan = build_duckdb_catalog_plan(db_session)
    
    # Assert no ATTACH statement targets 'main'
    attach_main = [s for s in plan.setup_sql if 'ATTACH' in s and '"main"' in s]
    assert len(attach_main) == 0, f"Found unexpected ATTACH for reserved name 'main': {attach_main}"

    # Assert 'main_cat' (non-reserved) has ATTACH statement
    attach_main_cat = [s for s in plan.setup_sql if 'ATTACH' in s and '"main_cat"' in s]
    assert len(attach_main_cat) == 1, "Expected non-reserved catalog 'main_cat' to be attached"

    # Assert DuckDB can execute the full setup plan without error
    import duckdb
    conn = duckdb.connect(":memory:")
    for stmt in plan.setup_sql:
        conn.execute(stmt)
    conn.close()


