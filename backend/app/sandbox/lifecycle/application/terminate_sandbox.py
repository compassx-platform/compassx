from app.sandbox.models import SandboxStatus


class TerminateSandbox:
    def execute(self, service, sandbox_id: str) -> bool:
        instance = service.get_sandbox(sandbox_id)
        if not instance:
            instance = service.find_active_sandbox(sandbox_id=sandbox_id, consumer_key=sandbox_id)
        if not instance:
            service._instances.pop(sandbox_id, None)
            return True
        driver = service._get_driver_for_mode(instance.runtime_mode)
        ok = driver.terminate(instance)
        instance.status = SandboxStatus.TERMINATED
        service._instances.pop(sandbox_id, None)
        service._instances.pop(instance.id, None)
        return ok


def terminate_sandbox(service, sandbox_id):
    return TerminateSandbox().execute(service, sandbox_id)
