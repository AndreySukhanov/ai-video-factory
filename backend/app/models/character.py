from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String, index=True)
    role = Column(String)  # main, support, antagonist, etc.
    description = Column(Text)
    reference_image_url = Column(String, nullable=True)  # Generated character image
    appearance_prompt = Column(Text, nullable=True)  # Prompt used to generate the character
    character_card = Column(Text, nullable=True)       # Fixed text <= 50 words for Veo 3.1
    voice_description = Column(String, nullable=True)  # "warm raspy female voice, American accent"
    seed = Column(Integer, nullable=True)              # Fixed seed for visual stability
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="characters")
