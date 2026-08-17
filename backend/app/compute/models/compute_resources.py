"""Compute resources database model."""
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.sql import func
from app.database import SystemBase as Base


class ComputeResource(Base):
    """Persistent compute resource configuration."""

    __tablename__ = "compute_resources"
    __table_args__ = {"schema": "compute"}

    id = Column(String, primary_key=True, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    runtime = Column(String, nullable=False)  # spark, flink, ray, duckdb
    profile = Column(String, nullable=False)  # local, cloud-s, cloud-l, gpu
    user_id = Column(String, nullable=False, index=True)
    custom_image = Column(String, nullable=True)
    extra_env = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String, nullable=False)
    description = Column(String, nullable=True)
    deployment_name = Column(String, nullable=True, index=True)
    pod_name = Column(String, nullable=True, index=True)
    desired_status = Column(String, nullable=False, server_default="stopped")
    is_default = Column(Boolean, nullable=False, server_default="false")
