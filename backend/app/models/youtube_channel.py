from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base


class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String, unique=True, index=True)
    channel_title = Column(String)
    access_token = Column(Text)  # Encrypted
    refresh_token = Column(Text)  # Encrypted
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    uploads = relationship("YouTubeUpload", back_populates="channel")


class YouTubeUpload(Base):
    __tablename__ = "youtube_uploads"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("youtube_channels.id"))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    story_idea_id = Column(Integer, ForeignKey("story_ideas.id"), nullable=True)
    youtube_video_id = Column(String, nullable=True)
    title = Column(String)
    description = Column(Text, default="")
    tags_json = Column(Text, default="[]")
    status = Column(String, default="pending")  # pending, uploading, published, scheduled, failed
    privacy_status = Column(String, default="private")
    scheduled_publish_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    youtube_url = Column(String, nullable=True)
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("YouTubeChannel", back_populates="uploads")
    project = relationship("Project")
    story_idea = relationship("StoryIdea")
    review_items = relationship("ReviewItem", back_populates="youtube_upload")
