from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base


class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, index=True)
    story_idea_id = Column(Integer, ForeignKey("story_ideas.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    video_url = Column(String, default="")           # URL to generated video file
    title = Column(String, default="")                # LLM-generated title
    description = Column(Text, default="")            # LLM-generated description
    tags_json = Column(Text, default="[]")            # JSON array of tags
    status = Column(String, default="pending_review")  # pending_review, approved, rejected, uploaded, published
    reviewer_notes = Column(Text, default="")         # Notes from reviewer
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    story_idea = relationship("StoryIdea")
    project = relationship("Project")
