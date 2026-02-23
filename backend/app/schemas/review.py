from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ReviewItemCreate(BaseModel):
    video_url: str
    title: str = ""
    description: str = ""
    tags: List[str] = []
    project_id: Optional[int] = None


class ReviewItemRead(BaseModel):
    id: int
    story_idea_id: Optional[int] = None
    project_id: Optional[int] = None
    video_url: str = ""
    title: str = ""
    description: str = ""
    tags_json: str = "[]"
    status: str = "pending_review"
    reviewer_notes: str = ""
    created_at: Optional[datetime] = None
    # Joined fields
    genre: Optional[str] = None
    virality_score: Optional[float] = None
    idea_text: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewApproveRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    reviewer_notes: str = ""


class ReviewScheduleRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    scheduled_publish_at: datetime
    reviewer_notes: str = ""


class ReviewRejectRequest(BaseModel):
    reviewer_notes: str = ""


class ReviewActionResponse(BaseModel):
    success: bool
    item: ReviewItemRead
    message: str = ""
