from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.db import Base


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, index=True)  # fetch_trends, auto_generate, youtube_upload
    status = Column(String, default="pending")  # pending, active, paused, completed, failed
    cron_expression = Column(String, nullable=True)  # e.g. "0 */6 * * *"
    run_at = Column(DateTime(timezone=True), nullable=True)  # One-time scheduled run
    interval_seconds = Column(Integer, nullable=True)  # Recurring interval
    payload_json = Column(Text, default="{}")  # JSON task parameters
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0)
    is_recurring = Column(Boolean, default=False)
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
