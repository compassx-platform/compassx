from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.documents.routes.doc_routes import _build_tree


def _page(*, page_id, parent_id=None, title="Untitled", children=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=page_id,
        workspace_id=uuid4(),
        parent_id=parent_id,
        title=title,
        type="note",
        status="draft",
        sort_order=0,
        created_by="test@example.com",
        created_at=now,
        updated_at=now,
        children=children or [],
    )


def test_build_tree_does_not_duplicate_loaded_children():
    parent_id = uuid4()
    child_id = uuid4()

    child = _page(page_id=child_id, parent_id=parent_id, title="Child")
    parent = _page(page_id=parent_id, title="Parent", children=[child])

    tree = _build_tree([parent, child])

    assert len(tree) == 1
    assert tree[0].id == parent_id
    assert [node.id for node in tree[0].children] == [child_id]


def test_build_tree_gives_each_root_an_independent_children_list():
    first_root = _page(page_id=uuid4(), title="First")
    second_root = _page(page_id=uuid4(), title="Second")

    tree = _build_tree([first_root, second_root])

    assert len(tree) == 2
    assert tree[0].children == []
    assert tree[1].children == []
    assert tree[0].children is not tree[1].children
