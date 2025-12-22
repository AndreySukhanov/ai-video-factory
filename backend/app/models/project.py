from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Nullable for MVP/No Auth
    title = Column(String, index=True, nullable=True)
    logline = Column(String, nullable=True)
    genre = Column(String, nullable=True)
    target_platform = Column(String, default="tiktok")
    reference_image_url = Column(String, nullable=True)  # Optional reference image for the series
    total_episodes = Column(Integer, default=1)
    episode_duration_sec = Column(Integer, default=60)
    status = Column(String, default="draft") # draft, generating, ready, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    episodes = relationship("Episode", back_populates="project")
    characters = relationship("Character", back_populates="project")
