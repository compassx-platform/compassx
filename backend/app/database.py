import logging
from sqlalchemy import create_engine, pool, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Workspace DB auto-creation helper
# Connects to the postgres maintenance DB and issues CREATE DATABASE if the
# target workspace DB does not exist yet.  Must use AUTOCOMMIT — DDL cannot
# run inside a transaction on Postgres.
# ---------------------------------------------------------------------------

def _ensure_database_exists(db_name: str) -> None:
    """Create *db_name* on the Postgres server if it does not exist.

    Uses the *postgres* maintenance database with AUTOCOMMIT so that
    ``CREATE DATABASE`` can execute outside a transaction block.
    """
    maintenance_url = (
        f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}"
        f"@{settings.PG_HOST}:{settings.PG_PORT}/postgres"
    )
    maintenance_engine = create_engine(
        maintenance_url,
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
        poolclass=pool.NullPool,
    )
    try:
        with maintenance_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                # db_name is internal — safe to interpolate (not user input)
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Auto-created database '%s'", db_name)
            else:
                logger.debug("Database '%s' already exists", db_name)
    finally:
        maintenance_engine.dispose()


# ---------------------------------------------------------------------------
# Account (control plane) DB — compassx_account
# Stores governance, identity, catalog metadata, workspace configuration.
# ---------------------------------------------------------------------------
account_engine = None
AccountSessionLocal = None
_account_db_connection_failed = False


class AccountBase(DeclarativeBase):
    """Declarative base for all control plane tables (compassx_account DB)."""
    pass


try:
    if not settings.SKIP_DB_INIT:
        _ensure_database_exists(settings.SYSTEM_DB_NAME)
    pool_pre_ping = not settings.SKIP_DB_INIT
    account_engine = create_engine(
        settings.resolved_system_db_url,
        pool_pre_ping=pool_pre_ping,
        pool_size=settings.SYSTEM_DB_POOL_MIN,
        max_overflow=settings.SYSTEM_DB_POOL_MAX - settings.SYSTEM_DB_POOL_MIN,
        connect_args={"connect_timeout": 5},
    )
    AccountSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=account_engine)
    if not settings.SKIP_DB_INIT:
        with account_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Account (control plane) database connection successful: %s", settings.resolved_system_db_url)

        # Ensure dashboard storage lives in the account DB.
        try:
            from app.dashboards.models.dashboard import Dashboard  # noqa: WPS433
            AccountBase.metadata.create_all(bind=account_engine, tables=[Dashboard.__table__])
            logger.info("Account dashboard table verified/created")
        except Exception as _dashboard_init_err:
            logger.warning("Could not verify/create account dashboard table: %s", _dashboard_init_err)
    else:
        logger.info("Account database connection test skipped (SKIP_DB_INIT=True)")
except Exception as e:
    _account_db_connection_failed = True
    logger.critical(
        "FATAL: Account (control plane) database unavailable: %s\n"
        "  URL: %s\n"
        "  Auto-creation was attempted. Check PG_* credentials and that the "
        "PostgreSQL server is reachable.",
        e, settings.resolved_system_db_url,
    )
    raise RuntimeError(
        f"Account database unavailable ({settings.resolved_system_db_url}): {e}"
    ) from e


def get_account_db():
    """FastAPI dependency that yields a session to the account (control plane) DB."""
    db = AccountSessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_account_db_available() -> bool:
    return AccountSessionLocal is not None and not _account_db_connection_failed


# ---------------------------------------------------------------------------
# System DB — compassx_system (default DB name)
# Stores operational activity: query history, agent logs, sessions, memories.
# ---------------------------------------------------------------------------
system_engine = None
SystemSessionLocal = None
_system_db_connection_failed = False


class SystemBase(DeclarativeBase):
    """Declarative base for all system plane tables (compassx_system DB)."""
    pass


try:
    if not settings.SKIP_DB_INIT:
        _ensure_database_exists(settings.DATA_DB_NAME)
    pool_pre_ping = not settings.SKIP_DB_INIT
    system_engine = create_engine(
        settings.resolved_data_db_url,
        pool_pre_ping=pool_pre_ping,
        pool_size=settings.DATA_DB_POOL_MIN,
        max_overflow=settings.DATA_DB_POOL_MAX - settings.DATA_DB_POOL_MIN,
        connect_args={"connect_timeout": 5},
    )
    SystemSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=system_engine)
    if not settings.SKIP_DB_INIT:
        with system_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("System database connection successful: %s", settings.resolved_data_db_url)
    else:
        logger.info("System database connection test skipped (SKIP_DB_INIT=True)")
except Exception as e:
    _system_db_connection_failed = True
    logger.critical(
        "FATAL: System database unavailable: %s\n"
        "  URL: %s\n"
        "  Auto-creation was attempted. Check PG_* credentials and that the "
        "PostgreSQL server is reachable.",
        e, settings.resolved_data_db_url,
    )
    raise RuntimeError(
        f"System database unavailable ({settings.resolved_data_db_url}): {e}"
    ) from e


def get_system_db():
    """FastAPI dependency that yields a session to the system DB (compassx_system)."""
    db = SystemSessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_system_db_available() -> bool:
    return SystemSessionLocal is not None and not _system_db_connection_failed


# ---------------------------------------------------------------------------
# Asset DB — asset_manager (default DB name)
# Stores Asset Manager entities: types, instances, relationships, etc.
# ---------------------------------------------------------------------------
asset_engine = None
AssetSessionLocal = None
_asset_db_connection_failed = False


class AssetBase(DeclarativeBase):
    """Declarative base for all asset manager tables."""
    pass


try:
    if not settings.SKIP_DB_INIT:
        _ensure_database_exists(settings.ASSET_DB_NAME)
    pool_pre_ping = not settings.SKIP_DB_INIT
    asset_engine = create_engine(
        settings.resolved_asset_db_url,
        pool_pre_ping=pool_pre_ping,
        pool_size=settings.ASSET_DB_POOL_MIN,
        max_overflow=settings.ASSET_DB_POOL_MAX - settings.ASSET_DB_POOL_MIN,
        connect_args={"connect_timeout": 5},
    )
    AssetSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=asset_engine)
    if not settings.SKIP_DB_INIT:
        with asset_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Asset database connection successful: %s", settings.resolved_asset_db_url)

        # Auto-create tables in Asset DB
        # Import models to register them with metadata
        import app.asset_manager.models.asset_manager  # noqa: F401
        AssetBase.metadata.create_all(bind=asset_engine)
        logger.info("Asset manager tables verified/created in separate asset manager database")
    else:
        logger.info("Asset database connection test skipped (SKIP_DB_INIT=True)")
except Exception as e:
    _asset_db_connection_failed = True
    logger.critical(
        "FATAL: Asset database unavailable: %s\n"
        "  URL: %s\n"
        "  Auto-creation was attempted. Check PG_* credentials and that the "
        "PostgreSQL server is reachable.",
        e, settings.resolved_asset_db_url,
    )
    raise RuntimeError(
        f"Asset database unavailable ({settings.resolved_asset_db_url}): {e}"
    ) from e


def get_asset_db():
    """FastAPI dependency that yields a session to the asset database."""
    db = AssetSessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_asset_db_available() -> bool:
    return AssetSessionLocal is not None and not _asset_db_connection_failed


# ---------------------------------------------------------------------------
# Backward compatibility aliases for routes using generic get_db / SessionLocal
# (Points to the data plane: compassx_system)
# ---------------------------------------------------------------------------
get_db = get_system_db
SessionLocal = SystemSessionLocal
engine = system_engine
Base = SystemBase
is_db_available = is_system_db_available
