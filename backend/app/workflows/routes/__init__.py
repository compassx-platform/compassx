from app.workflows.routes.workflow_routes import router as workflow_router
from app.workflows.routes.entity_routes import router as entity_router
from app.workflows.routes.proxy_routes import router as proxy_router

__all__ = ["workflow_router", "entity_router", "proxy_router"]
