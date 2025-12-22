from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobBase(BaseModel):
    type: str
    status: str
    payload_json: str
    result_json: Optional[str] = None
    error_text: Optional[str] = None

class Job(JobBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobWithProgress(Job):
    """Job with additional progress tracking fields"""
    progress: int = 0
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    project_id: Optional[int] = None

