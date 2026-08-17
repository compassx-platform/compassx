"""Tests for branch cap enforcement (§5)."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.apps.models.apps import App, AppBranch
from app.apps.services.pod_service import PodService


@pytest.fixture
def app_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


def _make_mock_db(app: App, branch_count: int, user_id: uuid.UUID, app_id: uuid.UUID) -> MagicMock:
    db = MagicMock()

    # db.query(App).filter(...).one_or_none() → app
    app_query = MagicMock()
    app_query.filter.return_value.one_or_none.return_value = app
    app_query.filter.return_value.one.return_value = app

    # db.query(AppBranch).filter(...).count() → branch_count
    branch_query = MagicMock()
    branch_query.filter.return_value.count.return_value = branch_count

    def query_side_effect(model):
        if model is App:
            return app_query
        if model is AppBranch:
            return branch_query
        return MagicMock()

    db.query.side_effect = query_side_effect
    return db


def test_branch_cap_not_reached_succeeds(app_id, user_id):
    """Creating branches below cap should not raise."""
    app = App(
        app_id=app_id,
        catalog_fqn="cat.schema.myapp",
        workspace_id=uuid.uuid4(),
        owner_id=user_id,
        name="myapp",
        versioning_backend="native",
        max_concurrent_branches=5,
    )
    db = _make_mock_db(app=app, branch_count=4, user_id=user_id, app_id=app_id)

    svc = PodService(db)
    # Should not raise
    svc.check_branch_cap(app_id=app_id, user_id=user_id)


def test_branch_cap_exactly_at_limit_raises(app_id, user_id):
    """Creating a branch when count == max_concurrent_branches must raise ValueError."""
    app = App(
        app_id=app_id,
        catalog_fqn="cat.schema.myapp",
        workspace_id=uuid.uuid4(),
        owner_id=user_id,
        name="myapp",
        versioning_backend="native",
        max_concurrent_branches=5,
    )
    db = _make_mock_db(app=app, branch_count=5, user_id=user_id, app_id=app_id)

    svc = PodService(db)
    with pytest.raises(ValueError, match="Branch cap reached"):
        svc.check_branch_cap(app_id=app_id, user_id=user_id)


def test_branch_cap_above_limit_raises(app_id, user_id):
    """Creating a branch when count > max_concurrent_branches must raise ValueError."""
    app = App(
        app_id=app_id,
        catalog_fqn="cat.schema.myapp",
        workspace_id=uuid.uuid4(),
        owner_id=user_id,
        name="myapp",
        versioning_backend="native",
        max_concurrent_branches=3,
    )
    db = _make_mock_db(app=app, branch_count=3, user_id=user_id, app_id=app_id)

    svc = PodService(db)
    with pytest.raises(ValueError):
        svc.check_branch_cap(app_id=app_id, user_id=user_id)


def test_branch_cap_error_message_is_clear(app_id, user_id):
    """Error message should mention the cap limit."""
    app = App(
        app_id=app_id,
        catalog_fqn="cat.schema.myapp",
        workspace_id=uuid.uuid4(),
        owner_id=user_id,
        name="myapp",
        versioning_backend="native",
        max_concurrent_branches=2,
    )
    db = _make_mock_db(app=app, branch_count=2, user_id=user_id, app_id=app_id)

    svc = PodService(db)
    with pytest.raises(ValueError) as exc_info:
        svc.check_branch_cap(app_id=app_id, user_id=user_id)

    assert "2" in str(exc_info.value)   # mentions the limit
    assert "branch" in str(exc_info.value).lower()


def test_app_not_found_raises(app_id, user_id):
    """If the app does not exist, check_branch_cap raises ValueError."""
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None

    svc = PodService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.check_branch_cap(app_id=app_id, user_id=user_id)
