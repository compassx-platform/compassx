from typing import Optional

from fastapi import Request

from app.sandbox.service import sandbox_service


class ListSandboxes:
    def execute(self, request: Request, consumer_module: Optional[str], status: Optional[str]):
        ctx = getattr(request.state, "workspace", None)
        ws_id = str(ctx.workspace_id) if ctx else None
        return sandbox_service.list_sandboxes(
            workspace_id=ws_id,
            consumer_module=consumer_module,
            status=status,
        )


def list_sandboxes(request, consumer_module=None, status=None):
    return ListSandboxes().execute(request, consumer_module, status)
