"""DB Connection CRUD routes + schema introspection + connection test + data profiling."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.database import get_system_db as get_db, get_account_db
from app.dependencies import get_current_user
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/db-connections", tags=["DB Connections"])


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


@router.get("", response_model=list[DBConnectionResponse])
def list_db_connections(request: Request, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(DBConnection)
    if workspace_id:
        query = query.filter(DBConnection.workspace_id == workspace_id)
    else:
        query = query.filter(DBConnection.workspace_id == None)
    return [_to_response(r) for r in query.order_by(DBConnection.name).all()]


@router.post("", response_model=DBConnectionResponse, status_code=201)
def create_db_connection(
    request: Request,
    body: DBConnectionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = DBConnection(
        workspace_id=workspace_id,
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        db_name=body.db_name,
        username_enc=encrypt_field(body.username) if body.username else None,
        password_enc=encrypt_field(body.password) if body.password else None,
        ssl_config=body.ssl_config,
        profiler_agent_id=body.profiler_agent_id,
        scoped_tables=body.scoped_tables,
    )
    sys_db.add(conn)
    sys_db.commit()
    sys_db.refresh(conn)
    
    # Sync AgentDBConnection
    sync_agent_db_connection(conn.id, conn.profiler_agent_id, conn.scoped_tables, db)
    
    # Trigger profiling run
    if conn.profiler_agent_id:
        user_id = current_user.get("id") or current_user.get("sub") or "default_user"
        w_id = workspace_id or "default"
        trigger_profiling(conn, user_id, w_id, background_tasks)
        
    return _to_response(conn)


@router.get("/{connection_id}", response_model=DBConnectionResponse)
def get_db_connection(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return _to_response(_get_or_404(db, connection_id, workspace_id))


@router.put("/{connection_id}", response_model=DBConnectionResponse)
def update_db_connection(
    request: Request,
    connection_id: int,
    body: DBConnectionUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(sys_db, connection_id, workspace_id)
    old_profiler_id = conn.profiler_agent_id
    
    data = body.model_dump(exclude_none=True)
    if "username" in data:
        conn.username_enc = encrypt_field(data.pop("username"))
    if "password" in data:
        conn.password_enc = encrypt_field(data.pop("password"))
    for field, value in data.items():
        setattr(conn, field, value)
    
    sys_db.commit()
    sys_db.refresh(conn)
    
    # Sync AgentDBConnection
    sync_agent_db_connection(conn.id, conn.profiler_agent_id, conn.scoped_tables or [], db)
    
    # Trigger profiling if profiler_agent_id changed/updated
    if conn.profiler_agent_id and conn.profiler_agent_id != old_profiler_id:
        user_id = current_user.get("id") or current_user.get("sub") or "default_user"
        w_id = workspace_id or "default"
        trigger_profiling(conn, user_id, w_id, background_tasks)
        
    return _to_response(conn)


@router.delete("/{connection_id}", status_code=204)
def delete_db_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db)
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(sys_db, connection_id, workspace_id)
    sys_db.delete(conn)
    sys_db.commit()
    sync_agent_db_connection(connection_id, None, [], db)


@router.post("/{connection_id}/test", response_model=PingResponse)
def test_db_connection(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    success, message = test_connection(_get_or_404(db, connection_id, workspace_id))
    return PingResponse(success=success, message=message)


@router.get("/{connection_id}/schema", response_model=SchemaIntrospectionResponse)
def introspect_schema(request: Request, connection_id: int, db: Session = Depends(get_account_db)):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(db, connection_id, workspace_id)
    try:
        tables = get_schema(build_engine(conn))
    except Exception as exc:
        raise HTTPException(400, f"Schema introspection failed: {exc}")
    return SchemaIntrospectionResponse(tables=tables)


@router.post("/{connection_id}/reprofile")
def reprofile_db_connection(
    request: Request,
    connection_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    current_user: dict = Depends(get_current_user),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    conn = _get_or_404(db, connection_id, workspace_id)
    if not conn.profiler_agent_id:
        raise HTTPException(400, "No profiler agent configured for this connection")
        
    user_id = current_user.get("id") or current_user.get("sub") or "default_user"
    w_id = workspace_id or "default"
    trigger_profiling(conn, user_id, w_id, background_tasks)
    return {"status": "queued", "message": "Data profiling run started in the background."}


@router.get("/{connection_id}/profiles", response_model=list[DataSourceProfileResponse])
def get_db_connection_profiles(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    # check exists and workspace boundary
    _get_or_404(sys_db, connection_id, workspace_id)
    profiles = db.query(DataSourceProfile).filter(DataSourceProfile.connection_id == connection_id).all()
    return [DataSourceProfileResponse.model_validate(p) for p in profiles]


def _get_or_404(db: Session, connection_id: int, workspace_id: str | None = None) -> DBConnection:
    query = db.query(DBConnection).filter(DBConnection.id == connection_id)
    if workspace_id:
        query = query.filter(DBConnection.workspace_id == workspace_id)
    else:
        query = query.filter(DBConnection.workspace_id == None)
    conn = query.first()
    if not conn:
        raise HTTPException(404, "DB connection not found")
    return conn
