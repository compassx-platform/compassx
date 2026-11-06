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
