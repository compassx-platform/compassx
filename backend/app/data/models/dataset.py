from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase as Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Text, unique=True, nullable=False)
    type = Column(String, nullable=True)       # "entity", "projection", "api"
    source = Column(String, nullable=True)     # "projection_table", "entity_records", etc.
    entity_id = Column(Integer, nullable=True)
    config = Column(JSONB, default=dict)       # table name, adapter config, etc.