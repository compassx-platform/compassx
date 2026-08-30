"""CompassX API - FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import certifi

# Ensure SSL CA certs and CURL environment paths are set for DuckDB and libcurl in Linux containers
ca_path = certifi.where() if os.path.exists(certifi.where()) else "/etc/ssl/certs/ca-certificates.crt"
if os.path.exists(ca_path):
    os.environ.setdefault("CURL_CA_INFO", ca_path)
    os.environ.setdefault("CURL_CA_BUNDLE", ca_path)
    os.environ.setdefault("SSL_CERT_FILE", ca_path)

if os.name != "nt" and os.path.exists("/etc/ssl/certs/ca-certificates.crt"):
    os.environ.setdefault("SSL_CERT_DIR", "/etc/ssl/certs")
    try:
        os.makedirs("/etc/pki/tls/certs", exist_ok=True)
        if not os.path.exists("/etc/pki/tls/certs/ca-bundle.crt"):
            os.symlink("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

# Configure logging so INFO messages from our modules are visible in the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("app.main")

# Import all models so SQLAlchemy knows about them BEFORE importing routes
from app.data.models import data_catalog, dataset  # noqa: E402, F401
from app.catalog import models as unified_catalog_models  # noqa: E402, F401
from app.agents.models import agents as agents_models  # noqa: E402, F401
from app.compute.models import compute_resources  # noqa: E402, F401
from app.dashboards.models import dashboard  # noqa: E402, F401
from app.asset_manager.models import asset_manager as asset_manager_models  # noqa: E402, F401
from app.jobs.models import job as jobs_job_models  # noqa: E402, F401
from app.jobs.models import run_trace as jobs_run_trace_models  # noqa: E402, F401
from app.storage import db_models as storage_db_models  # noqa: E402, F401
from app.sql_warehouse import models as sql_warehouse_models  # noqa: E402, F401
from app.workspace import models as workspace_models  # noqa: E402, F401
from app.workspace import data_models as workspace_data_models  # noqa: E402, F401
from app.catalog import search_models as catalog_search_models  # noqa: E402, F401  (catalog_search_*)
from app.apps.models import apps as apps_models  # noqa: E402, F401
from app.ingestion import models as ingestion_models  # noqa: E402, F401
from app.monitoring import routes as monitoring_routes  # noqa: E402

# User Manager v1 models (registers tables with AccountBase / SystemBase)
from app.user_manager.models import account_models as _um_account_models  # noqa: E402, F401
from app.user_manager.models import system_models as _um_system_models    # noqa: E402, F401

# Now import routes
from app.data.routes import data_catalog_routes  # noqa: E402
from app.catalog import routes as catalog_routes  # noqa: E402
from app.storage import router as storage_router_module  # noqa: E402
from app.agents.routes import (  # noqa: E402
    agent_context_routes,
    agent_routes,
    chat_routes,
    db_connection_routes,
    git_connection_routes,
    llm_connection_routes,
    stream_routes,
    skill_routes,
    llm_call_routes,
    budget_routes,
    document_routes,
    artifact_routes,
    external_connection_routes,
    agent_tool_routes,
)
from app.catalog import tool_routes as catalog_tool_routes  # noqa: E402
from app.catalog.connections import routes as catalog_connection_routes  # noqa: E402
from app.dashboards.routes import dashboard_routes  # noqa: E402
from app.notebooks.routes import notebook_routes  # noqa: E402
from app.notebooks.routes import jupyter_proxy  # noqa: E402
from app.sql_warehouse import routes as sql_warehouse_routes  # noqa: E402
from app.workspace import auth_routes as workspace_auth_routes  # noqa: E402
from app.workspace import account_routes as workspace_account_routes  # noqa: E402
from app.workspace import workspace_routes as workspace_ws_routes  # noqa: E402

# User Manager v1 routes
from app.user_manager.routes import setup_routes as um_setup_routes  # noqa: E402
from app.user_manager.routes import auth_routes as um_auth_routes    # noqa: E402
from app.user_manager.routes import account_routes as um_account_routes  # noqa: E402
from app.user_manager.routes import workspace_member_routes as um_ws_member_routes  # noqa: E402
from app.user_manager.routes import invite_routes as um_invite_routes  # noqa: E402
from app.user_manager.routes import entry_point_routes as um_entry_point_routes  # noqa: E402

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan context.

    Platform infrastructure (postgres, minio, airflow, EG, ...) is managed
    by the `compassx` CLI (Platform Manager) — NOT here. The backend only:
    1. wires the platform DI container (registry, runtime manager)
    2. waits for required platform services to be healthy
    3. runs its own DB migrations / seeding / workers
    """
    # ── Platform container (DI) ──────────────────────────────────────────
    from compassx.container import PlatformContainer
    from compassx.models import HealthCheckFailedError

    container = PlatformContainer()
    app.state.platform = container
    try:
        # The backend cannot answer its own health endpoint until lifespan
        # startup completes. Waiting on itself creates a guaranteed timeout.
        required = [
            service
            for service in container.profile.required_healthy
            if service != "backend"
        ]
        if required:
            timeout = float(os.environ.get("COMPASSX_STARTUP_TIMEOUT", "60"))
            await container.health_checker.wait_until_healthy(
                required, timeout=timeout
            )
            logger.info("Platform services healthy: %s", ", ".join(required))
    except HealthCheckFailedError as exc:
        # Fail loud with root causes but keep serving so /health can report it.
        logger.error("Platform not healthy at startup:\n%s", exc)

    # Auto-run workspace migrations then first boot setup
    from app.workspace.startup import run_workspace_startup
    try:
        run_workspace_startup()
    except Exception as exc:
        logger.error("Workspace startup/migrations failed (non-fatal): %s", exc)

    # Default compute and SQL warehouse bootstrap per workspace (business concern — stays in the backend).
    async def _bootstrap_default_resources() -> None:
        try:
            from app.database import SystemSessionLocal, AccountSessionLocal, is_system_db_available, is_account_db_available
            from compute.resource_service import ComputeResourceService
            from app.compute.services.workspace_defaults import ensure_workspace_default_resources
            from compassx.runtime.repository import SqlRuntimeRepository
            from app.workspace.models import Workspace

            if is_system_db_available() and SystemSessionLocal is not None:
                def _bootstrap() -> None:
                    db = SystemSessionLocal()
                    try:
                        repository = SqlRuntimeRepository(SystemSessionLocal)
                        runtime_manager = container.build_runtime_manager(repository)
                        app.state.runtime_manager = runtime_manager
                        from app.jobs.execution_service import recover_orphaned_executions
                        recovered = recover_orphaned_executions(runtime_manager)
                        if recovered:
                            logger.warning(
                                "Recovered %s orphaned Jobs executions after restart",
                                recovered,
                            )
                        service = ComputeResourceService(db, runtime_manager=runtime_manager)
                        service.reconcile_runtime_states()

                        # Ensure defaults across all existing workspaces
                        workspaces = []
                        if is_account_db_available() and AccountSessionLocal is not None:
                            adb = AccountSessionLocal()
                            try:
                                workspaces = adb.query(Workspace).all()
                            except Exception as ws_q_err:
                                logger.debug("Could not query workspaces during resource bootstrap: %s", ws_q_err)
                            finally:
                                adb.close()

                        if workspaces:
                            for ws in workspaces:
                                ensure_workspace_default_resources(
                                    db,
                                    workspace_id=ws.id,
                                    created_by="system",
                                    user_id=ws.created_by or "default",
                                    runtime_manager=runtime_manager,
                                )
                        # Also ensure global/default scope
                        ensure_workspace_default_resources(
                            db,
                            workspace_id=None,
                            created_by="system",
                            user_id="default",
                            runtime_manager=runtime_manager,
                        )
                    finally:
                        db.close()

                await asyncio.get_event_loop().run_in_executor(None, _bootstrap)
        except Exception as exc:
            logger.error("Default resource bootstrap failed (non-fatal): %s", exc)

    asyncio.create_task(_bootstrap_default_resources())

    # ── User Manager v1: auto-create tables + seed ───────────────────────────
    try:
        from app.database import account_engine, system_engine, AccountBase, SystemBase
        from sqlalchemy import text as _text

        if account_engine is not None:
            with account_engine.connect() as _conn:
                for _enum_sql in [
                    "DO $$ BEGIN CREATE TYPE um_user_status AS ENUM ('invited','active','suspended','deactivated'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
                    "DO $$ BEGIN CREATE TYPE um_auth_provider AS ENUM ('local','sso'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
                    "DO $$ BEGIN CREATE TYPE um_principal_type AS ENUM ('user','group'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
                    "DO $$ BEGIN CREATE TYPE um_invite_target_scope AS ENUM ('account','workspace'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
                    "DO $$ BEGIN CREATE TYPE um_invite_status AS ENUM ('pending','accepted','expired','revoked'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
                ]:
                    _conn.execute(_text(_enum_sql))
                _conn.commit()
            AccountBase.metadata.create_all(bind=account_engine, checkfirst=True)
            try:
                with account_engine.connect() as _conn:
                    for _col in ["schema_id", "catalog_name", "schema_name"]:
                        try:
                            _conn.execute(_text(f"ALTER TABLE catalog_v2_connections ALTER COLUMN {_col} DROP NOT NULL;"))
                        except Exception:
                            pass
                    _is_gen = _conn.execute(_text("""
                        SELECT is_generated FROM information_schema.columns 
                        WHERE table_name = 'catalog_v2_connections' AND column_name = 'full_name'
                    """)).scalar()
                    if _is_gen and str(_is_gen).upper() in ("ALWAYS", "YES", "TRUE"):
                        _conn.execute(_text("ALTER TABLE catalog_v2_connections DROP COLUMN full_name;"))
                        _conn.execute(_text("ALTER TABLE catalog_v2_connections ADD COLUMN full_name VARCHAR(765);"))
                        _conn.execute(_text("UPDATE catalog_v2_connections SET full_name = COALESCE(catalog_name || '.' || schema_name || '.' || name, name);"))
                    
                    # Ensure current_version column exists on catalog_queries
                    _has_col = _conn.execute(_text("""
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'catalog_queries' AND column_name = 'current_version'
                    """)).scalar()
                    if not _has_col:
                        _conn.execute(_text("ALTER TABLE catalog_queries ADD COLUMN current_version INTEGER NOT NULL DEFAULT 1;"))
                        logger.info("Auto-migrated catalog_queries: added current_version column")

                    _conn.commit()
            except Exception as _conn_tbl_err:
                logger.debug("catalog schema migration check non-fatal: %s", _conn_tbl_err)
            logger.info("User Manager: account_db tables verified/created")

        if system_engine is not None:
            with system_engine.connect() as _conn:
                for _schema in ["query", "compute", "ai", "jobs"]:
                    _conn.execute(_text(f"CREATE SCHEMA IF NOT EXISTS {_schema};"))
                _conn.execute(_text(
                    "DO $$ BEGIN CREATE TYPE um_principal_type_sys AS ENUM ('user','group'); EXCEPTION WHEN duplicate_object THEN null; END $$;"
                ))
                _conn.commit()
            SystemBase.metadata.create_all(bind=system_engine, checkfirst=True)
            logger.info("User Manager: system_db tables verified/created")

        if account_engine is not None and system_engine is not None:
            from app.database import AccountSessionLocal, SystemSessionLocal
            from app.user_manager.seed import run_all_seeds
            from app.config import settings as _settings
            if _settings.SKIP_DB_INIT:
                logger.info("User Manager startup skipped (SKIP_DB_INIT=True)")
            elif AccountSessionLocal and SystemSessionLocal:
                _adb = AccountSessionLocal()
                _sdb = SystemSessionLocal()
                try:
                    run_all_seeds(_adb, _sdb)
                except Exception as _seed_err:
                    logger.warning("User Manager seed warning: %s", _seed_err)
                finally:
                    _adb.close()
                    _sdb.close()
    except Exception as _um_err:
        logger.warning("User Manager startup warning (non-fatal): %s", _um_err)

    # Start catalog embedding worker (daemon thread — exits with the process)
    try:
        from app.catalog.embedding_worker import start_embedding_worker
        from app.database import AccountSessionLocal
        from app.config import settings as _settings
        if _settings.SKIP_DB_INIT:
            logger.info("Catalog embedding worker skipped (SKIP_DB_INIT=True)")
        elif AccountSessionLocal is not None:
            start_embedding_worker(AccountSessionLocal)
        else:
            logger.warning("Account DB not available — catalog embedding worker not started")
    except Exception as _worker_err:
        logger.warning("Could not start catalog embedding worker: %s", _worker_err)

    async def _jobs_reconciliation_loop() -> None:
        from app.jobs.reconciliation import reconcile_airflow_runs
        from services.airflow.client import AirflowSchedulerGateway

        gateway = AirflowSchedulerGateway()
        app.state.scheduler_gateway = gateway
        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, reconcile_airflow_runs, gateway
                )
            except Exception:
                logger.warning("Jobs reconciliation cycle failed", exc_info=True)
            await asyncio.sleep(120)

    jobs_reconciliation_task = asyncio.create_task(_jobs_reconciliation_loop())
    try:
        yield
    finally:
        jobs_reconciliation_task.cancel()
        try:
            await jobs_reconciliation_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    lifespan=lifespan,
    title="CompassX API",
    description="CompassX Platform API",
    version="0.1.0",
    docs_url="/api/swagger/docs",
    openapi_url="/api/swagger.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace slug resolution middleware (must run after CORS)
from app.workspace.middleware import WorkspaceMiddleware  # noqa: E402
app.add_middleware(WorkspaceMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


@app.middleware("http")
async def db_error_handler(request: Request, call_next):
    """Catch database errors and return 503 Service Unavailable."""
    try:
        return await call_next(request)
    except RuntimeError as e:
        if "database not available" in str(e).lower():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Database service temporarily unavailable. This feature requires database connectivity."
                }
            )
        raise
    except OperationalError as e:
        logging.getLogger(__name__).error("Database operational error: %s", e)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database service temporarily unavailable. Please try again later."
            }
        )

app.include_router(data_catalog_routes.router)
app.include_router(catalog_routes.router)
app.include_router(storage_router_module.router)

app.include_router(llm_connection_routes.router)
app.include_router(db_connection_routes.router)
app.include_router(git_connection_routes.router)
app.include_router(agent_routes.router)
app.include_router(agent_context_routes.router)
app.include_router(skill_routes.router)
app.include_router(chat_routes.router)
app.include_router(stream_routes.router)
app.include_router(llm_call_routes.router)
app.include_router(budget_routes.router)
app.include_router(document_routes.router)
app.include_router(artifact_routes.router)
app.include_router(external_connection_routes.router)
app.include_router(catalog_tool_routes.router)
app.include_router(agent_tool_routes.router)
app.include_router(catalog_connection_routes.router)

app.include_router(notebook_routes.router)
app.include_router(jupyter_proxy.router)
app.include_router(dashboard_routes.router)
app.include_router(monitoring_routes.router)
app.include_router(sql_warehouse_routes.router)

# Workspace / account / auth routes (legacy - kept for backward compat)
app.include_router(workspace_auth_routes.router)
app.include_router(workspace_account_routes.router)
app.include_router(workspace_ws_routes.router)

# User Manager v1 routes
app.include_router(um_setup_routes.router)
app.include_router(um_auth_routes.router)
app.include_router(um_account_routes.router)
app.include_router(um_ws_member_routes.router)
app.include_router(um_invite_routes.router)
app.include_router(um_entry_point_routes.router)

# User Manager v1 routes now include the /api/um prefix directly so they
# match the rest of the API surface.

# Governance — grants, ownership, and effective-permission inspection.
from app.governance import routes as governance_routes  # noqa: E402
app.include_router(governance_routes.router)

from app.compute.routes.router import router as compute_router  # noqa: E402
app.include_router(compute_router, prefix="/api/v1/compute")

# Apps (CompassX Apps — FastAPI+React app builder)
from app.apps.routes import app_routes, branch_routes, publish_routes, file_routes  # noqa: E402
from app.apps.routes import terminal_routes, agent_routes  # noqa: E402
app.include_router(app_routes.router)
app.include_router(branch_routes.router)
app.include_router(publish_routes.router)
app.include_router(file_routes.router)
app.include_router(terminal_routes.router)
app.include_router(agent_routes.router)

from app.asset_manager.routes import (  # noqa: E402
    asset_type_routes,
    asset_instance_routes,
    asset_hierarchy_routes,
    asset_relationship_routes,
    asset_event_routes,
    asset_tag_routes,
    asset_document_routes,
    asset_import_routes,
)
app.include_router(asset_type_routes.router)
app.include_router(asset_instance_routes.router)
app.include_router(asset_hierarchy_routes.router)
app.include_router(asset_relationship_routes.router)
app.include_router(asset_event_routes.router)
app.include_router(asset_tag_routes.router)
app.include_router(asset_document_routes.router)
app.include_router(asset_import_routes.router)

from app.jobs.routes import router as jobs_router, run_router as job_runs_router, webhook_router as airflow_webhook_router  # noqa: E402
from app.jobs.execution_routes import execution_router as job_execution_router, internal_router as jobs_internal_router  # noqa: E402
app.include_router(jobs_router)
app.include_router(job_runs_router)
app.include_router(airflow_webhook_router)
app.include_router(job_execution_router)
app.include_router(jobs_internal_router)

from app.ingestion.routes import router as ingestion_router  # noqa: E402
app.include_router(ingestion_router)

from services.enterprise_gateway.router import router as eg_router  # noqa: E402
from services.airflow.router import router as airflow_router  # noqa: E402
from services.jupyter_server.router import router as js_router  # noqa: E402
app.include_router(eg_router, prefix="/api/v1/services/enterprise-gateway")
app.include_router(airflow_router, prefix="/api/v1/services/airflow")
app.include_router(js_router, prefix="/api/v1/services/jupyter-server")


@app.get("/")
def read_root():
    return {"service": "CompassX API", "status": "running"}


@app.get("/healthcheck")
def health():
    return {"status": "ok"}

