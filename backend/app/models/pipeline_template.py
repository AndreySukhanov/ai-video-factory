from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.db import Base


class PipelineTemplate(Base):
    """Reusable generation pipeline configuration (idea form + per-episode overrides + storyboard preset)."""
    __tablename__ = "pipeline_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=False)  # opaque JSON with version field
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
