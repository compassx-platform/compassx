"""Sandbox command port keeps a completed exec even when it prints nothing."""


def test_blank_sandbox_output_stays_on_the_sandbox(monkeypatch):
    class Inst:
        runtime_mode = "docker"

    class Result:
        stdout = ""
        stderr = ""
        success = True
        exit_code = 0

    class Driver:
        def exec_command(self, inst, command, timeout=30):
            return Result()

    class Svc:
        def find_active_sandbox(self, **kwargs):
            return Inst()

        def _get_driver_for_mode(self, mode):
            return Driver()

    import app.sandbox.service as sandbox_service_mod

    monkeypatch.setattr(sandbox_service_mod, "sandbox_service", Svc())

    def _legacy_driver():
        raise AssertionError("legacy driver should not run")

    import app.services.drivers.factory as factory_mod

    monkeypatch.setattr(
        factory_mod,
        "driver_factory",
        type("Factory", (), {"get_dev_driver": staticmethod(_legacy_driver)})(),
    )

    from app.services.studio.sandbox_commands import BuildSandboxCommands

    app = type("App", (), {"id": "app-1"})()
    result = BuildSandboxCommands().run(app, "true", timeout=1)

    assert result["success"] is True
    assert result["exit_code"] == 0
