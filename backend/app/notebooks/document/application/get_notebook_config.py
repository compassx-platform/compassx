from fastapi import Request

from app.governance.dependencies import Guard
from app.notebooks.shared.support import _jupyter_base_url, _jupyter_ws_url


class GetNotebookConfig:
    def execute(self, request: Request, guard: Guard):
        from app.notebooks.routes.notebook_routes import NotebookServerConfig

        ctx = getattr(request.state, "workspace", None)
        return NotebookServerConfig(
            base_url=_jupyter_base_url(),
            ws_url=_jupyter_ws_url(),
            token="",
            workspace_slug=ctx.workspace_slug if ctx else "",
        )


def get_notebook_config(request, guard):
    return GetNotebookConfig().execute(request, guard)
