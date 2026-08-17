from __future__ import annotations

from fastapi.testclient import TestClient


def test_catalog_bootstraps_default_catalog(client: TestClient):
    response = client.get("/api/v1/catalog/catalogs", headers={"authkey": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == "compassx"


from unittest.mock import patch

class MockFS:
    def __init__(self):
        self.files = {}
        
    def write_text(self, bucket: str, key: str, data: str):
        self.files[(bucket, key)] = data
        
    def exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self.files
        
    def delete(self, bucket: str, key: str):
        self.files.pop((bucket, key), None)


@patch("services.storage.fs.get_fs")
def test_catalog_notebook_lifecycle(mock_get_fs, client: TestClient):
    mock_fs = MockFS()
    mock_get_fs.return_value = mock_fs
    headers = {"authkey": "test-key"}
    
    # 0. Bootstrap default catalog
    client.get("/api/v1/catalog/catalogs", headers=headers)
    
    # 1. Create a target schema
    resp = client.post(
        "/api/v1/catalog/catalogs/compassx/schemas",
        json={"name": "analytics", "description": "Analytics Schema"},
        headers=headers,
    )
    print("CREATE SCHEMA RESP:", resp.status_code, resp.text)
    assert resp.status_code == 201

    # 2. Create notebook
    resp = client.post(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks",
        json={"name": "test_notebook", "comment": "Test Comment"},
        headers=headers,
    )
    print("CREATE NOTEBOOK RESP:", resp.status_code, resp.text)
    assert resp.status_code == 201
    nb_data = resp.json()
    assert nb_data["name"] == "test_notebook"
    assert nb_data["comment"] == "Test Comment"
    assert nb_data["catalog_name"] == "compassx"
    assert nb_data["schema_name"] == "analytics"
    assert "id" in nb_data

    # 3. Create notebook duplicate (name conflict 409)
    resp = client.post(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks",
        json={"name": "test_notebook", "comment": "Duplicate"},
        headers=headers,
    )
    assert resp.status_code == 409

    # 4. List notebooks
    resp = client.get(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks",
        headers=headers,
    )
    assert resp.status_code == 200
    nb_list = resp.json()
    assert len(nb_list) == 1
    assert nb_list[0]["name"] == "test_notebook"

    # 5. Get notebook
    resp = client.get(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks/test_notebook",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "test_notebook"

    # 6. Update/Rename notebook
    resp = client.patch(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks/test_notebook",
        json={"name": "test_notebook_updated", "comment": "Updated Comment"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "test_notebook_updated"
    assert resp.json()["comment"] == "Updated Comment"

    # 7. Create another schema for move target
    resp = client.post(
        "/api/v1/catalog/catalogs/compassx/schemas",
        json={"name": "production", "description": "Prod Schema"},
        headers=headers,
    )
    assert resp.status_code == 201

    # 8. Move notebook
    resp = client.post(
        "/api/v1/catalog/catalogs/compassx/schemas/analytics/notebooks/test_notebook_updated/move",
        json={"target_catalog": "compassx", "target_schema": "production", "new_name": "moved_notebook"},
        headers=headers,
    )
    assert resp.status_code == 200
    moved_data = resp.json()
    assert moved_data["name"] == "moved_notebook"
    assert moved_data["schema_name"] == "production"

    # 9. Schema Deletion Guard: Deleting "production" schema should fail because it contains notebooks
    resp = client.delete(
        "/api/v1/catalog/catalogs/compassx/schemas/production",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "contains registered notebooks" in resp.json()["detail"]

    # 10. Delete notebook
    resp = client.delete(
        "/api/v1/catalog/catalogs/compassx/schemas/production/notebooks/moved_notebook",
        headers=headers,
    )
    assert resp.status_code == 204

    # 11. Schema Deletion Guard: Deleting "production" schema should now succeed
    resp = client.delete(
        "/api/v1/catalog/catalogs/compassx/schemas/production",
        headers=headers,
    )
    assert resp.status_code == 204




