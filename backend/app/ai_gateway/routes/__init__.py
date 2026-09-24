"""AI Gateway Route Exports."""

from app.ai_gateway.routes.provider_routes import router as provider_router
from app.ai_gateway.routes.mcp_routes import router as mcp_router
from app.ai_gateway.routes.proxy_routes import router as proxy_router
from app.ai_gateway.routes.log_routes import router as log_router

__all__ = [
    "provider_router",
    "mcp_router",
    "proxy_router",
    "log_router",
]
