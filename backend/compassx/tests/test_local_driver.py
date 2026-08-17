import sys

import pytest

from compassx.drivers.local import LocalDriver
from compassx.models import (
    RuntimeAlreadyExistsError,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeProvisionError,
    RuntimeSpec,
)


@pytest.fixture
def driver(tmp_path):
    return LocalDriver(state_dir=tmp_path)


def spec(runtime_id="rt-local", command=None):
    return RuntimeSpec(
        runtime_id=runtime_id,
        runtime_type="python",
        command=command or [sys.executable, "-u", "-c", "print('hello from runtime')"],
    )


async def test_create_and_logs(driver):
    infra_id = await driver.create_runtime(spec())
    assert infra_id.isdigit()
    # Process prints then exits; wait for completion via status polling.
    import asyncio

    logs = ""
    for _ in range(50):
        info = await driver.get_status("rt-local")
        logs = await driver.logs("rt-local")
        if info.phase != RuntimePhase.RUNNING and "hello from runtime" in logs:
            break
        await asyncio.sleep(0.1)
    assert "hello from runtime" in logs


async def test_requires_command(driver):
    with pytest.raises(RuntimeProvisionError):
        await driver.create_runtime(RuntimeSpec(runtime_id="rt-nocmd", runtime_type="x"))


async def test_duplicate_rejected(driver):
    await driver.create_runtime(spec())
    with pytest.raises(RuntimeAlreadyExistsError):
        await driver.create_runtime(spec())


async def test_stop_long_running(driver):
    long_spec = spec(
        runtime_id="rt-long",
        command=[sys.executable, "-c", "import time; time.sleep(60)"],
    )
    await driver.create_runtime(long_spec)
    info = await driver.get_status("rt-long")
    assert info.phase == RuntimePhase.RUNNING
    await driver.stop_runtime("rt-long")
    info = await driver.get_status("rt-long")
    assert info.phase == RuntimePhase.STOPPED


async def test_delete(driver):
    await driver.create_runtime(spec())
    await driver.delete_runtime("rt-local")
    with pytest.raises(RuntimeNotFoundError):
        await driver.get_status("rt-local")


async def test_unknown_runtime(driver):
    with pytest.raises(RuntimeNotFoundError):
        await driver.get_status("ghost")


async def test_list(driver):
    await driver.create_runtime(spec("rt-1"))
    await driver.create_runtime(spec("rt-2"))
    infos = await driver.list_runtimes()
    assert sorted(i.runtime_id for i in infos) == ["rt-1", "rt-2"]
