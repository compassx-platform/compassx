"""Agent Manifest pydantic models per AI Data Engineer Agent Spec v5 (Part C)."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class BaseProfile(str, Enum):
    BUILD_AGENT = "build_agent"
    REACTIVE_AGENT = "reactive_agent"
    CUSTOM = "custom"


class PlanningCapability(BaseModel):
    enabled: bool = True
    router_thresholds: str = "default"
    max_retry_attempts: int = 3


class CheckpointsCapability(BaseModel):
    enabled: bool = True
    gated_write_categories: List[str] = Field(
        default_factory=lambda: ["catalog", "storage", "scheduler", "dashboard", "app"]
    )


class DocumentUploadCapability(BaseModel):
    enabled: bool = True
    accepted_types: List[str] = Field(
        default_factory=lambda: ["pdf", "docx", "xlsx", "csv", "txt", "md", "json", "png", "jpg", "jpeg", "webp", "gif", "svg"]
    )


class ArtifactVisibilityCapability(BaseModel):
    enabled: bool = True
    link_resolution: bool = True
    diff_capture: bool = True


class AgentCapabilities(BaseModel):
    planning: PlanningCapability = Field(default_factory=PlanningCapability)
    checkpoints: CheckpointsCapability = Field(default_factory=CheckpointsCapability)
    document_upload: DocumentUploadCapability = Field(default_factory=DocumentUploadCapability)
    artifact_visibility: ArtifactVisibilityCapability = Field(default_factory=ArtifactVisibilityCapability)


class AgentManifest(BaseModel):
    agent_id: str = "ai-data-engineer"
    display_name: str = "AI Data Engineer"
    base_profile: BaseProfile = BaseProfile.REACTIVE_AGENT
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)

    @classmethod
    def default_for_profile(cls, profile: BaseProfile, agent_id: str = "agent", display_name: str = "Agent") -> AgentManifest:
        if profile == BaseProfile.REACTIVE_AGENT:
            return cls(
                agent_id=agent_id,
                display_name=display_name,
                base_profile=profile,
                capabilities=AgentCapabilities(
                    planning=PlanningCapability(enabled=False),
                    checkpoints=CheckpointsCapability(enabled=False, gated_write_categories=[]),
                    document_upload=DocumentUploadCapability(enabled=True),
                    artifact_visibility=ArtifactVisibilityCapability(enabled=False, link_resolution=False, diff_capture=False),
                )
            )
        return cls(
            agent_id=agent_id,
            display_name=display_name,
            base_profile=profile,
            capabilities=AgentCapabilities()
        )
