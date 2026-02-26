from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base


class Trend(Base):
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, default="")
    source = Column(String, index=True)  # youtube, google_trends, apify, tiktok
    region = Column(String, default="US", index=True)  # ISO country code: US, RU, GB, etc.
    category = Column(String, default="")
    score = Column(Float, default=0.0)
    keywords_json = Column(Text, default="[]")  # JSON array of keywords
    url = Column(String, default="")
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    # Velocity & tracking fields
    velocity_score = Column(Float, default=0.0)  # views / hours_since_publish
    view_count = Column(Integer, nullable=True)  # raw view count
    published_at = Column(DateTime(timezone=True), nullable=True)  # original video publish time
    trend_stage = Column(String, default="unknown")  # rising, peaking, declining, unknown
    duration_sec = Column(Integer, nullable=True)  # original video duration in seconds
    competition_level = Column(Float, nullable=True)  # 0.0 - 1.0
    opportunity_score = Column(Float, nullable=True)  # high velocity + low competition

    ideas = relationship("StoryIdea", back_populates="trend")


class StoryIdea(Base):
    __tablename__ = "story_ideas"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=True)
    idea_text = Column(Text)
    genre = Column(String, default="drama")
    virality_score = Column(Float, default=0.5)
    status = Column(String, default="pending")  # pending, approved, generated, published
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Enhanced LLM output fields
    hook_type = Column(String, nullable=True)  # question, pov, cliffhanger, contrast, shocking_stat
    suggested_title = Column(String, nullable=True)  # SEO-optimized title
    suggested_tags_json = Column(Text, nullable=True)  # JSON array of suggested tags
    variants_json = Column(Text, nullable=True)  # JSON array of variant angles

    trend = relationship("Trend", back_populates="ideas")
    project = relationship("Project")


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    trend_title_hash = Column(String, index=True)  # SHA256(title|source|url)[:32]
    title = Column(String)
    source = Column(String)
    view_count = Column(Integer, default=0)
    velocity_score = Column(Float, default=0.0)
    score = Column(Float, default=0.0)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now())
