from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Channel schemas ---
class YouTubeChannelRead(BaseModel):
    id: int
    channel_id: str
    channel_title: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthUrlResponse(BaseModel):
    auth_url: str


class AuthCallbackResponse(BaseModel):
    success: bool
    channel: Optional[YouTubeChannelRead] = None
    message: str = ""


# --- Upload schemas ---
class YouTubeUploadRequest(BaseModel):
    channel_id: int
    video_url: str  # URL or path to video
    title: str
    description: str = ""
    tags: List[str] = []
    privacy_status: str = "private"  # private, public, unlisted
    generate_metadata: bool = False  # Use LLM to generate title/desc/tags
    story_idea_text: str = ""  # For LLM metadata generation
    project_id: Optional[int] = None
    story_idea_id: Optional[int] = None


class YouTubeUploadScheduleRequest(YouTubeUploadRequest):
    scheduled_publish_at: datetime


class YouTubeUploadRead(BaseModel):
    id: int
    channel_id: int
    project_id: Optional[int] = None
    story_idea_id: Optional[int] = None
    youtube_video_id: Optional[str] = None
    title: str
    description: str = ""
    tags_json: str = "[]"
    status: str
    privacy_status: str = "private"
    scheduled_publish_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    youtube_url: Optional[str] = None
    error_text: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QuotaStatusResponse(BaseModel):
    daily_limit: int
    used: int
    remaining: int
    upload_cost: int
    max_uploads_remaining: int
    date: str
