from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from app.sql_warehouse.models import SqlDraftQuery
from app.sql_warehouse.routes import create_draft, delete_draft, list_drafts, update_draft
from app.sql_warehouse.schemas import SqlDraftCreate, SqlDraftUpdate


def _mock_request(workspace_id: str | None = None, principal_id: str | None = None) -> Request:
    request = MagicMock(spec=Request)
    if workspace_id:
        class MockWorkspaceContext:
            def __init__(self, ws_id, p_id):
                self.workspace_id = ws_id
                self.principal_id = p_id
        request.state.workspace = MockWorkspaceContext(workspace_id, principal_id)
    else:
        request.state.workspace = None
    request.headers = {}
    request.query_params = {}
    return request


def test_draft_query_crud_and_scoping(db_session: Session):
    user1 = "user-1-" + str(uuid4())
    user2 = "user-2-" + str(uuid4())
    ws1 = "ws-1-" + str(uuid4())
    ws2 = "ws-2-" + str(uuid4())

    req_u1_w1 = _mock_request(workspace_id=ws1, principal_id=user1)
    req_u2_w1 = _mock_request(workspace_id=ws1, principal_id=user2)
    req_u1_w2 = _mock_request(workspace_id=ws2, principal_id=user1)

    # 1. Create first draft with default name
    d1 = create_draft(
        request=req_u1_w1,
        req=SqlDraftCreate(sql_text="SELECT 1;", catalog="main", schema_name="public"),
        db=db_session,
        user={"id": user1},
    )
    assert d1.id is not None
    assert d1.name == "Query 1"
    assert d1.sql_text == "SELECT 1;"
    assert d1.user_id == user1
    assert d1.workspace_id == ws1

    # 2. Create second draft with custom name
    d2 = create_draft(
        request=req_u1_w1,
        req=SqlDraftCreate(name="Monthly Report", sql_text="SELECT * FROM revenue;", catalog="analytics", schema_name="finance"),
        db=db_session,
        user={"id": user1},
    )
    assert d2.name == "Monthly Report"
    assert d2.sql_text == "SELECT * FROM revenue;"

    # 3. Create a third draft without name (should be Query 3)
    d3 = create_draft(
        request=req_u1_w1,
        req=SqlDraftCreate(sql_text="SELECT count(*) FROM users;"),
        db=db_session,
        user={"id": user1},
    )
    assert d3.name == "Query 3"

    # 4. Create a draft for User 2 in WS 1
    d_u2 = create_draft(
        request=req_u2_w1,
        req=SqlDraftCreate(sql_text="SELECT 'user2 query';"),
        db=db_session,
        user={"id": user2},
    )
    assert d_u2.user_id == user2
    assert d_u2.name == "Query 1"  # First draft for User 2

    # 5. Create a draft for User 1 in WS 2
    d_w2 = create_draft(
        request=req_u1_w2,
        req=SqlDraftCreate(sql_text="SELECT 'workspace 2 query';"),
        db=db_session,
        user={"id": user1},
    )
    assert d_w2.workspace_id == ws2
    assert d_w2.name == "Query 1"  # First draft for User 1 in WS 2

    # 6. Verify listing for User 1 in WS 1 -> should return d1, d2, d3 ONLY
    drafts_u1_w1 = list_drafts(request=req_u1_w1, db=db_session, user={"id": user1})
    assert len(drafts_u1_w1) == 3
    draft_ids = [d.id for d in drafts_u1_w1]
    assert d1.id in draft_ids
    assert d2.id in draft_ids
    assert d3.id in draft_ids
    assert d_u2.id not in draft_ids
    assert d_w2.id not in draft_ids

    # 7. Verify listing for User 2 in WS 1 -> should return d_u2 ONLY
    drafts_u2_w1 = list_drafts(request=req_u2_w1, db=db_session, user={"id": user2})
    assert len(drafts_u2_w1) == 1
    assert drafts_u2_w1[0].id == d_u2.id

    # 8. Verify listing for User 1 in WS 2 -> should return d_w2 ONLY
    drafts_u1_w2 = list_drafts(request=req_u1_w2, db=db_session, user={"id": user1})
    assert len(drafts_u1_w2) == 1
    assert drafts_u1_w2[0].id == d_w2.id

    # 9. Test Renaming & Updating a draft
    updated = update_draft(
        draft_id=d1.id,
        req=SqlDraftUpdate(name="Annual Revenue Analysis", sql_text="SELECT sum(amount) FROM revenue;"),
        request=req_u1_w1,
        db=db_session,
        user={"id": user1},
    )
    assert updated.id == d1.id
    assert updated.name == "Annual Revenue Analysis"
    assert updated.sql_text == "SELECT sum(amount) FROM revenue;"

    # 10. User 2 trying to update User 1's draft should fail with 404 (not found in user scope)
    with pytest.raises(Exception) as exc_info:
        update_draft(
            draft_id=d1.id,
            req=SqlDraftUpdate(name="Hacked"),
            request=req_u2_w1,
            db=db_session,
            user={"id": user2},
        )
    assert "404" in str(exc_info.value) or "Draft query not found" in str(exc_info.value)

    # 11. Test Deletion
    res = delete_draft(
        draft_id=d3.id,
        request=req_u1_w1,
        db=db_session,
        user={"id": user1},
    )
    assert res["deleted"] is True
    assert res["id"] == d3.id

    # Verify d3 is deleted from User 1 WS 1 list
    drafts_after_delete = list_drafts(request=req_u1_w1, db=db_session, user={"id": user1})
    assert len(drafts_after_delete) == 2
    assert d3.id not in [d.id for d in drafts_after_delete]
