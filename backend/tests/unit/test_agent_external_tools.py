"""End-to-end tests for Agent External Tools (architecture/agent-external-tools-spec.md)."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_system_db, get_account_db
from app.agents.models.external_connection import ExternalConnection, ToolInvocationAuditLog
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTool, UnifiedCatalogToolVersion
from app.agents.services import external_connection_service as conn_svc
from app.agents.schemas.external_connections import ExternalConnectionCreate, ExternalConnectionUpdate
from app.catalog import tool_service
from app.catalog.tool_schemas import ToolPromoteRequest
from app.agents.services.agent.tools import external_tool_executor
from app.agents.services.agent.tools.external_catalog_tool import ExternalCatalogTool
from services.compassx_tools import tool, connections, extract_param_schema, ConnectionClient
import services.compassx_tools as cx


# ── 1. External Connections CRUD & Encryption ─────────────────────────────────

def test_external_connection_crud_and_encryption(db_session: Session):
    # 1. Create connection with sensitive token
    payload = ExternalConnectionCreate(
        name="loki_prod",
        connector_type="loki",
        base_url="http://loki-prod.internal:3100",
        auth_config={"token": "super-secret-token-xyz", "headers": {"X-Scope-OrgID": "tenant1"}},
        status="active",
    )
    conn = conn_svc.create_connection(db_session, payload, workspace_id=None, user_id="user_1")
    assert conn.id is not None
    assert conn.name == "loki_prod"
    # Ensure auth_config is encrypted (not plaintext) in the database column
    assert conn.auth_config is not None
    assert "super-secret-token-xyz" not in conn.auth_config

    # Decrypt server-side
    decrypted = conn_svc.get_decrypted_auth_config(conn)
    assert isinstance(decrypted, dict)
    assert decrypted["token"] == "super-secret-token-xyz"
    assert decrypted["headers"]["X-Scope-OrgID"] == "tenant1"

    # 2. List & Get
    conns = conn_svc.list_connections(db_session)
    assert len(conns) >= 1
    found = conn_svc.get_connection(db_session, str(conn.id))
    assert found is not None
    assert found.name == "loki_prod"

    # 3. Update
    updated = conn_svc.update_connection(
        db_session,
        str(conn.id),
        ExternalConnectionUpdate(base_url="http://loki-updated.internal:3100"),
    )
    assert updated.base_url == "http://loki-updated.internal:3100"

    # 4. Disable
    disabled = conn_svc.disable_connection(db_session, str(conn.id))
    assert disabled.status == "disabled"

    # 5. Delete
    deleted = conn_svc.delete_connection(db_session, str(conn.id))
    assert deleted is True
    assert conn_svc.get_connection(db_session, str(conn.id)) is None


def test_external_connection_api_endpoints(client: TestClient):
    # Test POST create
    res = client.post(
        "/api/v1/external-connections",
        json={
            "name": "loki_api_test",
            "connector_type": "loki",
            "base_url": "http://loki.internal:3100",
            "auth_config": {"token": "secret123"},
            "status": "active",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "loki_api_test"
    conn_id = data["id"]
    # Ensure auth_config is NOT leaked in API response
    assert "auth_config" not in data

    # Test GET list
    res_list = client.get("/api/v1/external-connections")
    assert res_list.status_code == 200
    items = res_list.json()
    assert any(i["id"] == conn_id for i in items)
    for i in items:
        assert "auth_config" not in i

    # Test GET by ID
    res_get = client.get(f"/api/v1/external-connections/{conn_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "loki_api_test"
    assert "auth_config" not in res_get.json()

    # Test PUT update
    res_put = client.put(
        f"/api/v1/external-connections/{conn_id}",
        json={"base_url": "http://loki2.internal:3100"},
    )
    assert res_put.status_code == 200
    assert res_put.json()["base_url"] == "http://loki2.internal:3100"

    # Test POST disable
    res_dis = client.post(f"/api/v1/external-connections/{conn_id}/disable")
    assert res_dis.status_code == 200
    assert res_dis.json()["status"] == "disabled"

    # Test DELETE
    res_del = client.delete(f"/api/v1/external-connections/{conn_id}")
    assert res_del.status_code == 204


# ── 2. SDK Contract (@cx.tool & cx.connections.get) ───────────────────────────

def test_sdk_tool_decorator_and_schema():
    @cx.tool(
        name="get_service_logs",
        description="Fetch logs from Loki",
        connections=["loki_prod"],
    )
    def get_service_logs(service: str, limit: int = 50) -> str:
        return f"logs for {service}"

    assert getattr(get_service_logs, "_is_cx_tool") is True
    assert getattr(get_service_logs, "_tool_name") == "get_service_logs"
    assert getattr(get_service_logs, "_tool_description") == "Fetch logs from Loki"
    assert getattr(get_service_logs, "_tool_connections") == ["loki_prod"]

    schema = getattr(get_service_logs, "_tool_param_schema")
    assert schema["type"] == "object"
    assert "service" in schema["properties"]
    assert schema["properties"]["service"]["type"] == "string"
    assert "limit" in schema["properties"]
    assert schema["properties"]["limit"]["type"] == "integer"
    assert schema["required"] == ["service"]


def test_sdk_connection_client_and_loki_query():
    client = ConnectionClient(
        name="loki_prod",
        base_url="http://loki:3100",
        auth_config={"token": "tok123", "headers": {"X-Org": "default"}},
        connector_type="loki",
    )
    assert client.headers["Authorization"] == "Bearer tok123"
    assert client.headers["X-Org"] == "default"

    # Mock Loki query_range response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"service": "payment-api"},
                    "values": [
                        ["1692440000000000000", "INFO: Payment processed successfully"],
                        ["1692440005000000000", "WARN: Slow response from DB"],
                    ],
                }
            ],
        },
    }

    with patch.object(client, "get", return_value=mock_response):
        logs = client.query_range('{service="payment-api"}', minutes=5)
        assert "Payment processed successfully" in logs
        assert "Slow response from DB" in logs


# ── 3. Catalog Promotion & Tool Versioning ───────────────────────────────────

def test_catalog_tool_promotion_and_versioning(db_session: Session):
    tool_code_v1 = '''
import cx

@cx.tool(
    name="query_loki_logs",
    description="Fetch Loki logs v1",
    connections=["loki_prod"]
)
def query_loki_logs(service: str) -> str:
    return f"v1 logs for {service}"
'''

    # Initial promotion (v1)
    req_v1 = ToolPromoteRequest(
        catalog="main",
        schema="default",
        name="query_loki_logs",
        source_code=tool_code_v1,
    )
    tool_obj = tool_service.promote_tool(db_session, req_v1, user_id="author_1")
    assert tool_obj.name == "query_loki_logs"
    assert tool_obj.current_version == 1
    assert len(tool_obj.versions) == 1
    assert tool_obj.versions[0].version == 1
    assert tool_obj.connection_dependencies == ["loki_prod"]

    # Re-promotion (v2)
    tool_code_v2 = '''
import cx

@cx.tool(
    name="query_loki_logs",
    description="Fetch Loki logs v2 with limit",
    connections=["loki_prod"]
)
def query_loki_logs(service: str, limit: int = 100) -> str:
    return f"v2 logs for {service}, limit={limit}"
'''
    req_v2 = ToolPromoteRequest(
        catalog="main",
        schema="default",
        name="query_loki_logs",
        source_code=tool_code_v2,
    )
    tool_v2 = tool_service.promote_tool(db_session, req_v2, user_id="author_2")
    assert tool_v2.id == tool_obj.id
    assert tool_v2.current_version == 2
    assert len(tool_v2.versions) == 2
    assert tool_v2.versions[1].version == 2


def test_catalog_tool_api_endpoints(client: TestClient):
    source_code = '''
import cx

@cx.tool(name="api_tool_test", description="Test tool via API", connections=["loki_prod"])
def api_tool_test(service: str) -> str:
    return "ok"
'''
    res = client.post(
        "/api/v1/catalog/tools/promote",
        json={
            "catalog": "main",
            "schema": "default",
            "name": "api_tool_test",
            "source_code": source_code,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "api_tool_test"
    assert data["current_version"] == 1
    tool_id = data["id"]

    # Get tool
    res_get = client.get(f"/api/v1/catalog/tools/{tool_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == tool_id
    assert len(res_get.json()["versions"]) == 1

    # List tools
    res_list = client.get("/api/v1/catalog/tools")
    assert res_list.status_code == 200
    assert any(t["id"] == tool_id for t in res_list.json())


# ── 4. Execution Service Tests (Success, Truncation, Timeout, Errors, Audit) ───

def test_execution_service_success(db_session: Session):
    # Create connection
    conn = conn_svc.create_connection(
        db_session,
        ExternalConnectionCreate(
            name="loki_exec_test",
            connector_type="loki",
            base_url="http://mock-loki:3100",
            auth_config={"token": "mock-token"},
            status="active",
        ),
    )

    # Promote tool
    tool_code = '''
from services.compassx_tools import connections as cx_connections

def execute_test_func(service: str) -> dict:
    conn = cx_connections.get("loki_exec_test")
    return {"status": "ok", "service": service, "base_url": conn.base_url}
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="execute_test_func",
            source_code=tool_code,
            connection_dependencies=["loki_exec_test"],
        ),
    )

    res = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_obj.id,
            connection_id=str(conn.id),
            params={"service": "auth-service"},
            session_id="session_123",
            agent_type="nova",
        )
    )

    assert res["ok"] is True
    assert res["result"]["status"] == "ok"
    assert res["result"]["service"] == "auth-service"
    assert res["result"]["base_url"] == "http://mock-loki:3100"
    assert res["truncated"] is False

    # Verify audit row
    audit_row = db_session.query(ToolInvocationAuditLog).filter(ToolInvocationAuditLog.tool_id == tool_obj.id).first()
    assert audit_row is not None
    assert audit_row.status == "success"
    assert audit_row.agent_type == "nova"
    assert audit_row.duration_ms >= 0


def test_execution_service_truncation(db_session: Session):
    # Tool returning > 50KB string
    tool_code = '''
def large_output_tool() -> str:
    return "X" * 60000
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="large_output_tool",
            source_code=tool_code,
        ),
    )

    res = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_obj.id,
            params={},
            session_id="session_trunc",
        )
    )

    assert res["ok"] is True
    assert res["truncated"] is True
    assert "[TRUNCATED: Result exceeded 50KB limit]" in res["result"]


def test_execution_service_disabled_connection(db_session: Session):
    # Disabled connection
    conn = conn_svc.create_connection(
        db_session,
        ExternalConnectionCreate(
            name="loki_disabled",
            connector_type="loki",
            base_url="http://mock-loki:3100",
            status="disabled",
        ),
    )

    tool_code = '''
def test_dis() -> str:
    return "ok"
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="test_dis",
            source_code=tool_code,
            connection_dependencies=["loki_disabled"],
        ),
    )

    res = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_obj.id,
            connection_id=str(conn.id),
            params={},
        )
    )

    assert res["ok"] is False
    assert res["error_type"] == "connection_unreachable"
    assert res["retryable"] is False


def test_execution_service_invalid_params(db_session: Session):
    tool_code = '''
def param_tool(required_arg: str) -> str:
    return required_arg
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="param_tool",
            source_code=tool_code,
            param_schema={"type": "object", "properties": {"required_arg": {"type": "string"}}, "required": ["required_arg"]},
        ),
    )

    # Missing required_arg
    res = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_obj.id,
            params={},
        )
    )
    assert res["ok"] is False
    assert res["error_type"] == "invalid_params"
    assert res["retryable"] is False


def test_execution_service_runtime_error(db_session: Session):
    tool_code = '''
def buggy_tool() -> str:
    return 1 / 0
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="buggy_tool",
            source_code=tool_code,
        ),
    )

    res = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_obj.id,
            params={},
        )
    )
    assert res["ok"] is False
    assert res["error_type"] == "runtime_error"
    assert res["retryable"] is False
    assert "ZeroDivisionError" in res["message"]


def test_execution_service_timeout(db_session: Session):
    tool_code = '''
def slow_tool() -> str:
    return "done"
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="slow_tool",
            source_code=tool_code,
        ),
    )

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=30)):
        res = asyncio.run(
            external_tool_executor.execute_agent_tool(
                tool_id=tool_obj.id,
                params={},
            )
        )
        assert res["ok"] is False
        assert res["error_type"] == "timeout"
        assert res["retryable"] is True


def test_execution_service_concurrency_cap(db_session: Session):
    tool_code = '''
def cap_tool() -> str:
    return "done"
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="cap_tool",
            source_code=tool_code,
        ),
    )

    async def fake_wait_for(fut, timeout):
        if hasattr(fut, "close"):
            fut.close()
        raise asyncio.TimeoutError()

    # Mock timeout waiting on semaphore
    with patch("asyncio.wait_for", side_effect=fake_wait_for):
        res = asyncio.run(
            external_tool_executor.execute_agent_tool(
                tool_id=tool_obj.id,
                params={},
            )
        )
        assert res["ok"] is False
        assert res["error_type"] == "rate_limited"
        assert res["retryable"] is True


def test_execution_service_pinned_version(db_session: Session):
    # Version 1
    code_v1 = '''
def version_tool() -> str:
    return "version 1 output"
'''
    tool_v1 = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="version_tool",
            source_code=code_v1,
        ),
    )

    # Version 2
    code_v2 = '''
def version_tool() -> str:
    return "version 2 output"
'''
    tool_v2 = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="version_tool",
            source_code=code_v2,
        ),
    )

    # Call with pinned version 1 (D11)
    res_v1 = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_v2.id,
            version=1,
            params={},
        )
    )
    assert res_v1["ok"] is True
    assert res_v1["result"] == "version 1 output"

    # Call with latest (version 2)
    res_v2 = asyncio.run(
        external_tool_executor.execute_agent_tool(
            tool_id=tool_v2.id,
            version=2,
            params={},
        )
    )
    assert res_v2["ok"] is True
    assert res_v2["result"] == "version 2 output"


def test_agent_tool_execution_api_endpoint(client: TestClient, db_session: Session):
    tool_code = '''
def api_exec_tool(msg: str) -> dict:
    return {"echo": msg}
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="api_exec_tool",
            source_code=tool_code,
        ),
    )

    res = client.post(
        "/api/v1/agent-tools/execute",
        json={
            "tool_id": tool_obj.id,
            "params": {"msg": "hello from agent"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["result"]["echo"] == "hello from agent"
    assert data["truncated"] is False


# ── 5. BaseTool / Dynamic Catalog Adapter Integration ─────────────────────────

def test_external_catalog_tool_base_tool_adapter(db_session: Session):
    tool_code = '''
def adapter_tool(target: str) -> str:
    return f"analyzed {target}"
'''
    tool_obj = tool_service.promote_tool(
        db_session,
        ToolPromoteRequest(
            catalog="main",
            schema="default",
            name="adapter_tool",
            source_code=tool_code,
            param_schema={"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
        ),
    )

    adapter = ExternalCatalogTool(
        tool_id=tool_obj.id,
        name=tool_obj.name,
        description=tool_obj.description,
        input_schema=tool_obj.param_schema,
        pinned_version=tool_obj.current_version,
        session_id="session_adapter",
    )

    # Verify OpenAI definition
    defn = adapter.to_openai_definition()
    assert defn["type"] == "function"
    assert defn["function"]["name"] == "adapter_tool"
    assert "target" in defn["function"]["parameters"]["properties"]

    # Execute via BaseTool interface
    mock_agent = MagicMock()
    mock_agent.id = 1
    mock_agent.name = "nova"

    res = adapter.execute({"target": "cluster-1"}, agent=mock_agent, db=db_session)
    assert res.ok is True
    assert res.result["result"] == "analyzed cluster-1"
