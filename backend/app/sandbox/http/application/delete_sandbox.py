from fastapi import HTTPException

from app.sandbox.service import sandbox_service


class DeleteSandbox:
    def execute(self, sandbox_id: str):
        ok = sandbox_service.terminate_sandbox(sandbox_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be terminated")
        return {"terminated": True, "sandbox_id": sandbox_id}


def delete_sandbox(sandbox_id):
    return DeleteSandbox().execute(sandbox_id)
