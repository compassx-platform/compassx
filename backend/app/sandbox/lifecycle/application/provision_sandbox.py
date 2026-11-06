from app.sandbox.interfaces import SandboxHandle
from app.sandbox.models import SandboxSpec


class ProvisionSandbox:
    def execute(self, service, spec: SandboxSpec) -> SandboxHandle:
        instance = service.ensure_sandbox(spec)
        driver = service._get_driver_for_mode(instance.runtime_mode)
        return SandboxHandle(instance, driver, service)


def provision_sandbox(service, spec):
    return ProvisionSandbox().execute(service, spec)
