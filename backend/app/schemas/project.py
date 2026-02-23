from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CharacterBase(BaseModel):
    name: str
    role: str
    description: str

class Character(CharacterBase):
    id: int
    project_id: int
    reference_image_url: Optional[str] = None
    appearance_prompt: Optional[str] = None
    
    class Config:
        from_attributes = True

class EpisodeBase(BaseModel):
    number: int
    title: Optional[str] = None
    hook: Optional[str] = None
    synopsis: Optional[str] = None
    status: str = "pending"
    quality_score: Optional[float] = None

class Episode(EpisodeBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    target_platform: str = "tiktok"
    total_episodes: int = 1
    episode_duration_sec: int = 60

class ProjectCreate(BaseModel):
    idea: str
    genre: str
    target_platform: str = "tiktok"
    episodes_count: int = 1
    episode_duration_sec: int = 60
    reference_image_url: Optional[str] = None  # Optional reference image

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    seo_tags_json: Optional[str] = None

class Project(ProjectBase):
    id: int
    status: str
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    seo_tags_json: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    episodes: List[Episode] = []
    characters: List[Character] = []

    class Config:
        from_attributes = True

class ProjectFull(Project):
    pass # Add scenes later if needed
