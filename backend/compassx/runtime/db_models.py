"""SQLAlchemy model for platform runtime metadata.

Kept separate from app models; imported lazily so the platform CLI can
run without the backend's database stack.
"""

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.database import SystemBase as Base


class PlatformRuntime(Base):
    """Runtime ID -> infrastructure ID mapping + runtime metadata.

    infra_id (pod/deployment name, container id, PID) is internal to the
    Resource Manager and must never be exposed through public APIs.
    """

    __tablename__ = "platform_runtimes"
    __table_args__ = {"schema": "compute"}

    runtime_id = Column(String, primary_key=True, index=True)
    runtime_type = Column(String, nullable=False)
    driver = Column(String, nullable=False)
    infra_id = Column(String, nullable=True, index=True)
    namespace = Column(String, nullable=True)
    user_id = Column(String, nullable=True, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    phase = Column(String, nullable=False, server_default="unknown")
    spec_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
