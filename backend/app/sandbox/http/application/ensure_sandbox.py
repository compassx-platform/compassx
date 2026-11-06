from fastapi import Request

from app.sandbox.models import SandboxSpec
from app.sandbox.service import sandbox_service


class EnsureSandbox:
    def execute(self, request: Request, spec: SandboxSpec):
        ctx = getattr(request.state, "workspace", None)
        if not spec.workspace_id and ctx:
            spec.workspace_id = str(ctx.workspace_id)
        return sandbox_service.ensure_sandbox(spec)


def ensure_sandbox(request, spec):
    return EnsureSandbox().execute(request, spec)
