"""Verification test for Generic Sandbox ensure and idempotent caching."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.sandbox.models import SandboxSpec, InitScript, SandboxStatus
from app.sandbox.service import sandbox_service


def test_ensure_sandbox_idempotency():
    print("Testing ensure_sandbox idempotency & stage progress...")

    spec = SandboxSpec(
        sandbox_id="test-app-sandbox-99",
        consumer_key="app_test_app_99",
        name="App Dev - Test App 99",
        consumer_module="app",
        runtime_mode="local",
        ports=[8080],
        init_scripts=[
            InitScript(name="Verify Codebase", command="python -c \"print('Step 1: Code verified')\""),
            InitScript(name="Install Dependencies", command="python -c \"print('Step 2: Dependencies installed')\""),
            InitScript(name="Start Application", command="python -c \"print('Step 3: Server started')\""),
        ],
    )

    # 1. Cold Ensure (Provisions compute and runs sequential init scripts)
    print("Executing cold ensure_sandbox...")
    instance1 = sandbox_service.ensure_sandbox(spec)
    print(f"Cold result: ID={instance1.id}, Status={instance1.status}, Stage={instance1.progress.stage if instance1.progress else 'N/A'}")
    assert instance1.status == SandboxStatus.READY
    assert instance1.progress is not None
    assert instance1.progress.stage == "ready"
    assert instance1.progress.percent == 100

    # 2. Hot Ensure (Should return immediately with zero delay)
    print("Executing hot ensure_sandbox for same consumer_key...")
    instance2 = sandbox_service.ensure_sandbox(spec)
    print(f"Hot result: ID={instance2.id}, Status={instance2.status}, Progress Message={instance2.progress.message if instance2.progress else 'N/A'}")
    assert instance2.id == instance1.id
    assert instance2.status == SandboxStatus.READY
    assert instance2.progress.stage == "ready"

    # 3. Clean up
    print("Cleaning up test sandbox...")
    assert sandbox_service.terminate_sandbox(instance1.id) is True

    print("ALL ENSURE SANDBOX TESTS PASSED!")


if __name__ == "__main__":
    test_ensure_sandbox_idempotency()
