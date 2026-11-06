from typing import AsyncGenerator


class StreamSandboxLogs:
    async def execute(self, service, sandbox_id: str, tail_lines: int = 100) -> AsyncGenerator[str, None]:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            yield f"[Sandbox '{sandbox_id}' not found]\n"
            return
        driver = service._get_driver_for_mode(instance.runtime_mode)
        async for line in driver.stream_logs(instance, tail_lines=tail_lines):
            yield line


def stream_sandbox_logs(service, sandbox_id, tail_lines=100):
    return StreamSandboxLogs().execute(service, sandbox_id, tail_lines)
