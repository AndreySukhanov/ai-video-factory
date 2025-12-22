from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base

class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"))
    number = Column(Integer)
    duration_sec = Column(Integer)
    what_happens = Column(Text)
    visual_prompt = Column(Text, nullable=True)
    reference_image_url = Column(String, nullable=True)  # Optional reference image for image-to-video
    dialogue_json = Column(Text, nullable=True) # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    episode = relationship("Episode", back_populates="scenes")
