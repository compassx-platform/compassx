import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from fastapi import Request
from sqlalchemy.orm import Session

from app.workspace.models import Workspace, Account, Principal
from app.models.agents import LLMConnection, Agent
from app.models.compute_resources import ComputeResource
from app.sql_warehouse.models import SqlWarehouse
from app.agents.routes.llm_connection_routes import create_llm_connection, list_llm_connections
from app.agents.routes.agent_routes import create_agent, list_agents
from app.compute.routes.router import create_compute_resource, list_compute_resources
from app.compute.schemas import ComputeResourceRequest, RuntimeType, ComputeProfileId
from app.sql_warehouse.routes import create_wh, list_wh
from app.sql_warehouse.schemas import WarehouseCreate
from app.schemas.agents import LLMConnectionCreate, LLMProvider, AgentCreate


def _mock_request(workspace_id: str) -> Request:
    request = MagicMock(spec=Request)
    class MockWorkspaceContext:
        def __init__(self, ws_id):
            self.workspace_id = ws_id
    request.state.workspace = MockWorkspaceContext(workspace_id)
    return request


def _permissive_guard(principal_id: str) -> MagicMock:
    """A guard that allows everything, acting as ``principal_id``.

    This test is about workspace scoping, not access control — that is
    covered by the governance suite. Calling the handlers directly bypasses
    FastAPI's dependency injection, so the guard has to be supplied by hand.
    """
    guard = MagicMock()
    guard.principal.id = principal_id
    guard.require.return_value = None
    guard.require_workspace_admin.return_value = None
    guard.can.return_value = True
    guard.claim_ownership.return_value = None
    return guard


def test_resource_scoping_isolation(db_session: Session):
    # Setup accounts and principal
    account = Account(id=str(uuid4()), name="Test Account", slug="testaccount")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=str(uuid4()),
        account_id=account.id,
        type="user",
        name="System User",
        email="system@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    # Create two workspaces
    ws1 = Workspace(
        id=str(uuid4()),
        account_id=account.id,
        name="Workspace 1",
        slug="ws-1",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    ws2 = Workspace(
        id=str(uuid4()),
        account_id=account.id,
        name="Workspace 2",
        slug="ws-2",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    db_session.add_all([ws1, ws2])
    db_session.commit()

    # 1. Scope LLM Connections
    req1 = _mock_request(ws1.id)
    req2 = _mock_request(ws2.id)

    body_llm = LLMConnectionCreate(
        name="WS1 LLM",
        provider=LLMProvider.openai,
        model_name="gpt-4",
        api_key="secret",
    )
    create_llm_connection(req1, body_llm, db_session, {"id": principal.id})

    # List connections under ws1 context
    ws1_llms = list_llm_connections(req1, db_session)
    assert len(ws1_llms) == 1
    assert ws1_llms[0].name == "WS1 LLM"

    # List connections under ws2 context
    ws2_llms = list_llm_connections(req2, db_session)
    assert len(ws2_llms) == 0

    # 2. Scope Agents
    body_agent = AgentCreate(
        name="WS1 Agent",
        description="Test Agent in WS1",
        avatar="🤖",
        color="#000",
        prompt="Test prompt",
        model="gpt-4",
        max_tokens=4096,
        is_orchestrator=False,
        visibility="shared",
        tools=[],
        db_connections=[],
        git_connections=[],
        skills=[],
    )
    create_agent(req1, body_agent, db_session)

    # List agents under ws1 context
    ws1_agents = list_agents(req1, db_session)
    assert len(ws1_agents) == 1
    assert ws1_agents[0].name == "WS1 Agent"

    # List agents under ws2 context
    ws2_agents = list_agents(req2, db_session)
    assert len(ws2_agents) == 0

    # 3. Scope Compute Resources
    body_compute = ComputeResourceRequest(
        name="WS1 Compute",
        runtime=RuntimeType.SPARK,
        profile=ComputeProfileId.LOCAL,
        description="Compute resource in WS1",
    )
    guard = _permissive_guard(principal.id)
    create_compute_resource(req1, body_compute, db=db_session, guard=guard)

    # List compute under ws1 context
    ws1_computes = list_compute_resources(req1, db=db_session, guard=guard)
    assert len(ws1_computes) == 1
    assert ws1_computes[0].name == "WS1 Compute"

    # List compute under ws2 context
    ws2_computes = list_compute_resources(req2, db=db_session, guard=guard)
    assert len(ws2_computes) == 0

    # 4. Scope SQL Warehouses
    body_wh = WarehouseCreate(
        name="WS1 Warehouse",
        description="Warehouse in WS1",
        engine="duckdb",
        config={},
        resource_policy={},
    )
    class MockUser:
        id = principal.id
    create_wh(req1, body_wh, db_session, user=MockUser())

    # List warehouses under ws1 context
    ws1_whs = list_wh(req1, db_session, user=MockUser())
    assert len(ws1_whs) == 1
    assert ws1_whs[0].name == "WS1 Warehouse"

    # List warehouses under ws2 context
    ws2_whs = list_wh(req2, db_session, user=MockUser())
    assert len(ws2_whs) == 0


def test_agent_subsystem_resource_scoping(db_session: Session):
    from sqlalchemy import text
    from app.workspace.models import Workspace, Account, Principal
    from app.models.agents import Agent
    from app.agents.schemas.agents import SkillCreate, BudgetCreate, ChatSessionCreate
    from app.agents.routes.skill_routes import create_skill, list_skills
    from app.agents.routes.budget_routes import create_budget, list_budgets
    from app.agents.routes.chat_routes import create_session, list_sessions
    from app.agents.routes.llm_call_routes import list_llm_call_logs
    from app.agents.routes.stream_routes import list_active_streams
    from app.agents.services.stream_registry import stream_registry
    from app.agents.models.agents import LlmCallLog, Skill

    account = Account(id=str(uuid4()), name="Subsystem Account", slug="sub-account")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=str(uuid4()),
        account_id=account.id,
        type="user",
        name="Subsystem User",
        email="subsystem@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    # Create two workspaces
    ws1 = Workspace(
        id=str(uuid4()),
        account_id=account.id,
        name="Workspace 1",
        slug="ws-1",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    ws2 = Workspace(
        id=str(uuid4()),
        account_id=account.id,
        name="Workspace 2",
        slug="ws-2",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    db_session.add_all([ws1, ws2])
    db_session.commit()

    req1 = _mock_request(ws1.id)
    req2 = _mock_request(ws2.id)

    # First create an agent in WS1 so we have a valid agent_id for other tests
    agent_ws1 = Agent(
        workspace_id=ws1.id,
        name="WS1 Agent",
        model="gpt-4",
    )
    db_session.add(agent_ws1)
    db_session.commit()

    # 1. Test Skills Scoping
    body_skill = SkillCreate(
        name="WS1 Skill",
        description="A specialized skill in WS1",
        body="print('hello')",
        trigger_hints=["ws1", "hello"],
    )
    create_skill(req1, body_skill, db_session)

    # List under WS1
    ws1_skills = list_skills(req1, db=db_session)
    assert len(ws1_skills) == 1
    assert ws1_skills[0].name == "WS1 Skill"

    # List under WS2
    ws2_skills = list_skills(req2, db=db_session)
    assert len(ws2_skills) == 0

    # 2. Test Budgets Scoping
    body_budget = BudgetCreate(
        scope_type="agent",
        scope_id=str(agent_ws1.id),
        period="daily",
        limit_amount=10.0,
        warn_threshold_pct=80,
        on_exceeded="alert_only",
    )
    create_budget(req1, body_budget, db_session, {"username": "system"})

    # List under WS1
    ws1_budgets = list_budgets(req1, db=db_session)
    assert len(ws1_budgets) == 1
    assert float(ws1_budgets[0].limit_amount) == 10.0

    # List under WS2
    ws2_budgets = list_budgets(req2, db=db_session)
    assert len(ws2_budgets) == 0

    # 3. Test Chat Sessions Scoping
    body_session = ChatSessionCreate(title="Session in WS1")
    create_session(req1, agent_ws1.id, body_session, db_session)

    # List sessions under WS1
    ws1_sessions = list_sessions(req1, agent_ws1.id, db_session)
    assert len(ws1_sessions) == 1
    assert ws1_sessions[0].title == "Session in WS1"

    # List sessions under WS2 should raise 404 because agent is in WS1
    with pytest.raises(Exception):
        list_sessions(req2, agent_ws1.id, db_session)

    # 4. Test LLM Call Logs Scoping
    log_ws1 = LlmCallLog(
        workspace_id=ws1.id,
        agent_id=agent_ws1.id,
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
    )
    db_session.add(log_ws1)
    db_session.flush()

    # List call logs under WS1
    ws1_logs = list_llm_call_logs(
        req1,
        agent_id=None,
        session_id=None,
        model=None,
        start_date=None,
        end_date=None,
        limit=50,
        offset=0,
        db=db_session,
        current_user={"id": principal.id}
    )
    assert len(ws1_logs) == 1

    # List call logs under WS2
    ws2_logs = list_llm_call_logs(
        req2,
        agent_id=None,
        session_id=None,
        model=None,
        start_date=None,
        end_date=None,
        limit=50,
        offset=0,
        db=db_session,
        current_user={"id": principal.id}
    )
    assert len(ws2_logs) == 0

    # 5. Test Active Streams Scoping
    # Register stream in WS1
    stream_id = stream_registry.start(
        kind="agent",
        agent_id=agent_ws1.id,
        workspace_id=ws1.id,
    )
    try:
        # List active streams under WS1
        ws1_streams = list_active_streams(req1, kind=None)["streams"]
        assert len(ws1_streams) == 1
        assert ws1_streams[0]["id"] == stream_id

        # List active streams under WS2
        ws2_streams = list_active_streams(req2, kind=None)["streams"]
        assert len(ws2_streams) == 0
    finally:
        stream_registry.finish(stream_id)


def test_catalog_metadata_scoping(db_session: Session):
    import asyncio
    from uuid import uuid4
    from app.catalog.models import UnifiedCatalog, CatalogWorkspaceBinding
    from app.sql_warehouse.catalog.metadata_api import CatalogMetadataAPI

    # Create catalogs
    cat_global = UnifiedCatalog(id=str(uuid4()), name="global_cat", created_by="system", all_workspaces=True)
    cat_ws1 = UnifiedCatalog(id=str(uuid4()), name="ws1_cat", created_by="system", all_workspaces=False)
    cat_ws2 = UnifiedCatalog(id=str(uuid4()), name="ws2_cat", created_by="system", all_workspaces=False)

    db_session.add_all([cat_global, cat_ws1, cat_ws2])
    db_session.commit()

    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    # Create binding for ws1 to ws1_cat
    binding = CatalogWorkspaceBinding(
        id=str(uuid4()),
        catalog_id=cat_ws1.id,
        workspace_id=ws1_id,
        privilege="select",
        bound_by="system",
    )
    db_session.add(binding)
    db_session.commit()

    # Query metadata catalogs under ws1
    api_ws1 = CatalogMetadataAPI(db_session, workspace_id=ws1_id)
    res_ws1 = asyncio.run(api_ws1.list_catalogs())
    names_ws1 = {c["name"] for c in res_ws1["catalogs"]}
    assert "global_cat" in names_ws1
    assert "ws1_cat" in names_ws1
    assert "ws2_cat" not in names_ws1

    # Query metadata catalogs under ws2 (should only see global_cat)
    api_ws2 = CatalogMetadataAPI(db_session, workspace_id=ws2_id)
    res_ws2 = asyncio.run(api_ws2.list_catalogs())
    names_ws2 = {c["name"] for c in res_ws2["catalogs"]}
    assert "global_cat" in names_ws2
    assert "ws1_cat" not in names_ws2
    assert "ws2_cat" not in names_ws2

    # Test _catalog method scoping
    assert api_ws1._catalog("ws1_cat") is not None
    assert api_ws1._catalog("ws2_cat") is None
    assert api_ws2._catalog("ws1_cat") is None


