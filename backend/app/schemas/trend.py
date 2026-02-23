from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Trend schemas ---
class TrendBase(BaseModel):
    title: str
    description: str = ""
    source: str = ""
    region: str = "US"
    category: str = ""
    score: float = 0.0
    keywords_json: str = "[]"
    url: str = ""
    velocity_score: float = 0.0
    trend_stage: str = "unknown"
    competition_level: Optional[float] = None
    opportunity_score: Optional[float] = None

class TrendRead(TrendBase):
    id: int
    fetched_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    view_count: Optional[int] = None

    class Config:
        from_attributes = True

class TrendFetchRequest(BaseModel):
    region: str = "US"
    category: str = ""
    max_per_source: int = 20

class TrendFetchResponse(BaseModel):
    success: bool
    count: int
    trends: List[TrendRead] = []


# --- StoryIdea schemas ---
class StoryIdeaBase(BaseModel):
    idea_text: str
    genre: str = "drama"
    virality_score: float = 0.5
    status: str = "pending"

class StoryIdeaRead(StoryIdeaBase):
    id: int
    trend_id: Optional[int] = None
    project_id: Optional[int] = None
    created_at: Optional[datetime] = None
    hook_type: Optional[str] = None
    suggested_title: Optional[str] = None
    suggested_tags_json: Optional[str] = None
    variants_json: Optional[str] = None

    class Config:
        from_attributes = True

class TrendAnalyzeRequest(BaseModel):
    max_ideas: int = 5
    genre: str = ""

class TrendAnalyzeResponse(BaseModel):
    success: bool
    count: int
    ideas: List[StoryIdeaRead] = []

class IdeaApproveResponse(BaseModel):
    success: bool
    idea: StoryIdeaRead

class IdeaGenerateRequest(BaseModel):
    genre: str = ""
    model: str = "veo3"
    duration: int = 6
    aspect_ratio: str = "9:16"

class IdeaGenerateResponse(BaseModel):
    success: bool
    idea: StoryIdeaRead
    project_id: Optional[int] = None
    message: str = ""


# --- Trend Generate (Phase 9) ---
class TrendGenerateRequest(BaseModel):
    genre: str = "drama"
    model: str = "veo3"
    duration: int = 6
    aspect_ratio: str = "9:16"

class TrendGenerateResponse(BaseModel):
    success: bool
    project_id: Optional[int] = None
    idea_id: Optional[int] = None
    seo_title: str = ""
    seo_description: str = ""
    seo_tags: List[str] = []
    seo_hashtags: List[str] = []
    message: str = ""
