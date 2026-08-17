from datetime import datetime, timezone
from types import SimpleNamespace

from app.compute.services.resource_service import ComputeResourceService
from compassx.models import RuntimeInfo, RuntimePhase


class _Db:
    def __init__(self):
        self.commits = 0
        self.refreshes = 0

    def commit(self):
        self.commits += 1

    def refresh(self, _resource):
        self.refreshes += 1


class _RuntimeManager:
    def __init__(self, phase):
        self.phase = phase

    async def get_status(self, runtime_id):
        return RuntimeInfo(runtime_id=runtime_id, phase=self.phase)


def _resource(desired_status="running"):
    return SimpleNamespace(
        id="compute-1",
        name="Local compute",
        runtime="python",
        profile="local",
        user_id="user-1",
        workspace_id=None,
        created_by="user-1",
        created_at=datetime.now(timezone.utc),
        description=None,
        deployment_name="compute-compute-1",
        desired_status=desired_status,
        is_default=False,
        pod_name="old-container",
    )


def _service(db, phase):
    service = ComputeResourceService.__new__(ComputeResourceService)
    service.db = db
    service.runtime_manager = _RuntimeManager(phase)
    service._normalize_platform_runtime_driver = lambda _runtime_id: None
    return service


def test_missing_platform_runtime_is_persisted_as_stopped():
    db = _Db()
    resource = _resource()

    status = _service(db, RuntimePhase.MISSING)._platform_status(resource)

    assert status.phase == "Stopped"
    assert status.desired_status == "stopped"
    assert resource.desired_status == "stopped"
    assert resource.pod_name is None
    assert db.commits == 1
    assert "recreate" in status.message


def test_running_platform_runtime_keeps_running_intent():
    db = _Db()
    resource = _resource()

    status = _service(db, RuntimePhase.RUNNING)._platform_status(resource)

    assert status.phase == "Running"
    assert status.desired_status == "running"
    assert db.commits == 0
