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
    content_type: str = "other"

class TrendRead(TrendBase):
    id: int
    fetched_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    view_count: Optional[int] = None
    duration_sec: Optional[int] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: Optional[int] = None
    viral_coef: Optional[float] = None
    is_anomaly: bool = False
    matched_keyword: Optional[str] = None
    niche: Optional[str] = None

    class Config:
        from_attributes = True

class TrendFetchRequest(BaseModel):
    region: str = "US"
    category: str = ""
    max_per_source: int = 30
    keywords: List[str] = []
    platforms: List[str] = []  # empty = all enabled sources
    niche: Optional[str] = None  # astrology | relationships | motivation | ...

class NicheInfo(BaseModel):
    id: str
    display_name: str
    hashtag_count: int

class NichesResponse(BaseModel):
    niches: List[NicheInfo]


# --- TrendPattern (Phase 2: deep extraction) ---
class TrendPatternRead(BaseModel):
    id: int
    trend_id: int
    transcript_source: Optional[str] = None
    hook: Optional[str] = None
    story_beats_json: Optional[str] = None
    characters_json: Optional[str] = None
    title_formula: Optional[str] = None
    cta_structure_json: Optional[str] = None
    visual_style_json: Optional[str] = None
    viral_mechanic: Optional[str] = None
    adaptation_brief: Optional[str] = None
    anchor_prompt: Optional[str] = None
    character_card: Optional[str] = None
    extracted_at: Optional[datetime] = None
    llm_model: Optional[str] = None

    class Config:
        from_attributes = True

class ExtractPatternResponse(BaseModel):
    success: bool
    pattern: Optional[TrendPatternRead] = None
    error: Optional[str] = None


# --- Clone-to-brief (Phase 3) ---
class CloneBriefResponse(BaseModel):
    success: bool
    # Pre-filled IdeaForm payload
    idea: Optional[str] = None
    genre: Optional[str] = "drama"
    episodes_count: int = 5
    duration: int = 6
    aspect_ratio: str = "9:16"
    anchor_prompt: Optional[str] = None
    character_card: Optional[str] = None
    suggested_title: Optional[str] = None
    title_formula: Optional[str] = None
    viral_mechanic: Optional[str] = None
    folder_url: Optional[str] = None  # /static/clones/trend-{id}/ — папка с артефактами
    error: Optional[str] = None

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
    narrative_structure: Optional[str] = None
    regenerable: Optional[str] = None
    analysis_json: Optional[str] = None  # Trendsee-style extended analysis

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
    model: str = "laozhang"
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
    model: str = "laozhang"
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
