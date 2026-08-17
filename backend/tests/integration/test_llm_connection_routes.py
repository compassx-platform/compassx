from __future__ import annotations


def test_create_gemini_llm_connection(client):
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"name": "Gemini Workspace", "description": "test"},
    )
    assert workspace_response.status_code == 201, workspace_response.text

    workspace_id = workspace_response.json()["id"]
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/llm-connections",
        json={
            "name": "Gemini API",
            "provider": "gemini",
            "model_name": "gemini-2.5-flash",
            "api_key": "AIza-test-key",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["provider"] == "gemini"
    assert payload["model_name"] == "gemini-2.5-flash"
    assert payload["api_key_masked"]