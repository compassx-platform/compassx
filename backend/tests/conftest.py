"""
Shared pytest fixtures for the CompassX backend test suite.

Architecture
------------
- All tests use an **in-memory SQLite** database to avoid requiring a live
  PostgreSQL instance in CI.
- PostgreSQL-specific column types (JSONB, UUID) are shimmed to their SQLite
  equivalents via SQLAlchemy's @compiles extension mechanism.
- The FastAPI app is constructed fresh for each test session with all
  database dependencies overridden to use the test database.
- The `get_current_user` dependency is overridden to return a fixed mock user
  so no external User Manager service is needed.
"""

from __future__ import annotations

import os
import sys
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Ensure the backend/ directory is on sys.path so `app.*` imports work.
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Set required environment variables BEFORE importing app modules that read
# settings at module-load time.
# ---------------------------------------------------------------------------
os.environ.setdefault("PG_PASSWORD", "test")
os.environ["SKIP_DB_INIT"] = "true"
os.environ.setdefault(
    "CATALOG_ENCRYPTION_KEY",
    "dGVzdC1rZXktZm9yLXVuaXQtdGVzdHMtMzItYnl0ZXM="  # base64 of 32-byte test key
)

# ---------------------------------------------------------------------------
# Shim PostgreSQL-specific types to SQLite equivalents.
# Must be done BEFORE any app.models.* are imported.
# ---------------------------------------------------------------------------
import json
import sqlalchemy.dialects.postgresql
from sqlalchemy.types import TypeDecorator, TEXT

class SQLiteArray(TypeDecorator):
    impl = TEXT
    cache_ok = True

    def __init__(self, item_type, *args, **kwargs):
        self.item_type = item_type
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return value

sqlalchemy.dialects.postgresql.ARRAY = SQLiteArray

from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID, INET, ARRAY  # noqa: E402


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: D401
    return "TEXT"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # noqa: D401
    return "TEXT"


@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):  # noqa: D401
    return "TEXT"



from sqlalchemy.schema import CreateTable

@compiles(CreateTable, "sqlite")
def _compile_create_table_sqlite(element, compiler, **kw):
    ddl = compiler.visit_create_table(element, **kw)
    ddl = ddl.replace("DEFAULT gen_random_uuid()", "DEFAULT (lower(hex(randomblob(16))))")
    ddl = ddl.replace("DEFAULT now()", "DEFAULT CURRENT_TIMESTAMP")
    return ddl


# ---------------------------------------------------------------------------
# Import app models (triggers SQLAlchemy mapper registration).
# ---------------------------------------------------------------------------
from app.database import Base, AssetBase  # noqa: E402
from app.workspace import models as workspace_models  # noqa: F401, E402
from app.models import agents, dataset, data_catalog, unified_catalog  # noqa: E402, F401
import app.asset_manager.models.asset_manager  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Test database engine — single shared in-memory SQLite instance.
# StaticPool ensures all connections share the same in-memory DB.
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

# Enable foreign key enforcement and disable sqlite3 transaction management
@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    dbapi_conn.isolation_level = None
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Emit manual BEGIN statements to SQLite since autocommit mode is enabled
@event.listens_for(test_engine, "begin")
def _db_begin(conn):
    conn.exec_driver_sql("BEGIN")


TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

# Route System and Data engines to the in-memory test database with a session proxy
class SessionProxy:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass

    def commit(self):
        self._session.flush()

    def rollback(self):
        self._session.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class TestAccountSessionLocal:
    def __call__(self):
        import sys
        database_modules = {k: v for k, v in sys.modules.items() if "database" in k}
        print("TestAccountSessionLocal called. database_modules in sys.modules:")
        for k, v in database_modules.items():
            print(f"  {k}: id={id(v)}, has_attr={hasattr(v, '_current_db_session')}, attr_val={getattr(v, '_current_db_session', None)}")
        curr = getattr(app.database, "_current_db_session", None)
        if curr is not None:
            print("Returning SessionProxy wrapping", id(curr))
            return SessionProxy(curr)
        # Check if any other database module has it
        for m in database_modules.values():
            if getattr(m, "_current_db_session", None) is not None:
                curr = m._current_db_session
                print("Found _current_db_session in other module instance:", id(m))
                return SessionProxy(curr)
        print("Returning new TestSessionLocal")
        return TestSessionLocal()

import app.database
app.database.AccountSessionLocal = TestAccountSessionLocal()
app.database.SystemSessionLocal = TestAccountSessionLocal()
app.database.AssetSessionLocal = TestAccountSessionLocal()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session."""
    import app.sql_warehouse.models  # noqa: F401
    import app.user_manager.models.system_models  # noqa: F401
    import app.user_manager.models.account_models  # noqa: F401
    from app.database import AccountBase, SystemBase, AssetBase
    if "sqlite" in test_engine.name:
        for table in AccountBase.metadata.tables.values():
            table.schema = None
        for table in SystemBase.metadata.tables.values():
            table.schema = None
        for table in AssetBase.metadata.tables.values():
            table.schema = None
    Base.metadata.create_all(bind=test_engine)
    AccountBase.metadata.create_all(bind=test_engine)
    SystemBase.metadata.create_all(bind=test_engine)
    AssetBase.metadata.create_all(bind=test_engine)

    from app.user_manager.models.system_models import UmWorkspaceRole
    with Session(test_engine) as init_session:
        for r_id, r_name in [("workspace_admin", "Workspace Admin"), ("analyst", "Analyst"), ("business_viewer", "Business Viewer")]:
            if not init_session.query(UmWorkspaceRole).filter(UmWorkspaceRole.id == r_id).first():
                init_session.add(UmWorkspaceRole(id=r_id, display_name=r_name))
        init_session.commit()
    yield
    try:
        Base.metadata.drop_all(bind=test_engine)
        AccountBase.metadata.drop_all(bind=test_engine)
        SystemBase.metadata.drop_all(bind=test_engine)
        AssetBase.metadata.drop_all(bind=test_engine)
    except OperationalError as error:
        # SQLite schema cleanup can fail if the database state has become inconsistent
        # during a failed test run. Avoid hiding the actual failure, but allow the
        # fixture teardown to complete cleanly when teardown itself is the issue.
        print(f"Warning: cleanup drop_all failed: {error}")


@pytest.fixture()
def db_session(create_tables) -> Generator[Session, None, None]:
    """
    Provide a transactional database session that is rolled back after each test.

    This ensures complete test isolation — every test starts with a clean slate
    without needing to truncate tables manually.
    """
    connection = test_engine.connect()
    if "sqlite" in test_engine.name:
        import sqlite3
        dbapi_conn = connection.connection
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("ATTACH DATABASE ':memory:' AS ai")
        except (sqlite3.OperationalError, sqlite3.ProgrammingError):
            # Already attached
            pass
        cursor.close()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    # Patch the savepoint so nested transactions work in SQLite
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    # Set the current DB session globally so TestAccountSessionLocal uses it
    import app.database
    app.database._current_db_session = session

    try:
        yield session
    finally:
        app.database._current_db_session = None
        session.close()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# FastAPI test application
# ---------------------------------------------------------------------------


def _make_test_app(db: Session) -> FastAPI:
    """
    Build a minimal FastAPI app with all DB and auth dependencies overridden.
    Avoids importing app.main (which runs Alembic migrations at import time).
    """
    from fastapi import FastAPI
    from app.routes import data_catalog_routes, workspace_routes, llm_connection_routes
    from app.catalog import routes as catalog_routes
    from app.database import get_db, get_system_db, get_account_db, get_asset_db
    from app.dependencies import get_current_user

    app = FastAPI()

    # Override DB dependency
    def _override_get_db():
        yield db

    # Override auth dependency — return a fixed mock user
    async def _override_get_current_user():
        return {"id": 1, "email": "test@example.com", "first_name": "Test", "last_name": "User"}

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_system_db] = _override_get_db
    app.dependency_overrides[get_account_db] = _override_get_db
    app.dependency_overrides[get_asset_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    app.include_router(data_catalog_routes.router)
    app.include_router(catalog_routes.router)
    app.include_router(workspace_routes.router)
    app.include_router(llm_connection_routes.router)

    from app.agents.routes import external_connection_routes, agent_tool_routes
    from app.catalog import tool_routes as catalog_tool_routes
    from app.catalog.connections import routes as catalog_connection_routes

    app.include_router(external_connection_routes.router)
    app.include_router(catalog_tool_routes.router)
    app.include_router(agent_tool_routes.router)
    app.include_router(catalog_connection_routes.router)

    return app


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """Return a TestClient backed by the transactional test session."""
    app = _make_test_app(db_session)
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Common data factories
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_catalog_connection(db_session: Session):
    """Create and return a sample CatalogConnection."""
    from app.services.data_catalog_service import create_connection
    from app.schemas.data_catalog import ConnectionCreate

    return create_connection(
        db_session,
        ConnectionCreate(
            name="Test Connection",
            host="localhost",
            port=5432,
            username="postgres",
            password="secret123",
            default_database="testdb",
        ),
    )

