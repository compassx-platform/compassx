from typing import Optional

from app.sandbox.models import SandboxInstance


class GetSandbox:
    def execute(self, service, sandbox_id: str) -> Optional[SandboxInstance]:
        instance = service._instances.get(sandbox_id)
        if not instance:
            all_discovered = service.list_sandboxes()
            for disc in all_discovered:
                if disc.id == sandbox_id:
                    service._instances[sandbox_id] = disc
                    instance = disc
                    break

        if instance:
            driver = service._get_driver_for_mode(instance.runtime_mode)
            instance.status = driver.get_status(instance)
            instance.endpoints = driver.get_endpoints(instance)

        return instance


def get_sandbox(service, sandbox_id):
    return GetSandbox().execute(service, sandbox_id)
