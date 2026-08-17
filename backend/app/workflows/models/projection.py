from sqlalchemy import Column, String, DateTime, Index, Integer

from app.database import SystemBase as Base


class BreakdownEventFlat(Base):
    """Projection table â€“ denormalized view of breakdown_event entity records.

    READ-ONLY from the explorer's perspective.
    Populated by the projection sync service.
    """
    __tablename__ = "breakdown_events_flat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, nullable=False)
    asset_id = Column(String, nullable=False)
    child_asset_id = Column(String, nullable=True)
    breakdown_type = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    description = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="OPEN")
    created_by = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_flat_asset_time", "asset_id", "timestamp"),
        Index("idx_flat_status", "status"),
        Index("idx_flat_severity", "severity"),
    )