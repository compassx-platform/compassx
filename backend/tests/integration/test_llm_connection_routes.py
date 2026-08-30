from __future__ import annotations


def test_create_gemini_llm_connection(client):
    response = client.post(
        "/api/v1/llm-connections",
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