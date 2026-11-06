from app.sandbox.models import SandboxStatus


class ResumeSandbox:
    def execute(self, service, sandbox_id: str) -> bool:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            return False
        driver = service._get_driver_for_mode(instance.runtime_mode)
        ok = driver.resume(instance)
        if ok:
            instance.status = SandboxStatus.RUNNING
        return ok


def resume_sandbox(service, sandbox_id):
    return ResumeSandbox().execute(service, sandbox_id)
