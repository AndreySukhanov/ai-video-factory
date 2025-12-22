from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.db import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String) # GENERATE_STORY, GENERATE_SCENES, GENERATE_SCENE_PROMPTS, GENERATE_SCENE_MEDIA, RENDER_EPISODE, QUALITY_CHECK
    status = Column(String, default="queued") # queued, in_progress, done, failed
    payload_json = Column(Text) # JSON string
    result_json = Column(Text, nullable=True) # JSON string
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
