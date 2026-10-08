"""Verification test for Centralized Sandbox Module."""
import sys
import os

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.sandbox.models import SandboxSpec, InitScript, SandboxStatus
from app.sandbox.service import sandbox_service


def test_sandbox_lifecycle():
    print("Testing Sandbox Lifecycle...")

    # 1. Create a SandboxSpec with init scripts
    spec = SandboxSpec(
        name="test-runner",
        consumer_module="app",
        runtime_mode="local",
        env_vars={"COMPASSX_TEST": "1", "SANDBOX_VAR": "hello_world"},
        init_scripts=[
            InitScript(
                name="Echo setup",
                command="python -c \"print('Sandbox initialized successfully')\"",
            ),
        ],
    )

    # 2. Provision Sandbox
    handle = sandbox_service.provision_sandbox(spec)
    print(f"Provisioned Sandbox: ID={handle.id}, Name={handle.name}, Status={handle.status}")
    assert handle.status in (SandboxStatus.READY, SandboxStatus.RUNNING), f"Expected READY, got {handle.status}"

    # 3. Exec Command
    res = handle.exec("python -c \"import os; print('ENV:', os.environ.get('SANDBOX_VAR'))\"")
    print(f"Exec Result: code={res.exit_code}, stdout={res.stdout.strip()}, duration={res.duration_seconds}s")
    assert res.exit_code == 0
    assert "hello_world" in res.stdout

    # 4. List Sandboxes
    all_sb = sandbox_service.list_sandboxes()
    print(f"List Sandboxes count: {len(all_sb)}")
    matching = [s for s in all_sb if s.id == handle.id]
    assert len(matching) == 1, "Sandbox not found in list"

    # 5. Logs
    logs = handle.get_logs()
    print(f"Logs:\n{logs.strip()}")
    assert "Sandbox initialized successfully" in logs or "hello_world" in logs

    # 6. Suspend and Resume
    print("Testing suspend...")
    assert handle.suspend() is True
    assert handle.status == SandboxStatus.SUSPENDED

    print("Testing resume...")
    assert handle.resume() is True
    assert handle.status == SandboxStatus.RUNNING

    # 7. Terminate
    print("Testing terminate...")
    assert handle.terminate() is True
    assert handle.status == SandboxStatus.TERMINATED

    print("ALL SANDBOX TESTS PASSED!")


if __name__ == "__main__":
    test_sandbox_lifecycle()
