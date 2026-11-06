from fastapi import HTTPException

from app.sandbox.service import sandbox_service


class GetSandbox:
    def execute(self, sandbox_id: str):
        instance = sandbox_service.get_sandbox(sandbox_id)
        if not instance:
            raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found")
        return instance


def get_sandbox(sandbox_id):
    return GetSandbox().execute(sandbox_id)
