from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.compute.services.resource_service import ComputeResourceService
from compassx.models import RuntimeInfo, RuntimePhase


class _Db:
    def __init__(self, resources=None):
        self.commits = 0
        self.refreshes = 0
        self._resources = resources or []

    def commit(self):
        self.commits += 1

    def refresh(self, _resource):
        self.refreshes += 1

    def query(self, _model):
        class _Query:
            def __init__(self, items):
                self._items = items

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return self._items

            def first(self):
                return self._items[0] if self._items else None

        return _Query(self._resources)


class _RuntimeManager:
    def __init__(self, phase):
        self.phase = phase

    async def get_status(self, runtime_id):
        return RuntimeInfo(runtime_id=runtime_id, phase=self.phase)


def _resource(desired_status="running", resource_id="compute-1"):
    return SimpleNamespace(
        id=resource_id,
        name="Local compute",
        runtime="python",
        profile="local",
        user_id="user-1",
        workspace_id=None,
        created_by="user-1",
        created_at=datetime.now(timezone.utc),
        description=None,
        deployment_name=f"compute-{resource_id}",
        desired_status=desired_status,
        is_default=False,
        pod_name="old-container",
    )


def _service(db, phase):
    service = ComputeResourceService.__new__(ComputeResourceService)
    service.db = db
    service.runtime_manager = _RuntimeManager(phase)
    service._normalize_platform_runtime_driver = lambda *args, **kwargs: None
    return service


def test_missing_platform_runtime_with_running_intent_shows_pending():
    db = _Db()
    resource = _resource(desired_status="running")

    status = _service(db, RuntimePhase.MISSING)._platform_status(resource)

    assert status.phase == "Pending"
    assert status.desired_status == "running"
    assert resource.desired_status == "running"
    assert "initializing" in status.message or "pending" in status.message


def test_missing_platform_runtime_with_stopped_intent_shows_stopped():
    db = _Db()
    resource = _resource(desired_status="stopped")

    status = _service(db, RuntimePhase.MISSING)._platform_status(resource)

    assert status.phase == "Stopped"
    assert status.desired_status == "stopped"
    assert resource.desired_status == "stopped"


def test_running_platform_runtime_keeps_running_intent():
    db = _Db()
    resource = _resource(desired_status="running")

    status = _service(db, RuntimePhase.RUNNING)._platform_status(resource)

    assert status.phase == "Running"
    assert status.desired_status == "running"
    assert db.commits == 0


def test_reconcile_runtime_states_autostarts_stopped_or_missing_resources():
    resource = _resource(desired_status="running")
    db = _Db(resources=[resource])
    service = _service(db, RuntimePhase.MISSING)
    service._use_platform = lambda: True
    service.start_resource = MagicMock(return_value={"status": "Pending"})

    reconciled = service.reconcile_runtime_states()

    assert reconciled == 1
    service.start_resource.assert_called_once_with("compute-1", "user-1", None)


def test_reconcile_runtime_states_skips_already_running_resources():
    resource = _resource(desired_status="running")
    db = _Db(resources=[resource])
    service = _service(db, RuntimePhase.RUNNING)
    service._use_platform = lambda: True
    service.start_resource = MagicMock()

    reconciled = service.reconcile_runtime_states()

    assert reconciled == 0
    service.start_resource.assert_not_called()


def test_update_resource_updates_fields_and_restarts_if_running():
    from compute.schemas import ComputeProfileId, ComputeResourceUpdateRequest, RuntimeType

    resource = _resource(desired_status="running")
    db = _Db(resources=[resource])
    service = _service(db, RuntimePhase.RUNNING)
    service._get_resource_row = MagicMock(return_value=resource)
    service.stop_resource = MagicMock()
    service.start_resource = MagicMock()

    update_req = ComputeResourceUpdateRequest(
        runtime=RuntimeType.SPARK,
        profile=ComputeProfileId.CLOUD_S,
    )

    resp = service.update_resource("compute-1", update_req, "user-1")

    assert resource.runtime == "spark"
    assert resource.profile == "cloud-s"
    assert resp.runtime == "spark"
    service.stop_resource.assert_called_once_with("compute-1", "user-1", None)
    service.start_resource.assert_called_once_with("compute-1", "user-1", None)


def test_ensure_serverless_resource_returns_existing():
    resource = _resource(desired_status="running", resource_id="serverless-1")
    resource.name = "Serverless Compute"
    resource.is_default = True
    db = _Db(resources=[resource])
    service = _service(db, RuntimePhase.RUNNING)
    service._use_platform = lambda: True

    status = service.ensure_serverless_resource("user-1", None)
    assert status.id == "serverless-1"


def test_ensure_serverless_resource_creates_dedicated_for_new_notebook():
    db = _Db(resources=[])
    service = _service(db, RuntimePhase.RUNNING)
    service._use_platform = lambda: True
    created_res = _resource(desired_status="running", resource_id="nb-res-1")
    created_res.name = "Serverless - Untitled 4"
    created_res.is_default = False
    service.create_resource = MagicMock(return_value=created_res)
    service.get_resource_with_status = MagicMock(return_value=SimpleNamespace(id="nb-res-1", name="Serverless - Untitled 4", is_default=False))

    status = service.ensure_serverless_resource(
        "user-1", None, notebook_id="nb-4-uuid", notebook_name="Untitled 4"
    )

    assert status.id == "nb-res-1"
    service.create_resource.assert_called_once()
    call_args = service.create_resource.call_args
    req = call_args[0][0]
    assert req.name == "Serverless - Untitled 4"
    assert call_args[1]["is_default"] is False
    assert call_args[1]["auto_start"] is True




import pytest
import asyncio
from unittest.mock import AsyncMock
from compassx.interfaces.driver import ResourceDriver
from compassx.runtime.resource_manager import DefaultResourceManager, DriverRegistry
from compassx.runtime.repository import InMemoryRuntimeRepository, RuntimeRecord
from compassx.runtime.runtime_manager import DefaultRuntimeManager
from compassx.models import RuntimeNotFoundError, DriverUnavailableError, RuntimeSpec


class _MockDriver(ResourceDriver):
    name = "mock"

    def __init__(self):
        self.get_status_call = AsyncMock()
        self.start_runtime_call = AsyncMock()
        self.create_runtime_call = AsyncMock(return_value="infra-new")

    async def get_status(self, runtime_id):
        return await self.get_status_call(runtime_id)

    async def start_runtime(self, runtime_id):
        return await self.start_runtime_call(runtime_id)

    async def create_runtime(self, spec):
        return await self.create_runtime_call(spec)

    async def stop_runtime(self, runtime_id):
        pass

    async def delete_runtime(self, runtime_id):
        pass

    async def list_runtimes(self):
        return []

    async def exec(self, runtime_id, command):
        pass

    async def logs(self, runtime_id, tail=None):
        return ""

    async def stream_logs(self, runtime_id):
        if False:
            yield ""

    async def copy_file(self, runtime_id, src_path, dest_path, to_runtime=True):
        pass


@pytest.mark.asyncio
async def test_resource_manager_get_status_marks_missing_on_not_found():
    repo = InMemoryRuntimeRepository()
    record = RuntimeRecord(
        runtime_id="rt-1",
        runtime_type="duckdb",
        driver="mock",
        phase=RuntimePhase.RUNNING,
        infra_id="old-infra",
    )
    repo.save(record)

    mock_driver = _MockDriver()
    mock_driver.get_status_call.side_effect = RuntimeNotFoundError("Container gone")

    registry = DriverRegistry()
    registry.register("mock", lambda: mock_driver)

    rm = DefaultResourceManager(registry, repo, default_driver="mock")
    info = await rm.get_status("rt-1")

    assert info.phase == RuntimePhase.MISSING
    updated = repo.get("rt-1")
    assert updated.phase == RuntimePhase.MISSING
    assert updated.infra_id == ""


@pytest.mark.asyncio
async def test_resource_manager_start_runtime_marks_missing_on_not_found():
    repo = InMemoryRuntimeRepository()
    record = RuntimeRecord(
        runtime_id="rt-2",
        runtime_type="duckdb",
        driver="mock",
        phase=RuntimePhase.RUNNING,
        infra_id="old-infra",
    )
    repo.save(record)

    mock_driver = _MockDriver()
    mock_driver.start_runtime_call.side_effect = RuntimeNotFoundError("Container gone")

    registry = DriverRegistry()
    registry.register("mock", lambda: mock_driver)

    rm = DefaultResourceManager(registry, repo, default_driver="mock")

    with pytest.raises(RuntimeNotFoundError):
        await rm.start_runtime("rt-2")

    updated = repo.get("rt-2")
    assert updated.phase == RuntimePhase.MISSING
    assert updated.infra_id == ""


@pytest.mark.asyncio
async def test_runtime_manager_create_runtime_recovers_stale_running_state():
    repo = InMemoryRuntimeRepository()
    # Simulate stale state where repo thinks it is RUNNING but container is missing
    record = RuntimeRecord(
        runtime_id="rt-3",
        runtime_type="duckdb",
        driver="mock",
        phase=RuntimePhase.RUNNING,
        infra_id="old-infra",
    )
    repo.save(record)

    mock_driver = _MockDriver()
    mock_driver.get_status_call.side_effect = RuntimeNotFoundError("Container gone")
    mock_driver.create_runtime_call.return_value = "new-infra-123"

    registry = DriverRegistry()
    registry.register("mock", lambda: mock_driver)

    res_manager = DefaultResourceManager(registry, repo, default_driver="mock")

    builder = MagicMock()
    builder.build.return_value = RuntimeSpec(
        runtime_id="rt-3",
        runtime_type="duckdb",
        container_image="compute-duckdb:latest",
    )
    spec_builders = MagicMock()
    spec_builders.get.return_value = builder

    rt_manager = DefaultRuntimeManager(
        res_manager,
        spec_builders,
        repo,
        driver_policy=lambda _rt: "mock",
        env="local",
    )

    info = await rt_manager.create_runtime("duckdb", runtime_id="rt-3")
    assert info.phase == RuntimePhase.PENDING
    assert info.infra_id == "new-infra-123"

    updated = repo.get("rt-3")
    assert updated.infra_id == "new-infra-123"

