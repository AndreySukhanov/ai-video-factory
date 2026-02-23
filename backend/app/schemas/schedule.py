from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ScheduledTaskBase(BaseModel):
    task_type: str  # fetch_trends, auto_generate, youtube_upload
    cron_expression: Optional[str] = None
    run_at: Optional[datetime] = None
    interval_seconds: Optional[int] = None
    payload_json: str = "{}"
    is_recurring: bool = False


class ScheduledTaskCreate(ScheduledTaskBase):
    pass


class ScheduledTaskRead(ScheduledTaskBase):
    id: int
    status: str = "pending"
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    run_count: int = 0
    error_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrendFetchToggleResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
