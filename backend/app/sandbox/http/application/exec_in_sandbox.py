from app.sandbox.service import sandbox_service


class ExecInSandbox:
    def execute(self, sandbox_id: str, body):
        return sandbox_service.exec_in_sandbox(
            sandbox_id=sandbox_id,
            command=body.command,
            working_dir=body.working_dir,
            env=body.env,
            timeout=body.timeout,
        )


def exec_in_sandbox(sandbox_id, body):
    return ExecInSandbox().execute(sandbox_id, body)
