class GetSandboxLogs:
    def execute(self, service, sandbox_id: str, max_lines: int = 200) -> str:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            return f"[Sandbox '{sandbox_id}' not found]"
        driver = service._get_driver_for_mode(instance.runtime_mode)
        return driver.get_logs(instance, max_lines=max_lines)


def get_sandbox_logs(service, sandbox_id, max_lines=200):
    return GetSandboxLogs().execute(service, sandbox_id, max_lines)
