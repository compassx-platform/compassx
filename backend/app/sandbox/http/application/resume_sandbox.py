from fastapi import HTTPException

from app.sandbox.service import sandbox_service


class ResumeSandbox:
    def execute(self, sandbox_id: str):
        ok = sandbox_service.resume_sandbox(sandbox_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be resumed")
        return {"resumed": True, "sandbox_id": sandbox_id}


def resume_sandbox(sandbox_id):
    return ResumeSandbox().execute(sandbox_id)
