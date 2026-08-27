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
    service._normalize_platform_runtime_driver = lambda _runtime_id: None
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
