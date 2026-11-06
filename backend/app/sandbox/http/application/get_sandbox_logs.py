from app.sandbox.service import sandbox_service


class GetSandboxLogs:
    def execute(self, sandbox_id: str, max_lines: int):
        logs = sandbox_service.get_sandbox_logs(sandbox_id, max_lines=max_lines)
        return {"sandbox_id": sandbox_id, "logs": logs}


def get_sandbox_logs(sandbox_id, max_lines):
    return GetSandboxLogs().execute(sandbox_id, max_lines)
