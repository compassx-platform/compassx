"""Tests for the publish flow (§6)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.apps.models.apps import App, AppPod, AppProductionPointer
from app.apps.services.publish_service import PublishService


@pytest.fixture
def app_id():
    return uuid.uuid4()


@pytest.fixture
def commit_id():
    return uuid.uuid4()


@pytest.fixture
def branch_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


def _make_app(app_id, user_id, workspace_id=None):
    return App(
        app_id=app_id,
        catalog_fqn="cat.schema.myapp",
        workspace_id=workspace_id or uuid.uuid4(),
        owner_id=user_id,
        name="myapp",
        versioning_backend="native",
        terminal_enabled_prod=False,
        max_concurrent_branches=5,
    )


def _make_pod(app_id, pod_kind="production", status="running"):
    return AppPod(
        pod_id=uuid.uuid4(),
        app_id=app_id,
        branch_id=None,
        pod_kind=pod_kind,
        k8s_pod_name=f"app-{app_id}-prod-abc",
        preview_url=f"/pods/app-{app_id}-prod-abc",
        terminal_enabled=False,
        status=status,
        commit_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Publish creates production pod and updates pointer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_creates_pod_and_updates_pointer(app_id, commit_id, branch_id, user_id):
    """publish() provisions a new production pod and updates the production pointer."""
    app = _make_app(app_id, user_id)
    new_pod = _make_pod(app_id, status="running")

    db = MagicMock()

    # App lookup
    def query_side(model):
        q = MagicMock()
        if model is App:
            q.filter.return_value.one_or_none.return_value = app
            q.filter.return_value.one.return_value = app
        elif model is AppPod:
            # No prior production pod
            q.filter.return_value.order_by.return_value.first.return_value = None
        elif model is AppProductionPointer:
            q.filter.return_value.one_or_none.return_value = None
        else:
            q.filter.return_value.one_or_none.return_value = None
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side
    db.add = MagicMock()
    db.flush = MagicMock()

    svc = PublishService(db)

    with (
        patch.object(svc._cred_svc, "mint_scoped_token", new=AsyncMock(return_value="token-abc")),
        patch.object(svc._pod_svc, "provision_production_pod", new=AsyncMock(return_value=new_pod)),
        patch.object(svc._pod_svc, "wait_for_ready", new=AsyncMock(return_value=True)),
        patch("app.apps.services.publish_service.get_source_control_backend") as mock_sc_factory,
    ):
        mock_sc = MagicMock()
        mock_sc.materialize = AsyncMock()
        mock_sc_factory.return_value = mock_sc

        result_pod = await svc.publish(
            app_id=app_id,
            commit_id=commit_id,
            source_branch_id=branch_id,
            switched_by=user_id,
        )

    assert result_pod is new_pod
    mock_sc.materialize.assert_awaited_once()
    # Production pointer was added
    db.add.assert_called()


@pytest.mark.asyncio
async def test_publish_aborts_on_health_check_failure(app_id, commit_id, branch_id, user_id):
    """publish() raises RuntimeError and marks pod as failed if health check fails."""
    app = _make_app(app_id, user_id)
    failed_pod = _make_pod(app_id, status="starting")

    db = MagicMock()

    def query_side(model):
        q = MagicMock()
        q.filter.return_value.one_or_none.return_value = app if model is App else None
        q.filter.return_value.one.return_value = app if model is App else None
        q.filter.return_value.order_by.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side
    db.add = MagicMock()
    db.flush = MagicMock()

    svc = PublishService(db)

    with (
        patch.object(svc._cred_svc, "mint_scoped_token", new=AsyncMock(return_value="tok")),
        patch.object(svc._pod_svc, "provision_production_pod", new=AsyncMock(return_value=failed_pod)),
        patch.object(svc._pod_svc, "wait_for_ready", new=AsyncMock(return_value=False)),
        patch("app.apps.services.publish_service.get_source_control_backend") as mock_sc_factory,
    ):
        mock_sc = MagicMock()
        mock_sc.materialize = AsyncMock()
        mock_sc_factory.return_value = mock_sc

        with pytest.raises(RuntimeError, match="health check"):
            await svc.publish(
                app_id=app_id,
                commit_id=commit_id,
                source_branch_id=branch_id,
                switched_by=user_id,
            )

    assert failed_pod.status == "failed"


@pytest.mark.asyncio
async def test_publish_schedules_prior_pod_teardown(app_id, commit_id, branch_id, user_id):
    """publish() schedules teardown of the prior production pod after grace window."""
    import asyncio
    app = _make_app(app_id, user_id)
    new_pod = _make_pod(app_id, status="running")
    prior_pod = _make_pod(app_id, status="running")

    db = MagicMock()
    pointer = AppProductionPointer(
        app_id=app_id,
        current_commit_id=uuid.uuid4(),
        source_branch_id=branch_id,
        switched_at=datetime.now(timezone.utc),
        switched_by=user_id,
    )

    def query_side(model):
        q = MagicMock()
        if model is App:
            q.filter.return_value.one_or_none.return_value = app
            q.filter.return_value.one.return_value = app
        elif model is AppPod:
            q.filter.return_value.order_by.return_value.first.return_value = prior_pod
        elif model is AppProductionPointer:
            q.filter.return_value.one_or_none.return_value = pointer
        return q

    db.query.side_effect = query_side
    db.add = MagicMock()
    db.flush = MagicMock()

    teardown_called_with = []

    async def fake_teardown_after_grace(pod_id, delay):
        teardown_called_with.append((pod_id, delay))

    svc = PublishService(db)
    svc._teardown_after_grace = fake_teardown_after_grace

    with (
        patch.object(svc._cred_svc, "mint_scoped_token", new=AsyncMock(return_value="tok")),
        patch.object(svc._pod_svc, "provision_production_pod", new=AsyncMock(return_value=new_pod)),
        patch.object(svc._pod_svc, "wait_for_ready", new=AsyncMock(return_value=True)),
        patch("app.apps.services.publish_service.get_source_control_backend") as mock_sc_factory,
        patch("asyncio.create_task") as mock_create_task,
    ):
        mock_sc = MagicMock()
        mock_sc.materialize = AsyncMock()
        mock_sc_factory.return_value = mock_sc

        await svc.publish(
            app_id=app_id,
            commit_id=commit_id,
            source_branch_id=branch_id,
            switched_by=user_id,
        )

    # asyncio.create_task should have been called for grace window teardown
    mock_create_task.assert_called_once()
