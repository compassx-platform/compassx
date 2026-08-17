import pytest

from compassx.models import (
    DriverUnavailableError,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeSpec,
)
from compassx.runtime import (
    DefaultResourceManager,
    DriverRegistry,
    InMemoryRuntimeRepository,
)
from compassx.tests.fakes import FakeDriver


@pytest.fixture
def setup():
    driver = FakeDriver()
    registry = DriverRegistry()
    registry.register("fake", lambda: driver)
    repo = InMemoryRuntimeRepository()
    manager = DefaultResourceManager(registry, repo, default_driver="fake")
    return manager, driver, repo


def spec(runtime_id="rt-1"):
    return RuntimeSpec(
        runtime_id=runtime_id,
        runtime_type="duckdb",
        container_image="img:latest",
        user_id="u1",
        workspace_id="ws1",
    )


def test_exposes_default_driver(setup):
    manager, _, _ = setup
    assert manager.default_driver == "fake"


async def test_create_maps_runtime_to_infra_id(setup):
    manager, driver, repo = setup
    info = await manager.create_runtime(spec())
    assert info.runtime_id == "rt-1"
    record = repo.get("rt-1")
    assert record.infra_id == "infra-rt-1"
    assert record.driver == "fake"
    assert record.phase == RuntimePhase.PENDING


async def test_create_failure_marks_failed(setup):
    manager, driver, repo = setup
    driver.fail_create = True
    with pytest.raises(RuntimeError):
        await manager.create_runtime(spec())
    assert repo.get("rt-1").phase == RuntimePhase.FAILED


async def test_status_syncs_phase(setup):
    manager, driver, repo = setup
    await manager.create_runtime(spec())
    info = await manager.get_status("rt-1")
    assert info.phase == RuntimePhase.RUNNING
    assert repo.get("rt-1").phase == RuntimePhase.RUNNING


async def test_status_missing_infra(setup):
    manager, driver, repo = setup
    await manager.create_runtime(spec())
    driver.runtimes.clear()
    driver.phases.clear()
    info = await manager.get_status("rt-1")
    assert info.phase == RuntimePhase.MISSING


async def test_stop_start_delete(setup):
    manager, driver, repo = setup
    await manager.create_runtime(spec())
    await manager.stop_runtime("rt-1")
    assert repo.get("rt-1").phase == RuntimePhase.STOPPED
    await manager.start_runtime("rt-1")
    assert driver.phases["rt-1"] == RuntimePhase.RUNNING
    await manager.delete_runtime("rt-1")
    assert repo.find("rt-1") is None
    with pytest.raises(RuntimeNotFoundError):
        await manager.get_status("rt-1")


async def test_delete_tolerates_missing_infra(setup):
    manager, driver, repo = setup
    await manager.create_runtime(spec())
    driver.runtimes.clear()
    driver.phases.clear()
    await manager.delete_runtime("rt-1")  # must not raise
    assert repo.find("rt-1") is None


async def test_unknown_driver(setup):
    manager, _, _ = setup
    with pytest.raises(DriverUnavailableError):
        await manager.create_runtime(spec(), driver_name="nope")


async def test_exec_logs_stream(setup):
    manager, _, _ = setup
    await manager.create_runtime(spec())
    result = await manager.exec("rt-1", ["echo", "hi"])
    assert result.exit_code == 0
    assert await manager.logs("rt-1") == "line1\nline2"
    lines = [line async for line in manager.stream_logs("rt-1")]
    assert lines == ["line1", "line2"]
