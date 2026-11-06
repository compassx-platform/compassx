from app.sandbox.models import SandboxStatus


class SuspendSandbox:
    def execute(self, service, sandbox_id: str) -> bool:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            return False
        driver = service._get_driver_for_mode(instance.runtime_mode)
        ok = driver.suspend(instance)
        if ok:
            instance.status = SandboxStatus.SUSPENDED
        return ok


def suspend_sandbox(service, sandbox_id):
    return SuspendSandbox().execute(service, sandbox_id)
