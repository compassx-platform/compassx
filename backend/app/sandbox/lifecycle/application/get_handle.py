from typing import Optional

from app.sandbox.interfaces import SandboxHandle


class GetHandle:
    def execute(self, service, sandbox_id: str) -> Optional[SandboxHandle]:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            return None
        driver = service._get_driver_for_mode(instance.runtime_mode)
        return SandboxHandle(instance, driver, service)


def get_handle(service, sandbox_id):
    return GetHandle().execute(service, sandbox_id)
