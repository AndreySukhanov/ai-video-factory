from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base

class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    number = Column(Integer)
    title = Column(String, nullable=True)
    hook = Column(String, nullable=True)
    synopsis = Column(Text, nullable=True)
    status = Column(String, default="pending") # pending, generating, ready, failed
    quality_score = Column(Float, nullable=True)
    quality_report = Column(Text, nullable=True) # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="episodes")
    scenes = relationship("Scene", back_populates="episode")
