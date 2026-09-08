import pytest

from compassx.models import RuntimeAlreadyExistsError, RuntimePhase, RuntimeProvisionError
from compassx.runtime import (
    DefaultResourceManager,
    DefaultRuntimeManager,
    DriverRegistry,
    InMemoryRuntimeRepository,
    default_spec_builders,
)
from compassx.tests.fakes import FakeDriver


@pytest.fixture
def setup():
    driver = FakeDriver()
    registry = DriverRegistry()
    registry.register("fake", lambda: driver)
    repo = InMemoryRuntimeRepository()
    resources = DefaultResourceManager(registry, repo, default_driver="fake")
    manager = DefaultRuntimeManager(
        resources,
        default_spec_builders(),
        repo,
        driver_policy=lambda runtime_type: "fake",
        namespace="test-ns",
        env="local",
    )
    return manager, driver, repo


def test_exposes_resource_manager(setup):
    manager, _, _ = setup
    assert manager.resource_manager.default_driver == "fake"


from compassx.runtime.spec_builders import DUCKDB_IMAGE


async def test_create_generates_runtime_id(setup):
    manager, driver, _ = setup
    info = await manager.create_runtime("duckdb", user_id="u1")
    assert info.runtime_id.startswith("runtime-")
    spec = driver.runtimes[info.runtime_id]
    assert spec.container_image == DUCKDB_IMAGE
    assert spec.command == ["tail", "-f", "/dev/null"]
    assert spec.namespace == "test-ns"


async def test_create_duplicate_rejected(setup):
    manager, _, _ = setup
    await manager.create_runtime("duckdb", runtime_id="rt-x")
    with pytest.raises(RuntimeAlreadyExistsError):
        await manager.create_runtime("duckdb", runtime_id="rt-x")


async def test_unknown_runtime_type(setup):
    manager, _, _ = setup
    with pytest.raises(RuntimeProvisionError):
        await manager.create_runtime("cobol")


async def test_duckdb_profile_validation(setup):
    manager, _, _ = setup
    with pytest.raises(RuntimeProvisionError):
        await manager.create_runtime("duckdb", options={"profile_id": "gpu"})


async def test_spark_spec_fields(setup):
    manager, driver, _ = setup
    info = await manager.create_runtime(
        "spark",
        options={
            "profile_id": "cloud-s",
            "requests": {"cpu": "1", "memory": "1Gi"},
            "limits": {"cpu": "1", "memory": "4Gi"},
            "extra_env": {"FOO": "bar"},
        },
        user_id="u1",
    )
    spec = driver.runtimes[info.runtime_id]
    assert spec.env["SPARK_MODE"] == "master"
    assert spec.env["FOO"] == "bar"
    assert spec.env["AWS_ENDPOINT_URL"].startswith("http://")
    assert spec.resources.memory_limit == "4Gi"
    assert spec.labels["compassx/resource"] == info.runtime_id
    assert spec.annotations["compassx/profile"] == "cloud-s"


async def test_suspend_resume(setup):
    manager, driver, repo = setup
    info = await manager.create_runtime("duckdb", runtime_id="rt-s")
    await manager.suspend_runtime("rt-s")
    assert repo.get("rt-s").phase == RuntimePhase.SUSPENDED
    await manager.resume_runtime("rt-s")
    assert driver.phases["rt-s"] == RuntimePhase.RUNNING


async def test_list_filters_by_user(setup):
    manager, _, _ = setup
    await manager.create_runtime("duckdb", runtime_id="rt-a", user_id="alice")
    await manager.create_runtime("duckdb", runtime_id="rt-b", user_id="bob")
    infos = await manager.list_runtimes(user_id="alice")
    assert [i.runtime_id for i in infos] == ["rt-a"]


async def test_metadata(setup):
    manager, _, _ = setup
    await manager.create_runtime(
        "ray", runtime_id="rt-m", user_id="u1", workspace_id="ws9"
    )
    meta = await manager.get_metadata("rt-m")
    assert meta["runtime_type"] == "ray"
    assert meta["driver"] == "fake"
    assert meta["workspace_id"] == "ws9"


async def test_recreate_after_stop_allowed(setup):
    manager, driver, repo = setup
    await manager.create_runtime("duckdb", runtime_id="rt-r")
    await manager.stop_runtime("rt-r")
    driver.runtimes.clear()
    driver.phases.clear()
    info = await manager.create_runtime("duckdb", runtime_id="rt-r")
    assert info.runtime_id == "rt-r"
