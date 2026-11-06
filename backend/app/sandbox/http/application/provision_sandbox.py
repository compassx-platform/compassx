from fastapi import Request

from app.sandbox.models import SandboxSpec
from app.sandbox.service import sandbox_service


class ProvisionSandbox:
    def execute(self, request: Request, spec: SandboxSpec):
        ctx = getattr(request.state, "workspace", None)
        if not spec.workspace_id and ctx:
            spec.workspace_id = str(ctx.workspace_id)
        handle = sandbox_service.provision_sandbox(spec)
        return handle.instance


def provision_sandbox(request, spec):
    return ProvisionSandbox().execute(request, spec)
