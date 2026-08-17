"""Unit & Integration tests for AI Data Engineer Agent Spec v2 (Part A-F)."""

import pytest
from app.agents.schemas.agent_manifest import AgentManifest, BaseProfile
from app.agents.services.agent.write_gating_middleware import WriteGatingMiddleware, WriteGatingViolation
from app.agents.services.agent.request_router import RequestRouter
from app.agents.services.agent.plan_service import PlanService
from app.agents.schemas.plan_models import StepStatus
from app.agents.services.document_processor import parse_document


def test_agent_manifest_profiles():
    build_manifest = AgentManifest.default_for_profile(BaseProfile.BUILD_AGENT)
    assert build_manifest.capabilities.planning.enabled is True
    assert build_manifest.capabilities.checkpoints.enabled is True
    assert "catalog" in build_manifest.capabilities.checkpoints.gated_write_categories

    reactive_manifest = AgentManifest.default_for_profile(BaseProfile.REACTIVE_AGENT)
    assert reactive_manifest.capabilities.planning.enabled is False
    assert reactive_manifest.capabilities.checkpoints.enabled is False
    assert len(reactive_manifest.capabilities.checkpoints.gated_write_categories) == 0


def test_write_gating_middleware():
    manifest = AgentManifest.default_for_profile(BaseProfile.BUILD_AGENT)
    middleware = WriteGatingMiddleware(manifest)

    # Discovery/Inspection actions are un-gated (D2, A2)
    assert middleware.is_gated_write_tool("read_table") is False
    assert middleware.is_gated_write_tool("describe_table") is False
    assert middleware.is_gated_write_tool("list_objects") is False

    # Write tools in gated categories require plan checkpoint (Gate 1)
    assert middleware.is_gated_write_tool("create_table") is True

    # Validate Gate 1 exception
    with pytest.raises(WriteGatingViolation) as excinfo:
        middleware.validate_tool_execution("create_table", plan_approved=False, execution_approved=False)
    assert excinfo.value.checkpoint_type == "plan_checkpoint"

    # Validate Gate 2 exception
    with pytest.raises(WriteGatingViolation) as excinfo:
        middleware.validate_tool_execution("create_table", plan_approved=True, execution_approved=False, is_first_real_run=True)
    assert excinfo.value.checkpoint_type == "execution_checkpoint"

    # Approved calls pass
    middleware.validate_tool_execution("create_table", plan_approved=True, execution_approved=True, is_first_real_run=True)


def test_request_router():
    router = RequestRouter()
    build_manifest = AgentManifest.default_for_profile(BaseProfile.BUILD_AGENT)
    reactive_manifest = AgentManifest.default_for_profile(BaseProfile.REACTIVE_AGENT)

    # Multi-stage build
    res = router.classify_request("Build a SCADA medallion pipeline with 3 tables", agent_manifest=build_manifest)
    assert res == "multi_stage_build"

    # Informational
    res_info = router.classify_request("Show me the schema for catalog.sales", agent_manifest=build_manifest)
    assert res_info == "informational"

    # Reactive agent always bypasses multi_stage_build
    res_reactive = router.classify_request("Build a SCADA medallion pipeline", agent_manifest=reactive_manifest)
    assert res_reactive in ("single_action", "informational")


def test_plan_service(tmp_path):
    plan_service = PlanService(storage_dir=str(tmp_path))
    steps = [
        {"id": 1, "description": "Create catalog table", "verification": "describe_table passes"},
        {"id": 2, "description": "Transform data", "verification": "row_count > 0"},
    ]
    plan = plan_service.create_plan(agent_id="ai-data-engineer", goal="Build pipeline", steps=steps)

    assert plan.plan_id is not None
    assert len(plan.steps) == 2

    # Get next step
    next_step = plan_service.get_next_step(plan.plan_id)
    assert next_step.id == 1

    # Mark step done & append correction
    plan_service.mark_step(plan.plan_id, 1, StepStatus.DONE, result={"rows": 100})
    plan_service.append_correction(plan.plan_id, 1, "Corrected schema column type")

    updated = plan_service.get_plan(plan.plan_id)
    assert updated.steps[0].status == StepStatus.DONE
    assert len(updated.steps[0].corrections) == 1

    # Approvals
    plan_service.approve_plan(plan.plan_id)
    plan_service.approve_execution(plan.plan_id)
    final_plan = plan_service.get_plan(plan.plan_id)
    assert final_plan.approved_at is not None
    assert final_plan.execution_approved_at is not None


def test_document_processor_parsing():
    content = b"header1,header2\nval1,val2"
    parsed = parse_document(content, mime_type="text/csv", filename="data.csv")
    assert "header1,header2" in parsed

    json_content = b'{"key": "value"}'
    parsed_json = parse_document(json_content, mime_type="application/json", filename="config.json")
    assert '"key": "value"' in parsed_json
