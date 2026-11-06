"""DB Connection CRUD routes + schema introspection + connection test + data profiling."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request

from sqlalchemy.orm import Session

from app.agents.routes._authz import (
    authorized_agent,
    authorized_connection,
    visible_connections,
)

from app.database import get_system_db as get_db, get_account_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

from app.models.agents import DBConnection, AgentDBConnection, DataSourceProfile

from app.schemas.agents import (
    DBConnectionCreate,
    DBConnectionResponse,
    DBConnectionUpdate,
    PingResponse,
    SchemaIntrospectionResponse,
    DataSourceProfileResponse,
)

from app.services.db_introspector import build_engine, get_schema, test_connection

from app.services.encryption import encrypt_field

logger = logging.getLogger("app.agents.routes.db_connection_routes")

def _to_response(conn: DBConnection) -> DBConnectionResponse:
    return DBConnectionResponse(
        id=conn.id,
        name=conn.name,
        db_type=conn.db_type,
        host=conn.host,
        port=conn.port,
        db_name=conn.db_name,
        ssl_config=conn.ssl_config or {},
        profiler_agent_id=conn.profiler_agent_id,
        scoped_tables=conn.scoped_tables or [],
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )

def sync_agent_db_connection(connection_id: int, agent_id: int | None, scoped_tables: list[str], db: Session):
    # Remove existing mappings for this connection
    db.query(AgentDBConnection).filter(
        AgentDBConnection.db_connection_id == connection_id
    ).delete()
    
    if agent_id:
        # Create new mapping
        mapping = AgentDBConnection(
            agent_id=agent_id,
            db_connection_id=connection_id,
            allowed_tables=scoped_tables
        )
        db.add(mapping)
    db.commit()

def trigger_profiling(
    conn: DBConnection,
    user_id: str,
    workspace_id: str,
    background_tasks: BackgroundTasks,
    catalog_scope: dict | None = None,
):
    if not conn.profiler_agent_id:
        return
    
    async def run_profiling():
        from app.database import SessionLocal
        from app.agents.services.agent.orchestrator import orchestrate_stream
        from app.models.agents import ChatSession
        
        bg_db = SessionLocal()
        try:
            # Create chat session
            session = ChatSession(
                agent_id=conn.profiler_agent_id,
                title=f"Auto Profiling DB Conn {conn.id}"
            )
            bg_db.add(session)
            bg_db.commit()
            
            scope_instruction = ""
            if catalog_scope:
                scope_instruction = (
                    f" The catalog-selected scope is {catalog_scope!r}. Profile only this scope. "
                    "Use its table_name as the physical table when supplied. Every save_data_profile call "
                    "must include exactly this catalog identity. For catalog or schema scope, profile every "
                    "table inside it and save one aggregate profile for the selected scope."
                )
            prompt = (
                f"Please run a full data profiling pass on database connection ID {conn.id}.{scope_instruction} "
                "Follow the four-pass methodology: Structural Inventory, Relationship Inference, "
                "Semantic Classification, and Prior-Art Discovery. For each table, perform get_table_schema, "
                "get_column_stats, check_value_overlap, search_workspace, and then compile and save_data_profile."
            )
            
            async for event in orchestrate_stream(
                session_id=session.id,
                user_content=prompt,
                db=bg_db,
                user_id=user_id,
                workspace_id=workspace_id
            ):
                pass
        except Exception as e:
            logger.exception("Error during background profiling execution")
        finally:
            bg_db.close()
 
    background_tasks.add_task(run_profiling)

def _get_or_404(db: Session, connection_id: int, guard: Guard, privilege: Privilege) -> DBConnection:
    """Load a connection the caller holds ``privilege`` on.

    The workspace comes from the guard. The previous version fell back to
    ``workspace_id == None`` when none was resolved, so an unscoped request
    reached the workspace-less connections rather than being refused.
    """
    return authorized_connection(db, guard, DBConnection, connection_id, privilege)

import app.agents.http.db_connections.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.db_connections.application.list_db_connections import list_db_connections as list_db_connections_action
from app.agents.http.db_connections.application.create_db_connection import create_db_connection as create_db_connection_action
from app.agents.http.db_connections.application.get_db_connection import get_db_connection as get_db_connection_action
from app.agents.http.db_connections.application.update_db_connection import update_db_connection as update_db_connection_action
from app.agents.http.db_connections.application.delete_db_connection import delete_db_connection as delete_db_connection_action
from app.agents.http.db_connections.application.test_db_connection import test_db_connection as test_db_connection_action
from app.agents.http.db_connections.application.introspect_schema import introspect_schema as introspect_schema_action
from app.agents.http.db_connections.application.reprofile_db_connection import reprofile_db_connection as reprofile_db_connection_action
from app.agents.http.db_connections.application.get_db_connection_profiles import get_db_connection_profiles as get_db_connection_profiles_action

logger = logging.getLogger("app.agents.routes.db_connection_routes")

router = APIRouter(prefix="/api/v1/db-connections", tags=["DB Connections"])

@router.get("", response_model=list[DBConnectionResponse])
def list_db_connections(
    request: Request,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the database connections the caller may see.

    The response carries host, port, and database name but never the stored
    credentials, which are encrypted at rest and only decrypted when a query
    is actually run.
    """
    return list_db_connections_action(request=request, db=db, guard=guard)

@router.post("", response_model=DBConnectionResponse, status_code=201)
def create_db_connection(
    request: Request,
    body: DBConnectionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a database connection.

    Storing credentials that anyone granted USE_COMPUTE can then query through
    is an administrative act, so it sits with the workspace admin. The creator
    becomes the owner and can delegate from there.
    """
    return create_db_connection_action(request=request, body=body, background_tasks=background_tasks, db=db, sys_db=sys_db, guard=guard)

@router.get("/{connection_id}", response_model=DBConnectionResponse)
def get_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    return get_db_connection_action(request=request, connection_id=connection_id, db=db, guard=guard)

@router.put("/{connection_id}", response_model=DBConnectionResponse)
def update_db_connection(
    request: Request,
    connection_id: int,
    body: DBConnectionUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a connection's target or credentials.

    EDIT, because this rewrites where the connection points and what it
    authenticates as: everyone already granted USE_COMPUTE on it keeps their
    grant and silently starts querying the new target.
    """
    return update_db_connection_action(request=request, connection_id=connection_id, body=body, background_tasks=background_tasks, db=db, sys_db=sys_db, guard=guard)

@router.delete("/{connection_id}", status_code=204)
def delete_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Remove a connection.

    MANAGE: it takes away access for everyone granted on it, and the stored
    credentials go with it.
    """
    return delete_db_connection_action(request=request, connection_id=connection_id, db=db, sys_db=sys_db, guard=guard)

@router.post("/{connection_id}/test", response_model=PingResponse)
def test_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Open the connection and report whether it works.

    USE_COMPUTE, not BROWSE: this decrypts the stored credentials and makes a
    real connection to the remote database on the caller's behalf.
    """
    return test_db_connection_action(request=request, connection_id=connection_id, db=db, guard=guard)

@router.get("/{connection_id}/schema", response_model=SchemaIntrospectionResponse)
def introspect_schema(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """List the tables and columns of the remote database.

    USE_COMPUTE: the response is content read out of the remote system, not
    metadata CompassX holds about the connection.
    """
    return introspect_schema_action(request=request, connection_id=connection_id, db=db, guard=guard)

@router.post("/{connection_id}/reprofile")
def reprofile_db_connection(
    request: Request,
    connection_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    sys_db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Re-run the profiler agent against this connection.

    Two privileges, because the run touches two securables: USE_COMPUTE to
    read through the connection, and EXECUTE on the configured agent, which is
    what actually does the reading.
    """
    return reprofile_db_connection_action(request=request, connection_id=connection_id, background_tasks=background_tasks, db=db, sys_db=sys_db, guard=guard)

@router.get("/{connection_id}/profiles", response_model=list[DataSourceProfileResponse])
def get_db_connection_profiles(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Return the stored profiles for a connection.

    BROWSE: these are CompassX's own notes about the source — column stats and
    inferred relationships — not a live read of it.
    """
    return get_db_connection_profiles_action(request=request, connection_id=connection_id, db=db, sys_db=sys_db, guard=guard)
