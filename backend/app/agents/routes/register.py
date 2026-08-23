"""Register all agent-module routers onto a FastAPI app instance.

Called once from app/main.py to keep main.py clean of per-route include_router calls.
"""
from __future__ import annotations

from fastapi import FastAPI


def register_agent_routers(app: FastAPI) -> None:
    from app.agents.routes import (
        agent_routes,
        agent_context_routes,
        chat_routes,
        db_connection_routes,
        git_connection_routes,
        llm_connection_routes,
        stream_routes,
        skill_routes,
        llm_call_routes,
        budget_routes,
        research_engine_routes,
        document_routes,
        artifact_routes,
    )
    from app.nova.routes import attachment_routes
    app.include_router(agent_routes.router)
    app.include_router(agent_context_routes.router)
    app.include_router(llm_connection_routes.router)
    app.include_router(db_connection_routes.router)
    app.include_router(git_connection_routes.router)
    app.include_router(skill_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(stream_routes.router)
    app.include_router(llm_call_routes.router)
    app.include_router(budget_routes.router)
    app.include_router(research_engine_routes.router)
    app.include_router(document_routes.router)  # Part F — document upload
    app.include_router(artifact_routes.router)  # Part G — artifact visibility
    app.include_router(attachment_routes.router) # Nova File Attachments

