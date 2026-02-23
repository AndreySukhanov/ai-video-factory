from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.db import Base


class VideoAnalytics(Base):
    __tablename__ = "video_analytics"

    id = Column(Integer, primary_key=True, index=True)
    youtube_upload_id = Column(Integer, ForeignKey("youtube_uploads.id"), nullable=True)
    youtube_video_id = Column(String, index=True)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    watch_time_minutes = Column(Float, default=0.0)
    average_view_duration_seconds = Column(Float, default=0.0)
    click_through_rate = Column(Float, default=0.0)  # CTR %
    impression_count = Column(Integer, default=0)
    subscriber_gain = Column(Integer, default=0)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
