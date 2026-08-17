"""Integration tests for workflow HTTP routes."""

from __future__ import annotations

from app.services import entity_service


def test_create_workflow_and_query_transitions(client, db_session):
    entity_service.create_entity_definition(
        db_session,
        definition_data={
            "name": "workflow_entity",
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "title", "field_type": "string", "is_required": True, "is_indexed": False},
                {"field_name": "count", "field_type": "number", "is_required": False, "is_indexed": False},
            ],
            "system_fields": [],
        },
        user_email="test@example.com",
    )

    payload = {
        "entity_name": "workflow_entity",
        "initial_state": "OPEN",
        "states": ["OPEN", "IN_PROGRESS", "RESOLVED"],
        "transitions": [
            {"from": "OPEN", "to": "IN_PROGRESS"},
            {"from": "IN_PROGRESS", "to": "RESOLVED"},
        ],
    }

    response = client.post("/workflows", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["entity_name"] == "workflow_entity"
    assert data["initial_state"] == "OPEN"
    assert data["is_enabled"] is True
    assert len(data["states"]) == 3
    assert {tuple((t["from"], t["to"])) for t in data["transitions"]} == {
        ("OPEN", "IN_PROGRESS"),
        ("IN_PROGRESS", "RESOLVED"),
    }

    transitions_resp = client.get("/workflows/workflow_entity/transitions", params={"current_state": "OPEN"})
    assert transitions_resp.status_code == 200
    assert transitions_resp.json()["available"] == ["IN_PROGRESS"]


def test_invalid_state_transition_on_record_update(client, db_session):
    entity_service.create_entity_definition(
        db_session,
        definition_data={
            "name": "workflow_record_entity",
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "title", "field_type": "string", "is_required": True, "is_indexed": False},
                {"field_name": "count", "field_type": "number", "is_required": False, "is_indexed": False},
            ],
            "system_fields": [],
        },
        user_email="test@example.com",
    )

    workflow_payload = {
        "entity_name": "workflow_record_entity",
        "initial_state": "OPEN",
        "states": ["OPEN", "IN_PROGRESS", "RESOLVED"],
        "transitions": [
            {"from": "OPEN", "to": "IN_PROGRESS"},
            {"from": "IN_PROGRESS", "to": "RESOLVED"},
        ],
    }
    client.post("/workflows", json=workflow_payload)

    record_resp = client.post("/api/v1/entities/workflow_record_entity/records", json={
        "asset_id": None,
        "data": {"title": "Blocked issue", "count": 1},
    })
    assert record_resp.status_code == 201
    record = record_resp.json()

    invalid_resp = client.put(f"/api/v1/entities/workflow_record_entity/records/{record['id']}", json={
        "asset_id": None,
        "data": {},
        "status": "RESOLVED",
    })

    assert invalid_resp.status_code == 400
    assert "Invalid transition" in invalid_resp.json().get("detail", "")


def test_record_updates_status_without_workflow(client, db_session):
    entity_service.create_entity_definition(
        db_session,
        definition_data={
            "name": "free_entity",
            "entity_type": "generic",
            "asset_scoped": False,
            "time_based": False,
            "time_series": False,
            "fields": [
                {"field_name": "name", "field_type": "string", "is_required": True, "is_indexed": False},
            ],
            "system_fields": [],
        },
        user_email="test@example.com",
    )

    record_resp = client.post("/api/v1/entities/free_entity/records", json={
        "asset_id": None,
        "data": {"name": "Temporary"},
    })
    assert record_resp.status_code == 201
    record = record_resp.json()

    update_resp = client.put(f"/api/v1/entities/free_entity/records/{record['id']}", json={
        "asset_id": None,
        "data": {},
        "status": "PENDING",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "PENDING"
