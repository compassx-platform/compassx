from fastapi import HTTPException

from app.sandbox.service import sandbox_service


class SuspendSandbox:
    def execute(self, sandbox_id: str):
        ok = sandbox_service.suspend_sandbox(sandbox_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be suspended")
        return {"suspended": True, "sandbox_id": sandbox_id}


def suspend_sandbox(sandbox_id):
    return SuspendSandbox().execute(sandbox_id)
